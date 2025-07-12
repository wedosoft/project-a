"""
Anthropic 검색 오케스트레이터 (상담원 채팅 전용)

기존 HybridSearchManager를 활용하여 상담원 채팅에 최적화된 검색 기능을 제공합니다.
Constitutional AI 원칙을 적용하여 안전하고 유용한 검색 결과를 생성합니다.
"""

import logging
import yaml
import json
import traceback
from typing import Dict, List, Optional, Any, AsyncGenerator
from pathlib import Path

from .intent_analyzer import AnthropicIntentAnalyzer, SearchContext
from core.search.retriever import retrieve_top_k_docs
from core.search.embeddings.embedder import embed_documents_optimized
from core.search.enhanced_search import EnhancedSearchEngine
from core.llm.manager import LLMManager
from core.llm.models.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicSearchOrchestrator:
    """
    상담원 채팅을 위한 검색 오케스트레이터
    
    기존 HybridSearchManager와 의도 분석기를 결합하여
    상담원에게 최적화된 검색 경험을 제공합니다.
    """
    
    def __init__(self, 
                 vector_db = None,
                 llm_manager: Optional[LLMManager] = None):
        """
        초기화
        
        Args:
            vector_db: 벡터 데이터베이스 인스턴스
            llm_manager: LLM 매니저 인스턴스
        """
        self.intent_analyzer = AnthropicIntentAnalyzer()
        self.enhanced_search = EnhancedSearchEngine(vector_db, llm_manager)
        self.vector_db = vector_db
        self.llm_manager = llm_manager
        
        # Constitutional AI 프롬프트 로드
        self.prompts = self._load_constitutional_prompts()
        
        logger.info("AnthropicSearchOrchestrator 초기화 완료")
    
    def _load_constitutional_prompts(self) -> Dict[str, Any]:
        """Constitutional AI 프롬프트 템플릿을 로드합니다"""
        try:
            prompts_path = Path(__file__).parent.parent / "prompts" / "constitutional_search.yaml"
            
            if prompts_path.exists():
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    prompts = yaml.safe_load(f)
                logger.info("Constitutional AI 프롬프트 로드 완료")
                return prompts
            else:
                logger.warning(f"프롬프트 파일을 찾을 수 없음: {prompts_path}")
                return self._get_default_prompts()
                
        except Exception as e:
            logger.error(f"프롬프트 로드 실패: {e}")
            return self._get_default_prompts()
    
    def _get_default_prompts(self) -> Dict[str, Any]:
        """기본 프롬프트 템플릿을 반환합니다"""
        return {
            "constitutional_principles": {
                "helpful": "상담원 업무에 즉시 도움되는 정보 제공",
                "harmless": "개인정보 노출 절대 방지",
                "honest": "검색 한계와 신뢰도 명시"
            },
            "system_prompt": """당신은 숙련된 헬프데스크 팀장으로서, 상담원들에게 친절하고 명확한 가이드를 제공하는 역할을 합니다.
상담원이 고객 문의를 효과적으로 해결할 수 있도록 따뜻하고 전문적인 톤으로 도움을 주세요.""",
            "intent_prompts": {
                "general": {
                    "template": """상담원님께서 "{query}"에 대해 문의해주셨네요.

관련 문서들을 살펴본 결과, 다음과 같은 정보를 찾을 수 있었습니다:

{search_results}

📋 **상담 가이드**

이런 상황에서는 다음과 같이 접근해보시는 것을 권해드립니다:

• **핵심 포인트**: 위 문서들에서 가장 중요한 부분을 간단히 정리해드리면...
• **고객 응대 방법**: 이 정보를 바탕으로 고객에게는 이렇게 설명하시면 됩니다...
• **추가 체크사항**: 혹시 놓칠 수 있는 부분이나 함께 확인하면 좋을 점들...
• **에스컬레이션**: 만약 이 방법으로도 해결되지 않는다면...

💡 **팁**: 실무 경험상 이런 케이스에서는... 

검색 의도: {intent} | 우선순위: {urgency}

편안하게 참고하시고, 추가로 궁금한 점이 있으시면 언제든 말씀해주세요!"""
                }
            }
        }
    
    async def execute_agent_search(self, 
                                 query: str, 
                                 tenant_id: str,
                                 platform: str = "freshdesk",
                                 stream: bool = False,
                                 chat_history: List[Dict[str, str]] = None,
                                 force_intent: Optional[str] = None,
                                 skip_rag: bool = False) -> AsyncGenerator[Dict[str, Any], None]:
        """
        상담원 검색을 실행하고 결과를 반환합니다
        
        Args:
            query: 상담원의 자연어 쿼리
            tenant_id: 테넌트 ID
            platform: 플랫폼 ID
            stream: 스트리밍 여부
            
        Yields:
            Dict[str, Any]: 검색 결과 청크
        """
        try:
            logger.info(f"상담원 검색 시작: '{query[:50]}...' (tenant: {tenant_id}, skip_rag: {skip_rag}, force_intent: {force_intent})")
            
            # skip_rag가 True면 RAG 검색 없이 직접 LLM 응답
            if skip_rag:
                logger.info("자유 모드: RAG 검색을 건너뛰고 직접 LLM 응답 생성")
                direct_response = await self._generate_direct_llm_response(query, chat_history)
                
                final_result = {
                    "type": "final",
                    "search_context": {
                        "intent": "general",
                        "urgency": "general",
                        "keywords": [],
                        "response_type": "direct_llm",
                        "mode": "free"
                    },
                    "ai_summary": direct_response,
                    "structured_response": direct_response,
                    "search_results": {"documents": [], "metadatas": [], "ids": [], "distances": []},
                    "total_results": 0,
                    "quality_score": 0.9
                }
                
                if stream:
                    yield {"type": "content", "content": direct_response}
                yield final_result
                return
            
            # 1. 의도 분석
            context = await self.intent_analyzer.analyze_search_intent(query)
            
            # force_intent가 있으면 덮어쓰기
            if force_intent:
                context.intent = force_intent
            
            # 의도 분석에 따른 처리 방식 결정
            if context.intent == "general" and any(keyword in context.clean_query.lower() for keyword in ["안녕", "hello", "hi", "어떻게", "무엇"]):
                # 일반 대화나 인사말의 경우 RAG 없이 LLM 직접 응답
                direct_response = await self._generate_direct_llm_response(context.clean_query, chat_history)
                
                final_result = {
                    "type": "final",
                    "search_context": {
                        "intent": context.intent,
                        "urgency": context.urgency,
                        "keywords": context.keywords,
                        "response_type": "direct_llm"
                    },
                    "structured_response": direct_response,
                    "total_results": 0,
                    "quality_score": 0.9
                }
                
                if stream:
                    yield {"type": "content", "content": direct_response}
                yield final_result
                return
            
            # 고급 검색 엔진 활용 가능성 검토
            enhanced_context = await self.enhanced_search.analyze_enhanced_query(context.clean_query)
            if enhanced_context.search_type in ["attachment", "category", "solution"]:
                # 고급 검색 실행
                enhanced_results = await self.enhanced_search.execute_enhanced_search(
                    context=enhanced_context,
                    tenant_id=tenant_id,
                    platform=platform,
                    top_k=5
                )
                
                if enhanced_results.get("total_results", 0) > 0:
                    # 고급 검색 결과가 있으면 기본 검색 대신 사용
                    search_results = enhanced_results
                else:
                    # 고급 검색 결과가 없으면 기본 검색으로 폴백
                    search_results = await self._perform_vector_search(context, tenant_id, platform)
            else:
                # 기본 벡터 검색 수행
                search_results = await self._perform_vector_search(context, tenant_id, platform)
            
            # 2. 벡터 검색 실행 (이미 위에서 처리됨)
            if not self.vector_db:
                logger.error("VectorDB가 초기화되지 않음")
                error_result = {
                    "type": "final",
                    "error": "검색 시스템이 초기화되지 않았습니다.",
                    "ai_summary": "검색 시스템에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    "search_results": {"documents": [], "metadatas": [], "ids": [], "distances": []},
                    "total_results": 0
                }
                yield error_result
                return
            
            logger.info(f"VectorDB 인스턴스 확인: {type(self.vector_db)}")
            
            # 벡터 검색 실행 (이미 위에서 처리되지 않은 경우만)
            if "search_results" not in locals():
                logger.info(f"벡터 검색 시작 - 쿠리: '{context.clean_query}', tenant: {tenant_id}, platform: {platform}")
                search_results = await self._perform_vector_search(context, tenant_id, platform)
                logger.info(f"벡터 검색 완료: {search_results.get('total_results', 0)}개 결과")
                logger.info(f"검색 결과 세부: {list(search_results.keys())}")
            else:
                logger.info(f"고급 검색 결과 사용: {search_results.get('total_results', 0)}개 결과")
            
            # 3. 검색 결과 스트리밍 처리
            if stream and search_results.get('total_results', 0) > 0:
                # 검색 결과를 실시간으로 스트리밍
                documents = search_results.get('documents', [])
                metadatas = search_results.get('metadatas', [])
                ids = search_results.get('ids', [])
                distances = search_results.get('distances', [])
                
                logger.info(f"스트리밍할 검색 결과: {len(documents)}개")
                logger.info(f"문서 예시: {documents[0][:100] if documents else 'None'}...")
                logger.info(f"메타데이터 예시: {metadatas[0] if metadatas else 'None'}")
                
                # 각 검색 결과를 개별적으로 스트리밍
                for i, (doc, meta, doc_id, distance) in enumerate(zip(documents, metadatas, ids, distances)):
                    result_item = {
                        "type": "search_result_item",
                        "content": f"검색 결과 {i+1}/{len(documents)}",
                        "result_data": {
                            "document": doc,
                            "metadata": meta,
                            "id": doc_id,
                            "distance": distance,
                            "index": i,
                            "total": len(documents)
                        }
                    }
                    logger.info(f"검색 결과 {i+1} 스트리밍: title='{meta.get('title', 'N/A')}', doc_type='{meta.get('doc_type', 'N/A')}'")
                    yield result_item
                    logger.info(f"검색 결과 {i+1} 스트리밍 완료")
                
                # 모든 검색 결과 스트리밍 완료
                yield {
                    "type": "search_complete",
                    "content": f"{search_results.get('total_results', 0)}개의 관련 문서를 찾았습니다.",
                    "total_results": search_results.get('total_results', 0)
                }
                logger.info("검색 결과 스트리밍 모두 완료")
            elif stream:
                # 검색 결과가 없는 경우에도 알림
                yield {
                    "type": "search_complete",
                    "content": "검색 결과가 없습니다.",
                    "total_results": 0
                }

            # 4. 결과 최적화 및 구조화
            enhanced_results = await self._enhance_results(search_results, context)
            
            # 4. Constitutional AI 응답 생성
            structured_response = ""
            if self.llm_manager and search_results.get('documents'):
                logger.info("Constitutional AI 응답 생성 시작")
                structured_response = await self._generate_constitutional_response(
                    enhanced_results, context, chat_history
                )
                logger.info("Constitutional AI 응답 생성 완료")
                
                if stream:
                    yield {"type": "content", "content": structured_response}
            else:
                structured_response = "검색 결과를 확인해주세요."
            
            # 5. 최종 결과 - AI 요약과 검색 결과 분리
            final_result = {
                "type": "final",
                "search_context": {
                    "intent": context.intent,
                    "urgency": context.urgency,
                    "keywords": context.keywords,
                    "filters": context.filters
                },
                # AI 요약 응답
                "ai_summary": structured_response if 'structured_response' in locals() else "검색 결과를 확인해주세요.",
                
                # 클릭 가능한 검색 결과들
                "search_results": {
                    "documents": enhanced_results.get('documents', []),
                    "metadatas": enhanced_results.get('metadatas', []),
                    "ids": enhanced_results.get('ids', []),
                    "distances": enhanced_results.get('distances', [])
                },
                
                "total_results": enhanced_results.get('total_results', 0),
                "quality_score": enhanced_results.get('search_quality_score', 0.0)
            }
            
            yield final_result
            
        except Exception as e:
            logger.error(f"상담원 검색 실패: {e}")
            logger.error(f"오류 스택: {traceback.format_exc()}")
            error_result = {
                "type": "error",
                "error": str(e),
                "content": f"검색 중 오류가 발생했습니다: {str(e)}"
            }
            yield error_result
    
    async def _perform_vector_search(self, context: SearchContext, tenant_id: str, platform: str) -> Dict[str, Any]:
        """
        벡터 검색을 수행합니다
        
        Args:
            context: 분석된 검색 컨텍스트
            tenant_id: 테넌트 ID
            platform: 플랫폼 ID
            
        Returns:
            Dict[str, Any]: 검색 결과
        """
        try:
            # 우선순위에 따른 결과 수 조정
            urgency_to_top_k = {
                "immediate": 3,
                "today": 5,
                "general": 5,  # 7->5로 줄임
                "reference": 7
            }
            top_k = urgency_to_top_k.get(context.urgency, 5)  # 기본값도 5로
            
            # 종합적 검색: 티켓과 아티클 모두 검색 (실용성 우선)
            doc_types = ["ticket", "article"] 
            
            # 각 타입별로 적절한 수 검색
            tickets_limit = 3  # 관련 티켓 사례
            articles_limit = 3  # 관련 문서/가이드
            
            logger.info(f"종합 검색: tickets({tickets_limit}개) + articles({articles_limit}개)")
            
            # 쿼리 임베딩 생성
            try:
                embeddings = embed_documents_optimized([context.clean_query], mode="multilingual")
                query_embedding = embeddings[0] if embeddings else None
                if not query_embedding:
                    logger.error("쿼리 임베딩 생성 실패")
                    return {
                        "documents": [],
                        "total_results": 0,
                        "search_quality_score": 0.0
                    }
            except Exception as e:
                logger.error(f"임베딩 생성 중 오류: {e}")
                return {
                    "documents": [],
                    "total_results": 0,
                    "search_quality_score": 0.0
                }
            
            # 검색 실행
            all_documents = []
            all_metadatas = []
            all_ids = []
            all_distances = []
            
            logger.info(f"검색 조건: tenant_id='{tenant_id}', platform='{platform}'")
            
            # 티켓 검색
            logger.info(f"티켓 검색 시도: top_k={tickets_limit}")
            ticket_result = self.vector_db.search(
                query_embedding=query_embedding,
                top_k=tickets_limit,
                tenant_id=tenant_id,
                platform=platform,
                doc_type="ticket"
            )
            
            # 아티클 검색
            logger.info(f"아티클 검색 시도: top_k={articles_limit}")
            article_result = self.vector_db.search(
                query_embedding=query_embedding,
                top_k=articles_limit,
                tenant_id=tenant_id,
                platform=platform,
                doc_type="article"
            )
            
            # 결과 통합 및 URL 정보 추가
            if ticket_result:
                ticket_docs = ticket_result.get("documents", [])
                ticket_metas = ticket_result.get("metadatas", [])
                
                # 티켓 메타데이터에 URL 정보 추가
                for meta in ticket_metas:
                    if not meta.get("source_url"):
                        ticket_id = meta.get("original_id") or meta.get("source_id")
                        if ticket_id:
                            # Freshdesk 티켓 URL 생성
                            domain = meta.get("domain", "wedosoft")  # 기본 도메인
                            meta["source_url"] = f"https://{domain}.freshdesk.com/a/tickets/{ticket_id}"
                            meta["display_url"] = f"티켓 #{ticket_id}"
                
                all_documents.extend(ticket_docs)
                all_metadatas.extend(ticket_metas)
                all_ids.extend(ticket_result.get("ids", []))
                all_distances.extend(ticket_result.get("distances", []))
                
                logger.info(f"티켓 검색 결과: {len(ticket_docs)}개")
            
            if article_result:
                article_docs = article_result.get("documents", [])
                article_metas = article_result.get("metadatas", [])
                
                # 아티클 메타데이터에 URL 정보 추가
                for meta in article_metas:
                    if not meta.get("source_url"):
                        article_id = meta.get("original_id") or meta.get("source_id")
                        if article_id:
                            # Freshdesk KB 아티클 URL 생성 
                            domain = meta.get("domain", "wedosoft")
                            meta["source_url"] = f"https://{domain}.freshdesk.com/a/solutions/articles/{article_id}"
                            meta["display_url"] = f"문서 #{article_id}"
                
                all_documents.extend(article_docs)
                all_metadatas.extend(article_metas)
                all_ids.extend(article_result.get("ids", []))
                all_distances.extend(article_result.get("distances", []))
                
                logger.info(f"아티클 검색 결과: {len(article_docs)}개")
            
            # 검색 결과가 없으면 필터링 조건 로깅
            if len(all_documents) == 0:
                logger.warning(f"검색 결과 없음. 필터링 조건 확인 필요: tenant_id={tenant_id}, platform={platform}, doc_types={doc_types}")
                logger.info(f"임베딩 벡터 차원: {len(query_embedding) if query_embedding else 'None'}")
                
                # 전체 문서 수 확인
                try:
                    total_count = self.vector_db.count()
                    tenant_count = self.vector_db.count(tenant_id=tenant_id) if tenant_id else 0
                    logger.info(f"전체 문서 수: {total_count}, tenant '{tenant_id}' 문서 수: {tenant_count}")
                    
                    # 필터 없는 검색으로 샘플 데이터 확인
                    sample_result = self.vector_db.client.scroll(
                        collection_name=self.vector_db.collection_name,
                        limit=5,
                        with_payload=True,
                        with_vectors=False
                    )
                    sample_points = sample_result[0] if sample_result else []
                    logger.error(f"🔍 실제 DB 스키마 분석 - 샘플 데이터 ({len(sample_points)}개):")
                    
                    tenant_ids_found = set()
                    platforms_found = set()
                    doc_types_found = set()
                    
                    for i, point in enumerate(sample_points):
                        payload = point.payload
                        t_id = payload.get('tenant_id')
                        platform = payload.get('platform') 
                        doc_type = payload.get('doc_type')
                        legacy_type = payload.get('type')
                        
                        tenant_ids_found.add(t_id)
                        platforms_found.add(platform)
                        doc_types_found.add(doc_type)
                        
                        logger.error(f"  📄 문서 {i+1}: tenant_id='{t_id}', platform='{platform}', doc_type='{doc_type}', type='{legacy_type}'")
                        
                    logger.error(f"🎯 발견된 실제 값들:")
                    logger.error(f"   tenant_ids: {sorted([t for t in tenant_ids_found if t])}")
                    logger.error(f"   platforms: {sorted([p for p in platforms_found if p])}")
                    logger.error(f"   doc_types: {sorted([d for d in doc_types_found if d])}")
                    
                    # 필터 없는 벡터 검색으로 임베딩 테스트
                    try:
                        logger.error("🧪 필터 없는 벡터 검색 테스트:")
                        no_filter_result = self.vector_db.client.search(
                            collection_name=self.vector_db.collection_name,
                            query_vector=query_embedding,
                            limit=3,
                            with_payload=True
                        )
                        logger.error(f"   필터 없는 검색 결과: {len(no_filter_result)}개")
                        if no_filter_result:
                            for i, hit in enumerate(no_filter_result):
                                score = hit.score
                                payload = hit.payload
                                logger.error(f"   결과 {i+1}: score={score:.3f}, tenant='{payload.get('tenant_id')}', platform='{payload.get('platform')}', doc_type='{payload.get('doc_type')}'")
                    except Exception as filter_err:
                        logger.error(f"   필터 없는 검색 실패: {filter_err}")
                    
                except Exception as e:
                    logger.error(f"문서 수 확인 실패: {e}")
            return {
                "documents": all_documents,
                "metadatas": all_metadatas,
                "ids": all_ids,
                "distances": all_distances,
                "total_results": len(all_documents),
                "search_quality_score": 0.8 if all_documents else 0.0
            }
            
        except Exception as e:
            logger.error(f"벡터 검색 실패: {e}")
            return {
                "documents": [],
                "total_results": 0,
                "search_quality_score": 0.0
            }
            
    
    async def _enhance_results(self, 
                             search_results: Dict[str, Any], 
                             context: SearchContext) -> Dict[str, Any]:
        """
        검색 결과를 상담원 사용에 최적화합니다
        
        Args:
            search_results: 원본 검색 결과
            context: 검색 컨텍스트
            
        Returns:
            Dict[str, Any]: 최적화된 검색 결과
        """
        try:
            enhanced = search_results.copy()
            
            # 1. 결과 우선순위 조정
            enhanced = self._adjust_results_priority(enhanced, context)
            
            # 2. 개인정보 마스킹
            enhanced = self._mask_sensitive_info(enhanced)
            
            # 3. 상담원 친화적 메타데이터 추가
            enhanced = self._add_agent_metadata(enhanced, context)
            
            # 4. 액션 아이템 생성
            enhanced["action_items"] = self._generate_action_items(enhanced, context)
            
            # 5. 관련 제안 생성
            enhanced["related_suggestions"] = self._generate_related_suggestions(enhanced, context)
            
            logger.debug("검색 결과 최적화 완료")
            return enhanced
            
        except Exception as e:
            logger.error(f"결과 최적화 실패: {e}")
            return search_results
    
    def _adjust_results_priority(self, 
                               results: Dict[str, Any], 
                               context: SearchContext) -> Dict[str, Any]:
        """우선순위에 따라 결과 순서를 조정합니다"""
        if context.urgency == "immediate":
            # 즉시 처리 필요한 경우 해결된 사례 우선
            # 구현 생략 (실제로는 메타데이터 기반 정렬)
            pass
        
        return results
    
    def _mask_sensitive_info(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """개인정보 및 민감한 정보를 마스킹합니다"""
        import re
        
        # 이메일 마스킹 패턴
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # 전화번호 마스킹 패턴
        phone_pattern = r'\b\d{3}-\d{3,4}-\d{4}\b'
        
        # 문서 내용 마스킹
        documents = results.get('documents', [])
        for i, doc in enumerate(documents):
            # 이메일 마스킹
            doc = re.sub(email_pattern, '***@***.***', doc)
            # 전화번호 마스킹
            doc = re.sub(phone_pattern, '***-****-****', doc)
            documents[i] = doc
        
        results['documents'] = documents
        
        return results
    
    def _add_agent_metadata(self, 
                          results: Dict[str, Any], 
                          context: SearchContext) -> Dict[str, Any]:
        """상담원 친화적 메타데이터를 추가합니다"""
        metadatas = results.get('metadatas', [])
        
        for metadata in metadatas:
            # 상담원 친화적 레이블 추가
            if metadata.get('doc_type') == 'ticket':
                metadata['agent_label'] = '유사 사례'
            elif metadata.get('doc_type') == 'article':
                metadata['agent_label'] = '지식베이스'
            
            # 실행 가능 여부 표시
            if metadata.get('status') == 'solved':
                metadata['actionable'] = True
            else:
                metadata['actionable'] = False
        
        results['metadatas'] = metadatas
        return results
    
    def _generate_action_items(self, 
                             results: Dict[str, Any], 
                             context: SearchContext) -> List[str]:
        """검색 결과 기반 액션 아이템을 생성합니다"""
        action_items = []
        
        if context.intent == "problem_solving":
            action_items.extend([
                "유사 사례의 해결 단계 확인",
                "고객에게 임시 해결방안 제시",
                "필요시 기술팀에 에스컬레이션"
            ])
        elif context.intent == "info_gathering":
            action_items.extend([
                "관련 정책 문서 확인",
                "최신 업데이트 사항 점검",
                "고객에게 정확한 정보 제공"
            ])
        
        return action_items
    
    def _generate_related_suggestions(self, 
                                    results: Dict[str, Any], 
                                    context: SearchContext) -> List[str]:
        """관련 제안을 생성합니다"""
        suggestions = []
        
        # 검색 결과 기반 제안
        if results.get('total_results', 0) > 0:
            suggestions.append("유사한 다른 검색어로 추가 검색")
            suggestions.append("최근 업데이트된 문서 확인")
        
        # 의도 기반 제안
        if context.intent == "problem_solving":
            suggestions.append("에스컬레이션 가이드라인 검토")
        
        return suggestions
    
    async def _generate_constitutional_response(self, 
                                              results: Dict[str, Any], 
                                              context: SearchContext,
                                              chat_history: List[Dict[str, str]] = None) -> str:
        """
        Constitutional AI 원칙을 적용한 구조화된 응답을 생성합니다
        
        Args:
            results: 검색 결과
            context: 검색 컨텍스트
            
        Returns:
            str: 구조화된 응답
        """
        try:
            # 프롬프트 템플릿 선택
            intent_prompts = self.prompts.get("intent_prompts", {})
            template_data = intent_prompts.get(context.intent, intent_prompts.get("general", {}))
            prompt_template = template_data.get("template", "")
            
            if not prompt_template:
                return "검색 결과를 처리할 수 없습니다."
            
            # 검색 결과 포맷팅
            formatted_results = self._format_search_results(results)
            
            # 프롬프트 생성
            prompt = prompt_template.format(
                query=context.original_query,
                intent=context.intent,
                urgency=context.urgency,
                search_results=formatted_results
            )
            
            # LLM 호출
            if self.llm_manager:
                # 대화 히스토리 포함
                messages = []
                if chat_history:
                    # 이전 대화 추가
                    messages.extend(chat_history)
                # 현재 쿼리 추가
                messages.append({"role": "user", "content": prompt})
                
                response = await self.llm_manager.generate(
                    messages=messages,
                    provider=LLMProvider.ANTHROPIC, 
                    model="claude-3-haiku-20240307",
                    max_tokens=1000
                )
                
                if response and response.success:
                    logger.debug(f"Constitutional AI 응답 성공: {len(response.content)}자")
                    return response.content
                else:
                    logger.warning(f"LLM 응답 실패: {response.error if response else 'No response'}")
                    return "죄송합니다. 일시적으로 응답을 생성할 수 없습니다."
            
            return "응답 생성에 실패했습니다. 검색된 문서를 참고하여 직접 확인해 주세요."
            
        except Exception as e:
            logger.error(f"Constitutional AI 응답 생성 실패: {e}")
            return f"응답 생성 중 오류가 발생했습니다: {str(e)[:100]}... 검색된 문서를 직접 확인해 주세요."
    
    async def _generate_direct_llm_response(self, query: str, chat_history: List[Dict[str, str]] = None) -> str:
        """
        RAG 없이 LLM에 직접 질문하여 응답을 생성합니다 (일반 대화용)
        
        Args:
            query: 사용자 질문
            
        Returns:
            str: LLM 응답
        """
        try:
            # 일반 대화용 프롬프트
            prompt = f"""당신은 고객 지원 상담원을 돕는 AI 어시스턴트입니다.

상담원의 질문: {query}

다음 원칙에 따라 친근하고 도움이 되는 답변을 제공해주세요:
1. 상담원에게 도움이 되는 정보 제공
2. 정확하고 신뢰할 수 있는 내용
3. 친근하고 전문적인 톤
4. 한국어로 답변
5. 답변 길이는 2-3문장으로 간결하게

답변:"""

            # LLM 호출
            if self.llm_manager:
                # 대화 히스토리 포함
                messages = []
                if chat_history:
                    messages.extend(chat_history)
                messages.append({"role": "user", "content": prompt})
                
                response = await self.llm_manager.generate(
                    messages=messages,
                    provider=LLMProvider.ANTHROPIC,
                    model="claude-3-haiku-20240307",
                    max_tokens=500
                )
                
                if response and response.success:
                    return response.content
                else:
                    logger.warning(f"LLM 응답 실패: {response.error if response else 'No response'}")
                    return "죄송합니다. 일시적으로 응답을 생성할 수 없습니다."
            
            # fallback 응답
            logger.warning("LLM 매니저를 사용할 수 없어 기본 응답 반환")
            return "안녕하세요! 어떤 도움이 필요하신지 알려주시면 최선을 다해 도와드리겠습니다."
            
        except Exception as e:
            logger.error(f"직접 LLM 응답 생성 실패: {e}")
            # 일반 대화의 경우 친근한 기본 응답 제공
            if any(keyword in query.lower() for keyword in ["안녕", "hello", "hi"]):
                return "안녕하세요! 😊 오늘 어떤 일로 도움이 필요하신가요?"
            else:
                return "안녕하세요! 현재 시스템에 일시적인 문제가 있어 기본 응답을 드립니다. 기술적인 문제가 있으시면 구체적으로 알려주세요."
    
    def _format_search_results(self, results: Dict[str, Any]) -> str:
        """검색 결과를 프롬프트에 적합한 형태로 포맷팅합니다"""
        formatted = []
        
        documents = results.get('documents', [])
        metadatas = results.get('metadatas', [])
        distances = results.get('distances', [])
        
        logger.info(f"포맷팅할 검색 결과: {len(documents)}개 문서")
        
        for i, (doc, meta, distance) in enumerate(zip(documents[:7], metadatas[:7], distances[:7])):  # 최대 7개
            title = meta.get('title', meta.get('subject', f'문서 {i+1}'))
            doc_type = meta.get('doc_type', 'unknown')
            relevance = round((1 - distance/2) * 100, 1) if distance else 'N/A'
            
            # 문서 내용에서 첫 300자 추출 (더 많은 컨텍스트 제공)
            content_preview = doc[:300] if doc else "내용 없음"
            
            formatted.append(f"""
📄 검색 결과 {i+1} (관련도: {relevance}%):
제목: {title}
유형: {doc_type}
내용: {content_preview}
---""")
        
        result_text = "\n".join(formatted)
        logger.info(f"포맷팅된 결과 길이: {len(result_text)}자")
        return result_text