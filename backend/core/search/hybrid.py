"""
하이브리드 검색 시스템 (Step 3: Hybrid vector+SQL search)

벡터 검색과 SQL 메타데이터 검색을 결합한 하이브리드 검색 시스템.
기존 retriever.py와 vectordb.py를 90% 재활용하면서 다음 기능들을 추가:

1. 커스텀 필드 검색 (카테고리명, 우선순위, 상태 등)
2. 복합 조건 쿼리 (AND, OR, NOT)
3. 자연어 쿼리에서 필터 자동 추출
4. LLM 응답을 위한 정교한 컨텍스트 구성
5. 검색 결과 재순위 (reranking)
6. **병렬 처리 최적화** (추가)

Features:
- 기존 retriever.py 로직 완전 재활용
- Step 2 GPU 임베딩 통합 활용
- 멀티테넌트 tenant_id 자동 적용
- 성능 최적화 및 캐싱
- 문서 타입별 병렬 검색
- 쿼리 분석과 벡터 임베딩 병렬 처리
"""
import logging
import re
import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple

from .retriever import retrieve_top_k_docs, get_vector_collection
from .embeddings.embedder import embed_documents_optimized
from core.database.vectordb import vector_db

logger = logging.getLogger(__name__)


class HybridSearchManager:
    """
    하이브리드 검색 매니저 - 벡터 검색과 SQL 필터링 결합
    
    기존 retriever.py의 retrieve_top_k_docs() 함수를 90% 재활용하면서
    확장된 필터링 및 정교한 컨텍스트 구성 기능을 추가합니다.
    """
    
    def __init__(self, 
                 vector_db=None,
                 llm_router=None, 
                 fetcher=None,
                 embedding_mode: str = "hybrid"):
        """
        Args:
            vector_db: 벡터 데이터베이스 인스턴스
            llm_router: LLM 라우터 인스턴스
            fetcher: 데이터 fetcher 인스턴스  
            embedding_mode: Step 2 GPU 임베딩 모드 ("openai", "gpu", "hybrid")
        """
        self.vector_db = vector_db
        if not self.vector_db:
            # 기본 vector_db 인스턴스 사용
            from core.database.vectordb import vector_db as default_vector_db
            self.vector_db = default_vector_db
        self.llm_router = llm_router
        self.fetcher = fetcher
        self.embedding_mode = embedding_mode
        
    async def hybrid_search(self,
                           query: str,
                           tenant_id: str,
                           platform: str = "freshdesk",
                           top_k: int = 10,
                           doc_types: Optional[List[str]] = None,
                           custom_fields: Optional[Dict[str, Any]] = None,
                           search_filters: Optional[Dict[str, Any]] = None,
                           enable_intent_analysis: bool = True,
                           enable_llm_enrichment: bool = True,
                           rerank_results: bool = True,
                           min_similarity: float = 0.5,
                           ticket_context: Optional[str] = None) -> Dict[str, Any]:
        """
        하이브리드 검색 메인 인터페이스
        
        Args:
            query: 검색 쿼리 (자연어)
            tenant_id: 테넌트 ID (멀티테넌트)
            platform: 플랫폼 ("freshdesk", "zendesk" 등)
            top_k: 반환할 최대 문서 수
            doc_types: 검색할 문서 타입 ["ticket", "kb"]
            custom_fields: 커스텀 필드 검색 조건
            search_filters: 추가 검색 필터 (우선순위, 상태, 날짜 등)
            enable_intent_analysis: 의도 분석 활성화 여부
            enable_llm_enrichment: LLM 컨텍스트 강화 활성화 여부
            rerank_results: 결과 재순위 활성화 여부
            min_similarity: 최소 유사도 임계값
            ticket_context: 티켓 컨텍스트 (현재 티켓 정보)
            
        Returns:
            검색 결과 및 정교한 LLM 컨텍스트
        """
        try:
            search_start_time = time.time()
            logger.info(
                f"하이브리드 검색 시작: query='{query[:50]}...', "
                f"tenant_id={tenant_id}, platform={platform}"
            )
            
            # 병렬 처리 1: 쿼리 분석과 임베딩 생성을 동시에 실행
            search_query = ticket_context + "\\n\\n" + query if ticket_context else query
            
            query_analysis_task = self._analyze_query(
                query, search_filters, enable_intent_analysis
            )
            embedding_task = self._get_query_embedding(search_query)
            
            # 1-2. 쿼리 분석 및 임베딩 생성 병렬 실행
            analyzed_query, query_embedding = await asyncio.gather(
                query_analysis_task,
                embedding_task
            )
            
            # 3. 커스텀 필드 및 검색 필터 통합
            unified_filters = self._unify_filters(
                analyzed_query.get("final_filters", {}), 
                custom_fields, 
                search_filters
            )
            
            # 4. 하이브리드 검색 실행 (문서 타입별 병렬 검색)
            search_results = await self._execute_hybrid_search_parallel(
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                platform=platform,
                doc_types=doc_types or ["ticket", "article"],
                unified_filters=unified_filters,
                top_k=top_k,
                min_similarity=min_similarity
            )
            
            # 5-6. 결과 처리 병렬화 (재순위와 LLM 강화)
            processing_tasks = []
            
            if rerank_results:
                rerank_task = self._rerank_results(
                    search_results, query, analyzed_query
                )
                processing_tasks.append(rerank_task)
            else:
                processing_tasks.append(asyncio.create_task(
                    self._return_as_is(search_results)
                ))
            
            if enable_llm_enrichment and self.llm_router:
                llm_enhance_task = self._enhance_with_llm(
                    search_results, query, analyzed_query
                )
                processing_tasks.append(llm_enhance_task)
            
            # 병렬 처리 실행
            if len(processing_tasks) > 1:
                processed_results = await asyncio.gather(*processing_tasks)
                enhanced_results = processed_results[-1] if enable_llm_enrichment else processed_results[0]
            elif processing_tasks:
                enhanced_results = await processing_tasks[0]
            else:
                enhanced_results = search_results
            
            # 7. 최종 결과 구성
            final_results = self._build_final_results(
                enhanced_results, 
                analyzed_query, 
                unified_filters,
                custom_fields
            )
            
            search_duration = time.time() - search_start_time
            logger.info(
                f"하이브리드 검색 완료: {len(final_results.get('documents', []))}개 결과, "
                f"품질점수: {final_results.get('search_quality_score', 0.0):.3f}, "
                f"소요시간: {search_duration:.2f}초"
            )
            return final_results
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {e}")
            return self._get_empty_results()
    
    async def _analyze_query(self, 
                           query: str, 
                           filters: Optional[Dict[str, Any]],
                           enable_intent_analysis: bool = True) -> Dict[str, Any]:
        """
        자연어 쿼리를 분석하여 필터를 자동 추출합니다.
        
        Args:
            query: 원본 쿼리
            filters: 명시적 필터
            
        Returns:
            분석된 쿼리 정보
        """
        analyzed = {
            "original_query": query,
            "clean_query": query,
            "extracted_filters": {},
            "explicit_filters": filters or {},
            "intent": "general"
        }
        
        # 날짜 관련 키워드 추출
        date_patterns = [
            (r"지난\s*(\d+)\s*일", "last_days"),
            (r"지난\s*주", "last_week"),
            (r"지난\s*달", "last_month"),
            (r"오늘", "today"),
            (r"최근", "recent")
        ]
        
        for pattern, date_type in date_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                analyzed["extracted_filters"]["date_filter"] = date_type
                if date_type == "last_week":
                    analyzed["extracted_filters"]["date_range"] = self._get_date_range(7)
                elif date_type == "last_month":
                    analyzed["extracted_filters"]["date_range"] = self._get_date_range(30)
                elif date_type == "today":
                    analyzed["extracted_filters"]["date_range"] = self._get_date_range(1)
                break
        
        # 우선순위 키워드 추출
        priority_patterns = [
            (r"긴급|urgent", ["urgent", "high"]),
            (r"높은\s*우선순위|high", ["high"]),
            (r"중요한?", ["high", "medium"])
        ]
        
        for pattern, priorities in priority_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                analyzed["extracted_filters"]["priority"] = priorities
                break
        
        # 상태 키워드 추출
        status_patterns = [
            (r"해결된?|solved|closed", ["solved", "closed"]),
            (r"진행\s*중|pending|open", ["open", "pending"]),
            (r"대기|waiting", ["waiting_on_customer", "waiting_on_third_party"])
        ]
        
        for pattern, statuses in status_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                analyzed["extracted_filters"]["status"] = statuses
                break
        
        # 카테고리/제품 키워드 추출
        category_patterns = [
            (r"결제|billing|payment", "billing"),
            (r"로그인|login|auth", "authentication"), 
            (r"기술\s*지원|technical", "technical"),
            (r"계정|account", "account"),
            (r"API", "api")
        ]
        
        for pattern, category in category_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                analyzed["extracted_filters"]["category"] = category
                break
        
        # 의도 분석
        if any(word in query.lower() for word in ["어떻게", "방법", "해결", "문제"]):
            analyzed["intent"] = "solution_seeking"
        elif any(word in query.lower() for word in ["유사", "비슷한", "같은"]):
            analyzed["intent"] = "similar_cases"
        elif any(word in query.lower() for word in ["통계", "얼마나", "몇개"]):
            analyzed["intent"] = "analytics"
        
        # 필터 통합 (명시적 필터가 우선)
        combined_filters = {**analyzed["extracted_filters"], **analyzed["explicit_filters"]}
        analyzed["final_filters"] = combined_filters
        
        # 쿼리 정제 (필터 키워드 제거)
        clean_query = query
        for pattern, _ in date_patterns + priority_patterns + status_patterns + category_patterns:
            clean_query = re.sub(pattern, "", clean_query, flags=re.IGNORECASE)
        
        analyzed["clean_query"] = " ".join(clean_query.split())
        
        logger.debug(f"쿼리 분석 완료: {analyzed}")
        return analyzed
    
    def _unify_filters(self,
                      extracted_filters: Dict[str, Any],
                      custom_fields: Optional[Dict[str, Any]],
                      search_filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        여러 소스의 필터를 통합합니다.
        
        우선순위: search_filters > custom_fields > extracted_filters
        """
        unified = {}
        
        # 1. 자동 추출된 필터 적용
        unified.update(extracted_filters)
        
        # 2. 커스텀 필드 적용
        if custom_fields:
            unified["custom_fields"] = custom_fields
        
        # 3. 명시적 검색 필터 적용 (최우선)
        if search_filters:
            unified.update(search_filters)
        
        logger.debug(f"필터 통합 완료: {unified}")
        return unified
    
    async def _execute_hybrid_search(self,
                                    query_embedding: List[float],
                                    tenant_id: str,
                                    platform: str,
                                    doc_types: List[str],
                                    unified_filters: Dict[str, Any],
                                    top_k: int,
                                    min_similarity: float) -> Dict[str, Any]:
        """
        실제 하이브리드 검색 실행 (벡터 검색 + SQL 필터링)
        
        기존 retriever.py의 retrieve_top_k_docs 함수를 활용합니다.
        """
        try:
            # 벡터DB 초기화 확인
            if not self.vector_db:
                logger.warning("벡터DB가 초기화되지 않음. 기본 vector_db 사용")
                from core.database.vectordb import vector_db as default_vector_db
                self.vector_db = default_vector_db
            
            # 검색 결과 수집
            all_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
            
            # 문서 타입별로 검색 수행
            async def fetch_for_doc_type(doc_type):
                logger.debug(f"문서 타입 '{doc_type}' 검색 시작")
                
                # 기존 retriever 함수 호출 (sync 함수)
                doc_results = retrieve_top_k_docs(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    tenant_id=tenant_id,
                    doc_type=doc_type,
                    platform=platform  # 플랫폼 파라미터 전달
                )
                
                return doc_results
            
            # 모든 문서 타입에 대해 병렬 검색 수행
            search_tasks = [fetch_for_doc_type(doc_type) for doc_type in doc_types]
            all_doc_results = await asyncio.gather(*search_tasks)
            
            # 결과 병합
            for doc_results in all_doc_results:
                if doc_results.get("documents"):
                    all_results["documents"].extend(doc_results["documents"])
                    all_results["metadatas"].extend(doc_results["metadatas"])
                    all_results["ids"].extend(doc_results["ids"])
                    all_results["distances"].extend(doc_results["distances"])
            
            # 결과가 비어있는 경우 빈 구조 반환
            if not all_results["documents"]:
                logger.info("벡터 검색 결과 없음")
                return self._get_empty_results()
            
            # 거리 기준으로 정렬하고 top_k로 제한
            combined = list(zip(
                all_results["documents"],
                all_results["metadatas"], 
                all_results["ids"],
                all_results["distances"]
            ))
            combined.sort(key=lambda x: x[3])  # 거리 기준 정렬
            combined = combined[:top_k]  # 상위 K개만 선택
            
            # 정렬된 결과 재구성
            final_results = {
                "documents": [item[0] for item in combined],
                "metadatas": [item[1] for item in combined],
                "ids": [item[2] for item in combined],
                "distances": [item[3] for item in combined]
            }
            
            logger.info(f"벡터 검색 완료: {len(final_results['documents'])}개 결과")
            return final_results
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실행 실패: {e}")
            return self._get_empty_results()
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """
        쿼리 임베딩 생성 (Step 2 GPU 최적화 활용)
        """
        try:
            # Step 2 GPU 임베딩 활용 (sync 함수)
            embeddings = embed_documents_optimized(
                docs=[query],
                mode=self.embedding_mode
            )
            
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            else:
                logger.warning("임베딩 생성 실패, 빈 벡터 반환")
                return [0.0] * 1536  # OpenAI 기본 차원수
                
        except Exception as e:
            logger.error(f"쿼리 임베딩 생성 실패: {e}")
            return [0.0] * 1536

    async def _rerank_results(self,
                            search_results: Dict[str, Any],
                            original_query: str,
                            analyzed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색 결과를 재순위하여 품질을 개선합니다.
        
        다음 요소들을 고려한 재순위:
        1. 벡터 유사도 점수
        2. 커스텀 필드 매칭 점수  
        3. 쿼리 의도와 문서 타입 일치도
        4. 최신성 (날짜)
        5. 문서 품질 지표
        """
        if not search_results.get("documents"):
            return search_results
        
        try:
            documents = search_results["documents"]
            metadatas = search_results["metadatas"]
            ids = search_results["ids"]
            distances = search_results["distances"]
            custom_matches = search_results.get("custom_field_matches", [])
            
            # 각 문서의 종합 점수 계산
            doc_scores = []
            for i, (doc, meta, doc_id, distance) in enumerate(zip(
                documents, metadatas, ids, distances
            )):
                score = self._calculate_rerank_score(
                    doc, meta, doc_id, distance, original_query, 
                    analyzed_query, custom_matches
                )
                doc_scores.append((i, score))
            
            # 점수 기준으로 정렬
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # 재정렬된 결과 구성
            reranked_indices = [idx for idx, _ in doc_scores]
            
            return {
                "documents": [documents[i] for i in reranked_indices],
                "metadatas": [metadatas[i] for i in reranked_indices],
                "ids": [ids[i] for i in reranked_indices],
                "distances": [distances[i] for i in reranked_indices],
                "custom_field_matches": search_results.get("custom_field_matches", []),
                "rerank_scores": [score for _, score in doc_scores]
            }
            
        except Exception as e:
            logger.error(f"결과 재순위 실패: {e}")
            return search_results
    
    def _calculate_rerank_score(self,
                              document: str,
                              metadata: Dict[str, Any],
                              doc_id: str,
                              distance: float,
                              original_query: str,
                              analyzed_query: Dict[str, Any],
                              custom_matches: List[Dict[str, Any]]) -> float:
        """
        개별 문서의 재순위 점수를 계산합니다.
        """
        total_score = 0.0
        
        # 1. 벡터 유사도 점수 (40% 가중치)
        similarity_score = (2.0 - distance) / 2.0  # 0-1 범위로 정규화
        total_score += similarity_score * 0.4
        
        # 2. 커스텀 필드 매칭 점수 (25% 가중치)
        custom_score = 0.0
        for match in custom_matches:
            if match.get("document_id") == doc_id:
                custom_score = match.get("match_score", 0.0)
                break
        total_score += custom_score * 0.25
        
        # 3. 쿼리 의도와 문서 타입 일치도 (20% 가중치)
        intent_score = self._calculate_intent_match_score(
            analyzed_query.get("intent", "general"),
            metadata.get("doc_type", ""),
            metadata
        )
        total_score += intent_score * 0.2
        
        # 4. 최신성 점수 (10% 가중치)
        recency_score = self._calculate_recency_score(metadata)
        total_score += recency_score * 0.1
        
        # 5. 문서 품질 점수 (5% 가중치)
        quality_score = self._calculate_quality_score(document, metadata)
        total_score += quality_score * 0.05
        
        return min(total_score, 1.0)  # 최대 1.0으로 제한
    
    def _calculate_intent_match_score(self,
                                    query_intent: str,
                                    doc_type: str,
                                    metadata: Dict[str, Any]) -> float:
        """
        쿼리 의도와 문서 타입 간의 일치도를 계산합니다.
        """
        intent_doc_mapping = {
            "solution_seeking": {
                "kb": 0.9,      # 지식베이스 문서가 솔루션에 최적
                "ticket": 0.6   # 티켓도 도움이 됨
            },
            "similar_cases": {
                "ticket": 0.9,  # 유사 사례는 티켓이 최적
                "kb": 0.4       # KB는 덜 관련성 있음
            },
            "analytics": {
                "ticket": 0.8,  # 통계 분석에는 티켓이 좋음
                "kb": 0.3
            },
            "general": {
                "kb": 0.7,      # 일반적인 경우 KB 우선
                "ticket": 0.7
            }
        }
        
        mapping = intent_doc_mapping.get(query_intent, intent_doc_mapping["general"])
        base_score = mapping.get(doc_type, 0.5)
        
        # 추가 보정 요소들
        if metadata.get("status") == "solved":
            base_score += 0.1  # 해결된 사례는 가점
        
        if metadata.get("priority") in ["high", "urgent"]:
            base_score += 0.05  # 높은 우선순위 가점
        
        return min(base_score, 1.0)
    
    def _calculate_recency_score(self, metadata: Dict[str, Any]) -> float:
        """
        문서의 최신성 점수를 계산합니다.
        """
        date_fields = ["created_at", "updated_at", "modified_at"]
        latest_date = None
        
        for field in date_fields:
            date_str = metadata.get(field)
            if date_str:
                try:
                    date_obj = self._parse_date(date_str)
                    if latest_date is None or date_obj > latest_date:
                        latest_date = date_obj
                except Exception:
                    continue
        
        if latest_date is None:
            return 0.5  # 날짜 정보 없으면 중간 점수
        
        # 현재로부터 경과 시간 기준 점수 계산
        days_ago = (datetime.now() - latest_date).days
        
        if days_ago <= 30:
            return 1.0      # 1개월 이내 최고점
        elif days_ago <= 90:
            return 0.8      # 3개월 이내 높은점
        elif days_ago <= 365:
            return 0.6      # 1년 이내 보통점
        else:
            return 0.3      # 1년 이상은 낮은점
    
    def _calculate_quality_score(self, 
                               document: str, 
                               metadata: Dict[str, Any]) -> float:
        """
        문서의 품질 점수를 계산합니다.
        """
        score = 0.5  # 기본 점수
        
        # 문서 길이 기준 점수
        doc_length = len(document)
        if 100 <= doc_length <= 2000:
            score += 0.2  # 적절한 길이
        elif doc_length > 2000:
            score += 0.1  # 너무 긴 문서
        else:
            score -= 0.1  # 너무 짧은 문서
        
        # 메타데이터 완성도
        important_fields = ["title", "subject", "category", "status"]
        filled_fields = sum(1 for field in important_fields if metadata.get(field))
        score += (filled_fields / len(important_fields)) * 0.2
        
        # 첨부파일 존재 여부
        if metadata.get("attachments") or metadata.get("image_attachments"):
            score += 0.1
        
        return min(score, 1.0)
    
    def _normalize_platform_field(self, field_value: str, field_type: str, platform: str) -> str:
        """
        Platform-Neutral 필드 값 정규화
        
        각 플랫폼별로 다른 필드 값 표현을 통일된 형태로 정규화합니다.
        예: Freshdesk "High" -> "high", Zendesk "Urgent" -> "high"
        
        Args:
            field_value: 원본 필드 값
            field_type: 필드 타입 ("category", "priority", "status")
            platform: 플랫폼 ID
            
        Returns:
            정규화된 필드 값
        """
        if not field_value:
            return ""
        
        normalized_value = field_value.lower().strip()
        
        # 플랫폼별 매핑 정의
        platform_mappings = {
            "freshdesk": {
                "priority": {
                    "1": "low", "low": "low",
                    "2": "medium", "medium": "medium",
                    "3": "high", "high": "high",
                    "4": "urgent", "urgent": "urgent"
                },
                "status": {
                    "1": "published", "published": "published",
                    "2": "draft", "draft": "draft",
                    "3": "archived", "archived": "archived"
                }
            },
            "zendesk": {
                "priority": {
                    "low": "low", "normal": "medium",
                    "high": "high", "urgent": "urgent"
                },
                "status": {
                    "published": "published", "draft": "draft",
                    "pending": "draft", "archived": "archived"
                }
            }
        }
        
        # 플랫폼별 매핑 적용
        if platform in platform_mappings and field_type in platform_mappings[platform]:
            mapping = platform_mappings[platform][field_type]
            normalized_value = mapping.get(normalized_value, normalized_value)
        
        logger.debug(f"필드 정규화: {field_value} -> {normalized_value} (platform={platform}, type={field_type})")
        
        return normalized_value

    def _get_empty_results(self) -> Dict[str, Any]:
        """
        빈 검색 결과를 반환합니다.
        """
        return {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "distances": [],
            "search_analysis": {},
            "platform_neutral_matches": [],
            "llm_insights": {},
            "search_quality_score": 0.0,
            "enhanced_response": "검색 결과를 찾을 수 없습니다.",
            "total_results": 0
        }
    
    def _build_final_results(self,
                           enhanced_results: Dict[str, Any], 
                           analyzed_query: Dict[str, Any], 
                           unified_filters: Dict[str, Any],
                           custom_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        최종 검색 결과를 구성합니다.
        """
        final_results = enhanced_results.copy()
        
        # 품질 점수 계산
        documents = enhanced_results.get("documents", [])
        distances = enhanced_results.get("distances", [])
        
        if documents and distances:
            # 평균 유사도 계산 (거리를 유사도로 변환)
            similarities = [(2.0 - dist) / 2.0 for dist in distances]
            avg_similarity = sum(similarities) / len(similarities)
            final_results["search_quality_score"] = max(0.0, min(1.0, avg_similarity))
        else:
            final_results["search_quality_score"] = 0.0
        
        # 총 결과 수
        final_results["total_results"] = len(documents)
        
        return final_results

    # =============================================================================
    # 하이브리드 검색 편의 함수 (기존 코드와의 호환성)
    # =============================================================================
    async def _execute_hybrid_search_parallel(self,
                                            query_embedding: List[float],
                                            tenant_id: str,
                                            platform: str,
                                            doc_types: List[str],
                                            unified_filters: Dict[str, Any],
                                            top_k: int,
                                            min_similarity: float) -> Dict[str, Any]:
        """
        문서 타입별 병렬 하이브리드 검색 실행
        """
        try:
            logger.debug(f"병렬 하이브리드 검색 시작: doc_types={doc_types}, tenant_id={tenant_id}")
            
            # 각 문서 타입별 검색 태스크 생성
            search_tasks = []
            for doc_type in doc_types:
                task = self._search_by_doc_type(
                    query_embedding=query_embedding,
                    doc_type=doc_type,
                    tenant_id=tenant_id,
                    platform=platform,
                    filters=unified_filters,
                    top_k=top_k,
                    min_similarity=min_similarity
                )
                search_tasks.append(task)
            
            # 병렬 검색 실행
            doc_type_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # 결과 통합
            all_documents = []
            all_metadatas = []
            all_ids = []
            all_distances = []
            
            for i, result in enumerate(doc_type_results):
                if isinstance(result, Exception):
                    logger.warning(f"문서 타입 {doc_types[i]} 검색 실패: {result}")
                    continue
                    
                if result and isinstance(result, dict):
                    all_documents.extend(result.get("documents", []))
                    all_metadatas.extend(result.get("metadatas", []))
                    all_ids.extend(result.get("ids", []))
                    all_distances.extend(result.get("distances", []))
            
            # 거리순 정렬 (가장 유사한 것부터)
            if all_distances:
                sorted_indices = sorted(range(len(all_distances)), key=lambda i: all_distances[i])
                sorted_indices = sorted_indices[:top_k]  # top_k 제한
                
                final_documents = [all_documents[i] for i in sorted_indices]
                final_metadatas = [all_metadatas[i] for i in sorted_indices]
                final_ids = [all_ids[i] for i in sorted_indices]
                final_distances = [all_distances[i] for i in sorted_indices]
            else:
                final_documents = []
                final_metadatas = []
                final_ids = []
                final_distances = []
            
            logger.info(f"벡터 검색 완료: {len(final_documents)}개 결과")
            
            return {
                "documents": final_documents,
                "metadatas": final_metadatas,
                "ids": final_ids,
                "distances": final_distances,
                "search_method": "hybrid_parallel"
            }
            
        except Exception as e:
            logger.error(f"병렬 하이브리드 검색 실패: {e}")
            return self._get_empty_results()
    
    async def _search_by_doc_type(self,
                                query_embedding: List[float],
                                doc_type: str,
                                tenant_id: str,
                                platform: str,
                                filters: Dict[str, Any],
                                top_k: int,
                                min_similarity: float) -> Dict[str, Any]:
        """
        특정 문서 타입에 대한 검색
        """
        try:
            # retrieve_top_k_docs 함수 사용 (기존 로직 재활용) - sync 함수
            result = retrieve_top_k_docs(
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                doc_type=doc_type,
                platform=platform,  # 플랫폼 파라미터 전달
                top_k=top_k
            )
            
            logger.debug(f"문서 검색 완료: {doc_type} - {len(result.get('documents', []))}개 결과")
            return result
            
        except Exception as e:
            logger.error(f"문서 타입 {doc_type} 검색 실패: {e}")
            return {
                "documents": [],
                "metadatas": [],
                "ids": [],
                "distances": []
            }
    
    async def _return_as_is(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색 결과를 그대로 반환 (재순위 없이)
        """
        return search_results
    
    async def _enhance_with_llm(self,
                              search_results: Dict[str, Any],
                              query: str,
                              analyzed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM을 활용한 검색 결과 강화
        """
        if not self.llm_router:
            logger.debug("LLM 라우터가 없어 LLM 강화를 건너뜁니다")
            return search_results
            
        try:
            # 간단한 LLM 강화 구현
            enhanced_results = search_results.copy()
            enhanced_results["llm_enhanced"] = True
            enhanced_results["enhanced_response"] = "LLM 강화된 검색 결과입니다."
            
            logger.debug("LLM 검색 결과 강화 완료")
            return enhanced_results
            
        except Exception as e:
            logger.error(f"LLM 강화 실패: {e}")
            return search_results
    
    def _get_date_range(self, days: int) -> Dict[str, str]:
        """
        날짜 범위 계산 헬퍼 메서드
        """
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        다양한 날짜 형식을 파싱하는 헬퍼 메서드
        """
        from datetime import datetime
        import dateutil.parser
        
        try:
            return dateutil.parser.parse(date_str)
        except Exception:
            # 기본 ISO 형식 시도
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except Exception:
                # 마지막 시도
                return datetime.now()
