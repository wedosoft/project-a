"""
하이브리드 검색 어댑터

기존 execute_init_sequential() 결과 구조와 호환되도록
HybridSearchManager 결과를 변환하는 어댑터 모듈
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

# LangChain Runnable 병렬 처리
from langchain_core.runnables import RunnableParallel, RunnableLambda

logger = logging.getLogger(__name__)


class InitHybridAdapter:
    """
    init 엔드포인트용 하이브리드 검색 어댑터
    
    기존 execute_init_sequential() 호환성을 유지하면서
    HybridSearchManager의 고급 기능을 활용
    """
    
    def __init__(self):
        self.logger = logger
    
    async def execute_hybrid_init(
        self,
        hybrid_manager,
        llm_manager,
        ticket_data: Dict[str, Any],
        tenant_id: str,
        platform: str = "freshdesk",
        include_summary: bool = True,
        include_similar_tickets: bool = True, 
        include_kb_docs: bool = True,
        top_k_tickets: int = 3,
        top_k_kb: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        하이브리드 검색을 실행하고 기존 형식으로 반환
        
        Args:
            hybrid_manager: HybridSearchManager 인스턴스
            llm_manager: LLMManager 인스턴스 (요약용)
            ticket_data: 티켓 데이터
            기타: 기존 execute_init_sequential과 동일한 파라미터
            
        Returns:
            기존 execute_init_sequential()과 동일한 형식
        """
        import time
        import asyncio
        start_time = time.time()
        
        try:
            results = {}
            
            # LangChain RunnableParallel을 올바르게 사용한 병렬 실행
            runnables = {}
            
            # 요약 태스크 - 최적화된 JSON 기반 Runnable
            if include_summary:
                def create_summary_runnable():
                    async def summary_func(_):
                        summary_start = time.time()
                        self.logger.info("🎯 [조회 티켓 프리미엄] ticket_view 템플릿 요약 생성 시작")
                        
                        # 조회 티켓 최우선 품질: ticket_view 템플릿 직접 사용
                        markdown_summary = await self._generate_premium_realtime_summary(
                            llm_manager, ticket_data
                        )
                        
                        summary_time = time.time() - summary_start
                        self.logger.info(f"🎯 [조회 티켓 프리미엄] 완료 ({summary_time:.2f}초) - 길이: {len(markdown_summary)}문자")
                        
                        # 기존 형식과 호환되도록 래핑
                        return {
                            "result": {
                                "task_type": "summary",
                                "summary": {"ticket_summary": markdown_summary},
                                "success": True,
                                "template_used": "ticket_view"  # 디버깅용
                            }, 
                            "execution_time": summary_time
                        }
                    return RunnableLambda(summary_func)
                
                runnables["summary"] = create_summary_runnable()
            
            # 검색 태스크 - 독립적인 Runnable
            if include_similar_tickets or include_kb_docs:
                def create_search_runnable():
                    async def search_func(_):
                        search_start = time.time()
                        self.logger.info("하이브리드 검색 시작 (병렬)")
                        
                        # 검색 쿼리 구성
                        search_query = f"{ticket_data.get('subject', '')} {ticket_data.get('description_text', '')}"[:500]
                        
                        # 하이브리드 검색 실행
                        hybrid_results = await hybrid_manager.hybrid_search(
                            query=search_query,
                            tenant_id=tenant_id,
                            platform=platform,
                            top_k=max(top_k_tickets, top_k_kb),
                            doc_types=self._get_doc_types(include_similar_tickets, include_kb_docs),
                            enable_llm_enrichment=False,  # 성능 최적화
                            rerank_results=True,
                            min_similarity=0.6,
                        )
                        
                        search_time = time.time() - search_start
                        self.logger.info(f"하이브리드 검색 완료 ({search_time:.2f}초)")
                        return {"result": hybrid_results, "execution_time": search_time}
                    return RunnableLambda(search_func)
                
                runnables["search"] = create_search_runnable()
            
            # RunnableParallel로 진짜 병렬 실행
            if runnables:
                self.logger.info(f"LangChain RunnableParallel 시작: {len(runnables)}개 태스크")
                parallel_runner = RunnableParallel(runnables)
                
                # 빈 입력으로 실행 (각 태스크가 독립적)
                parallel_results = await parallel_runner.ainvoke({})
                
                # 결과 처리
                if "summary" in parallel_results:
                    summary_data = parallel_results["summary"]
                    results["summary"] = summary_data["result"]
                    results["summary_time"] = summary_data["execution_time"]
                
                if "search" in parallel_results:
                    search_data = parallel_results["search"]
                    hybrid_results = search_data["result"]
                    
                    # 결과를 기존 형식으로 변환
                    unified_search_result = self._convert_to_legacy_format(
                        hybrid_results, 
                        top_k_tickets,
                        top_k_kb,
                        include_similar_tickets,
                        include_kb_docs
                    )
                    
                    results["unified_search"] = unified_search_result
                    results["similar_tickets"] = unified_search_result.get("similar_tickets", [])
                    results["kb_documents"] = unified_search_result.get("kb_documents", [])
                    results["search_time"] = search_data["execution_time"]
            
            # 총 실행시간 및 성공 플래그 (기존 구조 유지)
            total_time = time.time() - start_time
            results.update({
                "total_execution_time": total_time,
                "execution_type": "hybrid_parallel_runnable",  # LangChain Runnable 사용
                "success": True,
                "summary_time": results.get("summary_time", 0),
                "search_time": results.get("search_time", 0)
            })
            
            self.logger.info(f"LangChain RunnableParallel 완료 (총 {total_time:.2f}초)")
            return results
            
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"하이브리드 RunnableParallel 실행 실패: {str(e)}"
            self.logger.error(f"{error_msg} (실행시간: {total_time:.2f}초)")
            
            # 기존 에러 구조 유지 (사이드 이펙트 방지)
            return {
                "summary": {
                    "task_type": "summary",
                    "error": "병렬 실행 실패로 인한 요약 생성 불가",
                    "success": False
                },
                "unified_search": {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "병렬 실행 실패로 인한 검색 불가",
                    "success": False
                },
                "similar_tickets": [],
                "kb_documents": [],
                "total_execution_time": total_time,
                "execution_type": "hybrid_parallel_runnable",
                "success": False,
                "error": error_msg
            }
    
    async def execute_hybrid_init_streaming(
        self,
        hybrid_manager,
        llm_manager,
        ticket_data: Dict[str, Any],
        tenant_id: str,
        platform: str = "freshdesk",
        include_summary: bool = True,
        include_similar_tickets: bool = True,
        include_kb_docs: bool = True,
        top_k_tickets: int = 3,
        top_k_kb: int = 3,
        retry_reason: Optional[str] = None,
        **kwargs
    ):
        """
        스트리밍 하이브리드 검색 실행
        
        Args:
            retry_reason: 재시도 이유 ("quality_low", "detail_insufficient", etc.)
            기타: execute_hybrid_init과 동일한 파라미터
            
        Yields:
            Dict[str, Any]: 스트리밍 결과 청크 또는 최종 결과
        """
        import time
        start_time = time.time()
        
        try:
            # 스트리밍 요약 생성 먼저 시작
            if include_summary:
                yield {"type": "summary_start", "message": "요약 생성 시작..."}
                
                # PromptBuilder를 사용하여 YAML 템플릿 기반 프롬프트 생성
                summary_chunks = []
                
                try:
                    from core.llm.summarizer.prompt.builder import PromptBuilder
                    prompt_builder = PromptBuilder()
                    
                    # 시스템 프롬프트 (ticket_view YAML 템플릿 사용)
                    system_prompt = prompt_builder.build_system_prompt(
                        content_type="ticket_view",
                        content_language="ko",
                        ui_language="ko"
                    )
                    
                    # 티켓 콘텐츠 구성
                    ticket_content = f"""제목: {ticket_data.get('subject', '제목 없음')}
내용: {ticket_data.get('description_text', '내용 없음')}

우선순위: {ticket_data.get('metadata', {}).get('priority', 'Medium')}
상태: {ticket_data.get('metadata', {}).get('status', 'Open')}
카테고리: {ticket_data.get('metadata', {}).get('category', '일반')}"""
                    
                    # 사용자 프롬프트 빌드
                    user_prompt = prompt_builder.build_user_prompt(
                        content=ticket_content,
                        content_type="ticket_view",
                        subject=ticket_data.get('subject', '제목 없음'),
                        metadata={},
                        content_language="ko",
                        ui_language="ko"
                    )
                    
                    self.logger.info("스트리밍 요약에 YAML 템플릿 적용 완료")
                    
                except Exception as e:
                    self.logger.warning(f"YAML 템플릿 로드 실패, 기본 프롬프트 사용: {e}")
                    # 폴백: 간단한 프롬프트
                    system_prompt = """당신은 Freshdesk 티켓 분석 전문가입니다. 
실시간으로 티켓을 분석하여 상담원이 5초 내에 상황을 파악할 수 있도록 도와주세요."""

                    user_prompt = f"""다음 티켓을 분석해 주세요:

제목: {ticket_data.get('subject', '제목 없음')}
내용: {ticket_data.get('description_text', '내용 없음')[:400]}
우선순위: {ticket_data.get('metadata', {}).get('priority', 'Medium')}
상태: {ticket_data.get('metadata', {}).get('status', 'Open')}"""

                async for chunk in llm_manager.stream_generate_for_use_case(
                    use_case="realtime",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=400,  # 테스트에서 최적화된 값
                    temperature=0.1
                ):
                    summary_chunks.append(chunk)
                    yield {"type": "summary_chunk", "content": chunk}
                
                # 스트리밍 완료 후 전체 마크다운 내용 저장
                full_summary = "".join(summary_chunks)
                
                yield {"type": "summary_complete", "summary": full_summary}
            
            # 검색 작업들 (순차 실행으로 단순화)
            search_results = {}
            
            if (include_similar_tickets or include_kb_docs) and (top_k_tickets > 0 or top_k_kb > 0):
                yield {"type": "search_start", "message": "관련 문서 검색 시작..."}
                
                # 검색 쿼리 구성
                search_query = f"{ticket_data.get('subject', '')} {ticket_data.get('description_text', '')}"[:500]
                
                # 하이브리드 검색 실행
                hybrid_results = await hybrid_manager.hybrid_search(
                    query=search_query,
                    tenant_id=tenant_id,
                    platform=platform,
                    top_k=max(top_k_tickets, top_k_kb),
                    doc_types=self._get_doc_types(include_similar_tickets, include_kb_docs),
                    enable_llm_enrichment=False,
                    rerank_results=True,
                    min_similarity=0.6,
                )
                
                # 결과를 기존 형식으로 변환
                unified_search_result = self._convert_to_legacy_format(
                    hybrid_results, 
                    top_k_tickets,
                    top_k_kb,
                    include_similar_tickets,
                    include_kb_docs
                )
                
            
            # 최종 결과 반환
            execution_time = time.time() - start_time
            
            final_result = {
                "type": "final",
                "success": True,
                "execution_time": execution_time,
                "summary": full_summary if include_summary else None,
                **search_results
            }
            
            yield final_result
                
        except Exception as e:
            logger.error(f"스트리밍 하이브리드 검색 실행 실패: {e}")
            yield {
                "type": "error", 
                "message": f"스트리밍 실행 실패: {str(e)}",
                "success": False
            }

    def _get_doc_types(self, include_similar_tickets: bool, include_kb_docs: bool) -> List[str]:
        """문서 타입 리스트 생성"""
        doc_types = []
        if include_similar_tickets:
            doc_types.append("ticket")
        if include_kb_docs:
            doc_types.append("article")  # kb -> article로 수정
        return doc_types or ["ticket", "article"]
    
    def _convert_to_legacy_format(
        self, 
        hybrid_results: Dict[str, Any],
        top_k_tickets: int,
        top_k_kb: int,
        include_similar_tickets: bool,
        include_kb_docs: bool
    ) -> Dict[str, Any]:
        """
        하이브리드 검색 결과를 기존 unified_search 형식으로 변환
        """
        # 하이브리드 검색 결과에서 문서 추출 (안전한 처리)
        documents = hybrid_results.get("documents", [])
        metadatas = hybrid_results.get("metadatas", [])
        distances = hybrid_results.get("distances", [])
        ids = hybrid_results.get("ids", [])
        
        # 안전한 타입 확인 및 변환
        if not isinstance(documents, list):
            documents = []
        if not isinstance(metadatas, list):
            metadatas = []
        if not isinstance(distances, list):
            distances = []
        if not isinstance(ids, list):
            ids = []
        
        # 리스트 길이 통일 (가장 짧은 것에 맞춤)
        min_length = min(len(documents), len(metadatas), len(distances)) if documents and metadatas and distances else 0
        
        self.logger.debug(f"변환할 검색 결과: {min_length}개 문서")
        
        # 문서 타입별로 분리
        similar_tickets = []
        kb_documents = []
        
        for i in range(min_length):
            try:
                # 안전한 인덱스 접근
                doc = documents[i] if i < len(documents) else ""
                metadata = metadatas[i] if i < len(metadatas) else {}
                distance = distances[i] if i < len(distances) else 1.0
                doc_id = ids[i] if i < len(ids) else f"doc_{i}"
                
                # 메타데이터가 딕셔너리가 아닌 경우 처리
                if not isinstance(metadata, dict):
                    metadata = {}
                
                doc_type = metadata.get("source_type", metadata.get("doc_type", "unknown"))
                
                # 기존 형식으로 변환
                doc_item = {
                    "content": str(doc),
                    "metadata": metadata,
                    "distance": float(distance),
                    "id": str(doc_id),
                    "source_type": str(doc_type)
                }
                
                if doc_type == "ticket" and include_similar_tickets and len(similar_tickets) < top_k_tickets:
                    similar_tickets.append(doc_item)
                elif doc_type == "article" and include_kb_docs and len(kb_documents) < top_k_kb:
                    kb_documents.append(doc_item)
                    
            except Exception as e:
                self.logger.warning(f"문서 {i} 처리 중 오류: {e}")
                continue
        
        return {
            "task_type": "unified_search",
            "similar_tickets": similar_tickets,
            "kb_documents": kb_documents,
            "success": True,
            "cache_used": hybrid_results.get("cache_used", False),
            "search_quality_score": hybrid_results.get("search_quality_score", 0.0),
            "total_results": len(documents),
            "performance_metrics": hybrid_results.get("performance_metrics", {})
        }

    async def _generate_fast_json_summary(self, llm_manager, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        빠른 JSON 기반 요약 생성 (기존 요약 기능 활용)
        """
        try:
            # 빠른 JSON 요약을 위한 간소화된 티켓 데이터
            simplified_ticket = {
                "ticket_data": {
                    "id": ticket_data.get("id", "unknown"),
                    "subject": ticket_data.get("subject", "제목 없음")[:100],  # 제목 단축
                    "description_text": ticket_data.get("description_text", "설명 없음")[:200],  # 본문 단축
                    "priority": ticket_data.get("metadata", {}).get("priority", "Medium"),
                    "quick_mode": True  # 빠른 모드 플래그
                }
            }
            
            # 기존 요약 태스크 사용 (내부적으로 최적화됨)
            summary_result = await llm_manager._generate_summary_task(simplified_ticket)
            
            # 요약에서 구조화된 데이터 추출 시도
            if isinstance(summary_result, dict) and summary_result.get("summary"):
                summary_content = summary_result["summary"]
                
                # 마크다운에서 핵심 정보 추출
                subject = ticket_data.get("subject", "티켓 분석")
                
                return {
                    "problem": subject[:50] + ("..." if len(subject) > 50 else ""),
                    "priority": ticket_data.get("metadata", {}).get("priority", "Medium"),
                    "category": "일반",  # 기본값
                    "analysis": "AI가 분석한 티켓 요약입니다.",
                    "actions": ["상세 검토", "담당자 배정", "후속 조치"],
                    "estimated_time": "1-2시간",
                    "original_summary": summary_content  # 원본 요약 보존
                }
            
            # 폴백
            return self._create_fallback_summary(ticket_data)
            
        except Exception as e:
            self.logger.error(f"빠른 JSON 요약 생성 실패: {e}")
            return self._create_fallback_summary(ticket_data)
    
    def _create_fallback_summary(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """폴백 요약 생성"""
        subject = ticket_data.get("subject", "티켓 분석 필요")
        
        return {
            "problem": subject[:50] + ("..." if len(subject) > 50 else ""),
            "priority": ticket_data.get("metadata", {}).get("priority", "Medium"),
            "category": "일반",
            "analysis": "티켓 내용을 검토하고 적절한 조치가 필요합니다.",
            "actions": ["티켓 내용 확인", "담당자 배정", "상태 업데이트"],
            "estimated_time": "1-2시간"
        }
    
    async def _generate_premium_realtime_summary(self, llm_manager, ticket_data: Dict[str, Any]) -> str:
        """
        조회 티켓 최우선 품질: ticket_view 템플릿을 직접 사용한 프리미엄 요약 생성
        """
        try:
            self.logger.info("🎯 [조회 티켓 프리미엄] ticket_view 템플릿 사용 시작")
            from core.llm.summarizer.core.summarizer import core_summarizer
            
            # 티켓 내용 구성
            content = (
                ticket_data.get("description_text") or  # 파싱된 텍스트 우선
                ticket_data.get("description", "")      # HTML 폴백
            )
            
            if not content.strip():
                content = f"제목: {ticket_data.get('subject', '')}\n내용: 상세 내용이 없습니다."
            
            # 메타데이터 구성
            metadata = {
                "status": ticket_data.get("metadata", {}).get("status"),
                "priority": ticket_data.get("metadata", {}).get("priority"),
                "created_at": ticket_data.get("metadata", {}).get("created_at"),
                "company_name": ticket_data.get("metadata", {}).get("company_name"),
                "customer_email": ticket_data.get("metadata", {}).get("customer_email")
            }
            
            # ticket_view 템플릿으로 최고 품질 요약 생성
            self.logger.info(f"📝 [조회 티켓] 콘텐츠 길이: {len(content)} 문자")
            self.logger.info(f"📝 [조회 티켓] 제목: {ticket_data.get('subject', '')[:100]}...")
            
            summary = await core_summarizer.generate_summary(
                content=content,
                content_type="ticket_view",  # 최고 품질 템플릿
                subject=ticket_data.get("subject", ""),
                metadata=metadata,
                ui_language="ko"
            )
            
            # 생성된 요약의 구조 확인
            if summary and len(summary) > 100:
                has_sections = any(section in summary for section in ["🔍 문제 현황", "💡 원인 분석", "⚡ 해결 진행상황", "🎯 중요 인사이트"])
                if not has_sections:
                    self.logger.debug("ticket_view 4개 섹션 구조 검증 실패")
            
            self.logger.info("✅ [조회 티켓] ticket_view 템플릿 기반 프리미엄 요약 생성 완료")
            return summary
            
        except Exception as e:
            self.logger.error(f"프리미엄 요약 생성 실패: {e}")
            # 폴백: 기존 JSON 방식
            json_summary = await self._generate_fast_json_summary(llm_manager, ticket_data)
            return self._json_to_beautiful_markdown_fallback(json_summary)
    
    def _json_to_beautiful_markdown_fallback(self, json_data: Dict[str, Any]) -> str:
        """
        폴백용 마크다운 변환 (기존 로직 유지)
        """
        try:
            # 아이콘 매핑
            priority_icons = {"High": "🔥", "Medium": "⚡", "Low": "📝"}
            category_icons = {"기술": "🔧", "결제": "💳", "일반": "📋", "기타": "❓"}
            
            priority = json_data.get("priority", "Medium")
            category = json_data.get("category", "일반")
            
            # 아름다운 마크다운 템플릿
            markdown = f"""## 🔍 **{json_data.get('problem', '문제 분석 필요')}**

> {priority_icons.get(priority, '📋')} **우선순위**: `{priority}` | {category_icons.get(category, '📋')} **분류**: `{category}` | ⏱️ **예상 시간**: `{json_data.get('estimated_time', '미정')}`

### 📋 **상황 분석**
{json_data.get('analysis', '분석 정보가 없습니다.')}

### 🎯 **권장 조치사항**
{chr(10).join([f"- **{action}**" for action in json_data.get('actions', ['조치사항 없음'])])}

---
*✨ AI 실시간 분석 완료*"""

            return markdown
            
        except Exception as e:
            self.logger.error(f"마크다운 변환 실패: {e}")
            return f"## 🔍 티켓 요약\n\n{json_data.get('problem', '요약 생성 중 오류 발생')}"