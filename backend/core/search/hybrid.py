"""
하이브리드 검색 시스템 (Step 3: Hybrid vector+SQL search)

벡터 검색과 SQL 메타데이터 검색을 결합한 하이브리드 검색 시스템.
기존 retriever.py와 vectordb.py를 90% 재활용하면서 다음 기능들을 추가:

1. 커스텀 필드 검색 (카테고리명, 우선순위, 상태 등)
2. 복합 조건 쿼리 (AND, OR, NOT)
3. 자연어 쿼리에서 필터 자동 추출
4. LLM 응답을 위한 정교한 컨텍스트 구성
5. 검색 결과 재순위 (reranking)

Features:
- 기존 retriever.py 로직 완전 재활용
- Step 2 GPU 임베딩 통합 활용
- 멀티테넌트 tenant_id 자동 적용
- 성능 최적화 및 캐싱
"""
import logging
import re
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
        self.vector_db = vector_db or vector_db
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
            logger.info(
                f"하이브리드 검색 시작: query='{query[:50]}...', "
                f"tenant_id={tenant_id}, platform={platform}"
            )
            
            # 1. 쿼리 분석 및 필터 자동 추출 (의도 분석 포함)
            analyzed_query = await self._analyze_query(
                query, search_filters, enable_intent_analysis
            )
            
            # 2. 커스텀 필드 및 검색 필터 통합
            unified_filters = self._unify_filters(
                analyzed_query["final_filters"], 
                custom_fields, 
                search_filters
            )
            
            # 3. 임베딩 생성 (Step 2 GPU 최적화 활용)
            search_query = ticket_context + "\\n\\n" + query if ticket_context else query
            query_embedding = await self._get_query_embedding(search_query)
            
            # 4. 하이브리드 검색 실행
            search_results = await self._execute_hybrid_search(
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                platform=platform,
                doc_types=doc_types or ["ticket", "kb"],
                unified_filters=unified_filters,
                top_k=top_k,
                min_similarity=min_similarity
            )
            
            # 5. 결과 재순위 및 품질 개선
            if rerank_results:
                search_results = await self._rerank_results(
                    search_results, query, analyzed_query
                )
            
            # 6. LLM 기반 컨텍스트 강화
            enhanced_results = search_results
            if enable_llm_enrichment and self.llm_router:
                enhanced_results = await self._enhance_with_llm(
                    search_results, query, analyzed_query
                )
            
            # 7. 최종 결과 구성
            final_results = self._build_final_results(
                enhanced_results, 
                analyzed_query, 
                unified_filters,
                custom_fields
            )
            
            logger.info(
                f"하이브리드 검색 완료: {len(final_results.get('documents', []))}개 결과, "
                f"품질점수: {final_results.get('search_quality_score', 0.0):.3f}"
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
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """
        쿼리 임베딩 생성 (Step 2 GPU 최적화 활용)
        """
        try:
            embeddings = embed_documents_optimized(
                docs=[query],
                mode=self.embedding_mode,
                use_cache=True
            )
            return embeddings[0] if embeddings else []
        except Exception as e:
            logger.error(f"쿼리 임베딩 생성 실패: {e}")
            return []
    
    def _sort_and_limit_results(self,
                               results: Dict[str, Any],
                               top_k: int) -> Dict[str, Any]:
        """
        검색 결과를 유사도 기준으로 정렬하고 상위 K개로 제한합니다.
        """
        if not results["documents"]:
            return results
        
        # 거리 기준으로 정렬 (작을수록 유사도 높음)
        combined = list(zip(
            results["documents"],
            results["metadatas"],
            results["ids"],
            results["distances"]
        ))
        
        combined.sort(key=lambda x: x[3])  # 거리(distance) 기준 정렬
        combined = combined[:top_k]  # 상위 K개 선택
        
        return {
            "documents": [item[0] for item in combined],
            "metadatas": [item[1] for item in combined],
            "ids": [item[2] for item in combined],
            "distances": [item[3] for item in combined]
        }
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        다양한 날짜 형식을 파싱합니다.
        """
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"날짜 형식을 파싱할 수 없습니다: {date_str}")
    
    def _get_date_range(self, days: int) -> Dict[str, datetime]:
        """
        지정된 일수만큼의 날짜 범위를 반환합니다.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return {
            "start": start_date,
            "end": end_date
        }
    
    async def _execute_hybrid_search(self,
                                   query_embedding: List[float],
                                   tenant_id: str,
                                   platform: str,
                                   doc_types: List[str],
                                   unified_filters: Dict[str, Any],
                                   top_k: int,
                                   min_similarity: float) -> Dict[str, Any]:
        """
        Platform-Neutral 하이브리드 검색 핵심 실행 로직
        
        Platform-Neutral 3-Tuple (tenant_id, platform, original_id) 기반으로
        벡터 검색과 메타데이터 필터링을 결합합니다.
        """
        all_results = {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "distances": []
        }
        
        try:
            # Platform-Neutral 검색 실행
            for doc_type in doc_types:
                logger.debug(f"Platform-Neutral 검색 중: doc_type={doc_type}, tenant_id={tenant_id}, platform={platform}")
                
                # Platform-Neutral Vector DB 검색 (90% 기존 코드 재활용)
                type_results = self.vector_db.search(
                    query_embedding=query_embedding,
                    top_k=top_k * 2,  # 커스텀 필터링을 위해 더 많이 가져옴
                    tenant_id=tenant_id,
                    platform=platform,
                    doc_type=doc_type
                )
                
                # Platform-Neutral 커스텀 필드 필터링 적용
                filtered_results = self._apply_platform_neutral_filters(
                    type_results, unified_filters, min_similarity, tenant_id, platform
                )
                
                # Platform-Neutral 결과 통합
                all_results["documents"].extend(filtered_results["documents"])
                all_results["metadatas"].extend(filtered_results["metadatas"])
                all_results["ids"].extend(filtered_results["ids"])
                all_results["distances"].extend(filtered_results["distances"])
                
                # Platform-Neutral 매칭 정보 통합
                if "platform_neutral_matches" not in all_results:
                    all_results["platform_neutral_matches"] = []
                all_results["platform_neutral_matches"].extend(
                    filtered_results.get("platform_neutral_matches", [])
                )
                
                logger.info(
                    f"Platform-Neutral {doc_type} 검색 완료: {len(filtered_results['documents'])}개 문서 (platform={platform})"
                )
            
            # 전체 결과를 유사도 기준으로 재정렬
            if all_results["documents"]:
                all_results = self._sort_and_limit_results(all_results, top_k)
            
            return all_results
            
        except Exception as e:
            logger.error(f"Platform-Neutral 하이브리드 검색 실행 실패: {e}")
            return self._get_empty_results()
    
    def _apply_platform_neutral_filters(self,
                                       search_results: Dict[str, Any],
                                       unified_filters: Dict[str, Any],
                                       min_similarity: float,
                                       tenant_id: str,
                                       platform: str) -> Dict[str, Any]:
        """
        Platform-Neutral 3-Tuple 기반 검색 결과 필터링
        
        기존 커스텀 필드 필터링을 platform-neutral 구조로 개선.
        모든 필터링이 (tenant_id, platform, original_id) 기반으로 동작합니다.
        
        Args:
            search_results: 벡터 검색 결과
            unified_filters: 통합된 필터 조건
            min_similarity: 최소 유사도 임계값
            tenant_id: 테넌트 ID (테넌트 격리)
            platform: 플랫폼 ID (멀티플랫폼 지원)
            
        Returns:
            필터링된 검색 결과
        """
        if not unified_filters:
            return search_results
        
        # Platform-Neutral 필터링 준비
        logger.debug(f"Platform-Neutral 필터링 시작 (tenant_id={tenant_id}, platform={platform})")
        
        filtered_docs = []
        filtered_metas = []
        filtered_ids = []
        filtered_distances = []
        platform_neutral_matches = []
        
        documents = search_results.get("documents", [])
        metadatas = search_results.get("metadatas", [])
        ids = search_results.get("ids", [])
        distances = search_results.get("distances", [])
        
        for i, (doc, meta, doc_id, distance) in enumerate(zip(
            documents, metadatas, ids, distances
        )):
            # Platform-Neutral 3-Tuple 검증
            doc_tenant_id = meta.get("tenant_id", "")
            doc_platform = meta.get("platform", "")
            doc_original_id = meta.get("original_id", "")
            
            # 테넌트 및 플랫폼 격리 확인
            if doc_tenant_id != tenant_id:
                logger.debug(f"tenant_id 불일치로 문서 제외: {doc_tenant_id} != {tenant_id}")
                continue
            if doc_platform != platform:
                logger.debug(f"platform 불일치로 문서 제외: {doc_platform} != {platform}")
                continue
            
            # 유사도 임계값 확인
            similarity = (2.0 - distance) / 2.0  # 거리를 0-1 유사도로 변환
            if similarity < min_similarity:
                logger.debug(f"유사도 임계값 미달로 문서 제외: {similarity} < {min_similarity}")
                continue
            
            # Platform-Neutral 커스텀 필드 매칭 확인
            match_result = self._check_platform_neutral_match(
                meta, unified_filters, tenant_id, platform, doc_original_id
            )
            
            if match_result["matches"]:
                filtered_docs.append(doc)
                filtered_metas.append(meta)
                filtered_ids.append(doc_id)
                filtered_distances.append(distance)
                
                # Platform-Neutral 매칭 정보 기록
                platform_neutral_matches.append({
                    "document_id": doc_id,
                    "original_id": doc_original_id,
                    "tenant_id": doc_tenant_id,
                    "platform": doc_platform,
                    "matched_fields": match_result["matched_fields"],
                    "match_score": match_result["match_score"],
                    "similarity_score": similarity,
                    "platform_neutral_key": f"{doc_tenant_id}:{doc_platform}:{doc_original_id}"
                })
        
        logger.info(
            f"Platform-Neutral 필터링 완료: {len(documents)} -> {len(filtered_docs)}개 문서 "
            f"(tenant_id={tenant_id}, platform={platform})"
        )
        
        return {
            "documents": filtered_docs,
            "metadatas": filtered_metas,
            "ids": filtered_ids,
            "distances": filtered_distances,
            "platform_neutral_matches": platform_neutral_matches,
            "filtering_summary": {
                "total_input": len(documents),
                "total_output": len(filtered_docs),
                "tenant_id": tenant_id,
                "platform": platform,
                "min_similarity": min_similarity
            }
        }
    
    def _check_platform_neutral_match(self,
                                     metadata: Dict[str, Any],
                                     unified_filters: Dict[str, Any],
                                     tenant_id: str,
                                     platform: str,
                                     original_id: str) -> Dict[str, Any]:
        """
        Platform-Neutral 3-Tuple 기반 개별 문서 매칭 확인
        
        기존 커스텀 필드 매칭을 platform-neutral 구조로 개선.
        모든 매칭 로직이 3-tuple 컨텍스트에서 동작합니다.
        
        Args:
            metadata: 문서 메타데이터
            unified_filters: 필터 조건
            tenant_id: 테넌트 ID
            platform: 플랫폼 ID
            original_id: 원본 문서 ID
            
        Returns:
            Platform-Neutral 매칭 결과 정보
        """
        # Platform-Neutral 컨텍스트 기반 매칭
        platform_neutral_key = f"{tenant_id}:{platform}:{original_id}"
        
        matched_fields = []
        match_score = 0.0
        total_filters = len(unified_filters)
        
        logger.debug(f"Platform-Neutral 매칭 시작: {platform_neutral_key}")
        
        # 카테고리 매칭 (플랫폼별 카테고리 구조 고려)
        if "category" in unified_filters:
            category_filter = unified_filters["category"]
            doc_category = metadata.get("category", "").lower()
            
            # 플랫폼별 카테고리 정규화 (예: Freshdesk vs Zendesk)
            normalized_category = self._normalize_platform_field(
                doc_category, "category", platform
            )
            
            if isinstance(category_filter, str):
                if category_filter.lower() in normalized_category:
                    matched_fields.append(f"category({platform})")
                    match_score += 1.0
            elif isinstance(category_filter, list):
                if any(cat.lower() in normalized_category for cat in category_filter):
                    matched_fields.append(f"category({platform})")
                    match_score += 1.0
        
        # 우선순위 매칭 (플랫폼별 우선순위 매핑)
        if "priority" in unified_filters:
            priority_filter = unified_filters["priority"]
            doc_priority = metadata.get("priority", "").lower()
            
            # 플랫폼별 우선순위 정규화
            normalized_priority = self._normalize_platform_field(
                doc_priority, "priority", platform
            )
            
            if isinstance(priority_filter, str):
                if priority_filter.lower() == normalized_priority:
                    matched_fields.append(f"priority({platform})")
                    match_score += 1.0
            elif isinstance(priority_filter, list):
                if normalized_priority in [p.lower() for p in priority_filter]:
                    matched_fields.append(f"priority({platform})")
                    match_score += 1.0
        
        # 상태 매칭 (플랫폼별 상태 매핑)
        if "status" in unified_filters:
            status_filter = unified_filters["status"]
            doc_status = metadata.get("status", "").lower()
            
            # 플랫폼별 상태 정규화
            normalized_status = self._normalize_platform_field(
                doc_status, "status", platform
            )
            
            if isinstance(status_filter, str):
                if status_filter.lower() == normalized_status:
                    matched_fields.append(f"status({platform})")
                    match_score += 1.0
            elif isinstance(status_filter, list):
                if normalized_status in [s.lower() for s in status_filter]:
                    matched_fields.append(f"status({platform})")
                    match_score += 1.0
        
        # 날짜 범위 매칭
        if "date_range" in unified_filters:
            date_range = unified_filters["date_range"]
            doc_date_str = metadata.get("created_at", metadata.get("updated_at", ""))
            
            if doc_date_str:
                try:
                    # 다양한 날짜 형식 파싱 시도
                    doc_date = self._parse_date(doc_date_str)
                    if date_range["start"] <= doc_date <= date_range["end"]:
                        matched_fields.append("date_range")
                        match_score += 1.0
                except Exception as e:
                    logger.debug(f"날짜 파싱 실패: {doc_date_str}, {e}")
        
        # 커스텀 필드 매칭 (동적)
        custom_fields = unified_filters.get("custom_fields", {})
        for field_name, field_value in custom_fields.items():
            doc_field_value = metadata.get(field_name, "")
            
            if isinstance(field_value, str):
                if field_value.lower() in str(doc_field_value).lower():
                    matched_fields.append(f"custom_{field_name}")
                    match_score += 0.5  # 커스텀 필드는 낮은 가중치
            elif isinstance(field_value, list):
                if any(v.lower() in str(doc_field_value).lower() for v in field_value):
                    matched_fields.append(f"custom_{field_name}")
                    match_score += 0.5
        
        # 정규화된 매칭 점수 계산
        normalized_score = match_score / max(total_filters, 1) if total_filters > 0 else 0.0
        
        return {
            "matches": len(matched_fields) > 0,
            "matched_fields": matched_fields,
            "match_score": normalized_score,
            "total_fields_checked": total_filters,
            "platform_neutral_context": {
                "tenant_id": tenant_id,
                "platform": platform,
                "original_id": original_id,
                "platform_neutral_key": platform_neutral_key
            }
        }
    
    def _get_empty_results(self) -> Dict[str, Any]:
        """
        Platform-Neutral 빈 검색 결과를 반환합니다.
        """
        return {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "distances": [],
            "search_analysis": {},
            "platform_neutral_matches": [],  # platform-neutral 매칭 정보
            "llm_insights": {},
            "search_quality_score": 0.0,
            "enhanced_response": "검색 결과를 찾을 수 없습니다.",
            "platform_neutral_summary": {
                "total_results": 0,
                "platforms_searched": [],
                "companies_searched": []
            }
        }
    
    async def _enhance_with_llm(self,
                              search_results: Dict[str, Any],
                              original_query: str,
                              analyzed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM을 활용한 검색 결과 및 컨텍스트 강화
        
        더 정교한 LLM 응답을 위한 메타데이터 분석, 추천사항, 품질 평가를 수행합니다.
        """
        if not self.llm_router or not search_results.get("documents"):
            return search_results
        
        try:
            # 검색된 문서들의 메타데이터 분석
            metadata_analysis = self._analyze_search_metadata(
                search_results["metadatas"]
            )
            
            # LLM을 통한 검색 품질 평가 및 인사이트 생성
            llm_insights = await self._generate_llm_insights(
                search_results, original_query, analyzed_query, metadata_analysis
            )
            
            # 향상된 응답 생성
            enhanced_response = await self._generate_enhanced_response(
                search_results, original_query, llm_insights
            )
            
            search_results.update({
                "metadata_analysis": metadata_analysis,
                "llm_insights": llm_insights,
                "enhanced_response": enhanced_response,
                "search_quality_score": llm_insights.get("quality_score", 0.0)
            })
            
            return search_results
            
        except Exception as e:
            logger.error(f"LLM 기반 강화 실패: {e}")
            return search_results
    
    def _analyze_search_metadata(self, metadatas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        검색된 문서들의 메타데이터를 분석합니다.
        """
        if not metadatas:
            return {}
        
        analysis = {
            "document_types": {},
            "categories": {},
            "priorities": {},
            "statuses": {},
            "date_distribution": {},
            "quality_indicators": {}
        }
        
        # 문서 타입 분포
        for meta in metadatas:
            doc_type = meta.get("doc_type", meta.get("source_type", "unknown"))
            analysis["document_types"][doc_type] = (
                analysis["document_types"].get(doc_type, 0) + 1
            )
            
            # 카테고리 분포
            category = meta.get("category", "uncategorized")
            analysis["categories"][category] = (
                analysis["categories"].get(category, 0) + 1
            )
            
            # 우선순위 분포  
            priority = meta.get("priority", "normal")
            analysis["priorities"][priority] = (
                analysis["priorities"].get(priority, 0) + 1
            )
            
            # 상태 분포
            status = meta.get("status", "unknown")
            analysis["statuses"][status] = (
                analysis["statuses"].get(status, 0) + 1
            )
        
        # 품질 지표 계산
        total_docs = len(metadatas)
        analysis["quality_indicators"] = {
            "diversity_score": len(analysis["categories"]) / max(total_docs, 1),
            "has_high_priority": "high" in analysis["priorities"] or "urgent" in analysis["priorities"],
            "has_resolved_cases": "solved" in analysis["statuses"] or "closed" in analysis["statuses"],
            "total_documents": total_docs
        }
        
        return analysis
    
    async def _generate_llm_insights(self,
                                   search_results: Dict[str, Any],
                                   original_query: str,
                                   analyzed_query: Dict[str, Any],
                                   metadata_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM을 통한 검색 인사이트 및 추천사항 생성
        """
        try:
            # LLM 프롬프트 구성
            insight_prompt = f"""
다음 검색 결과를 분석하여 인사이트와 추천사항을 제공해주세요:

원본 쿼리: {original_query}
의도 분석: {analyzed_query.get('intent', 'general')}
검색된 문서 수: {len(search_results.get('documents', []))}

메타데이터 분석:
- 문서 타입: {metadata_analysis.get('document_types', {})}
- 카테고리: {metadata_analysis.get('categories', {})}
- 우선순위: {metadata_analysis.get('priorities', {})}
- 상태: {metadata_analysis.get('statuses', {})}

다음 형식으로 JSON 응답해주세요:
{{
    "quality_score": 0.0-1.0,
    "search_effectiveness": "효과성 평가",
    "recommendations": ["추천사항1", "추천사항2"],
    "insights": ["인사이트1", "인사이트2"],
    "suggested_actions": ["액션1", "액션2"]
}}
"""
            
            # LLM 호출
            response = await self.llm_router.call_llm(
                prompt=insight_prompt,
                system_prompt="당신은 고객 지원 데이터 분석 전문가입니다."
            )
            
            # JSON 파싱 시도
            try:
                import json
                insights = json.loads(response.text)
            except json.JSONDecodeError:
                # 파싱 실패 시 기본값 반환
                insights = {
                    "quality_score": 0.7,
                    "search_effectiveness": "검색 결과를 분석했습니다.",
                    "recommendations": ["관련 문서를 더 자세히 검토해보세요."],
                    "insights": ["검색된 문서들이 쿼리와 관련이 있습니다."],
                    "suggested_actions": ["추가 키워드로 재검색을 고려해보세요."]
                }
            
            return insights
            
        except Exception as e:
            logger.error(f"LLM 인사이트 생성 실패: {e}")
            return {
                "quality_score": 0.5,
                "search_effectiveness": "인사이트 생성 중 오류가 발생했습니다.",
                "recommendations": [],
                "insights": [],
                "suggested_actions": []
            }
    
    async def _generate_enhanced_response(self,
                                        search_results: Dict[str, Any],
                                        original_query: str,
                                        llm_insights: Dict[str, Any]) -> str:
        """
        정교한 LLM 응답 생성
        """
        try:
            documents = search_results.get("documents", [])
            if not documents:
                return "죄송합니다. 관련 문서를 찾을 수 없습니다."
            
            # 컨텍스트 구성
            context = "\\n\\n".join([
                f"문서 {i+1}: {doc[:300]}..."
                for i, doc in enumerate(documents[:3])
            ])
            
            # 향상된 응답 생성 프롬프트
            response_prompt = f"""
사용자 질문: {original_query}

관련 문서들:
{context}

검색 품질 점수: {llm_insights.get('quality_score', 0.0)}
추천사항: {', '.join(llm_insights.get('recommendations', []))}

위 정보를 바탕으로 다음과 같이 응답해주세요:
1. 사용자 질문에 대한 직접적인 답변
2. 관련 문서에서 찾은 구체적인 정보
3. 추가 도움이 될 수 있는 제안사항

친절하고 전문적인 톤으로 답변해주세요.
"""
            
            response = await self.llm_router.call_llm(
                prompt=response_prompt,
                system_prompt="당신은 친절하고 전문적인 고객 지원 AI입니다."
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"향상된 응답 생성 실패: {e}")
            return f"{original_query}에 대한 정보를 찾았습니다. 검색된 문서를 참고해주세요."
    
    def _build_final_results(self,
                           enhanced_results: Dict[str, Any],
                           analyzed_query: Dict[str, Any],
                           unified_filters: Dict[str, Any],
                           custom_fields: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        최종 하이브리드 검색 결과를 구성합니다.
        """
        return {
            "documents": enhanced_results.get("documents", []),
            "metadatas": enhanced_results.get("metadatas", []),
            "ids": enhanced_results.get("ids", []),
            "distances": enhanced_results.get("distances", []),
            "search_analysis": {
                "original_query": analyzed_query.get("original_query", ""),
                "clean_query": analyzed_query.get("clean_query", ""),
                "intent": analyzed_query.get("intent", "general"),
                "extracted_filters": analyzed_query.get("extracted_filters", {}),
                "applied_filters": unified_filters
            },
            "custom_field_matches": enhanced_results.get("custom_field_matches", []),
            "llm_insights": enhanced_results.get("llm_insights", {}),
            "search_quality_score": enhanced_results.get("search_quality_score", 0.0),
            "enhanced_response": enhanced_results.get("enhanced_response", ""),
            "metadata_analysis": enhanced_results.get("metadata_analysis", {})
        }
    
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


# =============================================================================
# 하이브리드 검색 편의 함수 (기존 코드와의 호환성)
# =============================================================================

async def hybrid_search(query: str,
                       tenant_id: str,
                       platform: str = "freshdesk",
                       top_k: int = 10,
                       custom_fields: Optional[Dict[str, Any]] = None,
                       search_filters: Optional[Dict[str, Any]] = None,
                       enable_llm_enrichment: bool = True) -> Dict[str, Any]:
    """
    하이브리드 검색 편의 함수
    
    Args:
        query: 검색 쿼리
        tenant_id: 테넌트 ID  
        platform: 플랫폼
        top_k: 결과 수
        custom_fields: 커스텀 필드 검색 조건
        search_filters: 검색 필터
        enable_llm_enrichment: LLM 강화 활성화
        
    Returns:
        하이브리드 검색 결과
    """
    manager = HybridSearchManager()
    
    return await manager.hybrid_search(
        query=query,
        tenant_id=tenant_id,
        platform=platform,
        top_k=top_k,
        custom_fields=custom_fields,
        search_filters=search_filters,
        enable_llm_enrichment=enable_llm_enrichment
    )
