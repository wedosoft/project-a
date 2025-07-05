"""
고급 자연어 검색 엔진

첨부파일 검색, 카테고리별 검색, 문제 해결 중심 검색을 지원하는 통합 검색 모듈입니다.
상담원이 자연어로 구체적인 요구사항을 표현하면 이를 정확한 검색 조건으로 변환합니다.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.search.embeddings.embedder import embed_documents_optimized
from core.llm.manager import LLMManager
from core.llm.models.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class EnhancedSearchContext:
    """고급 검색 컨텍스트"""
    search_type: str  # attachment, category, solution, general
    intent: str
    keywords: List[str]
    filters: Dict[str, Any]
    attachment_filters: Optional[Dict[str, Any]] = None
    category_hints: Optional[List[str]] = None
    solution_requirements: Optional[Dict[str, Any]] = None


class EnhancedSearchEngine:
    """
    고급 자연어 검색 엔진
    
    지원 기능:
    1. 첨부파일 전용 검색 - "엑셀 파일", "PDF 문서", "스크린샷" 등
    2. 카테고리별 검색 - "결제 관련", "로그인 문제", "API 오류" 등  
    3. 문제 해결 검색 - "이런 오류 해결방법", "비슷한 케이스" 등
    4. 복합 조건 검색 - "긴급한 결제 문제의 첨부파일" 등
    """
    
    def __init__(self, vector_db=None, llm_manager: Optional[LLMManager] = None):
        self.vector_db = vector_db
        self.llm_manager = llm_manager
        
        # 첨부파일 검색 패턴 정의
        self.attachment_patterns = {
            "file_types": {
                r"엑셀|xlsx?|spreadsheet": {"content_types": ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]},
                r"PDF|pdf": {"content_types": ["application/pdf"]},
                r"이미지|스크린샷|screenshot|png|jpg|jpeg": {"content_types": ["image/png", "image/jpeg", "image/gif"]},
                r"워드|docx?|문서": {"content_types": ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]},
                r"압축|zip|rar": {"content_types": ["application/zip", "application/x-rar"]},
                r"텍스트|txt": {"content_types": ["text/plain"]},
                r"로그|log": {"content_types": ["text/plain"], "name_patterns": [r"\.log$", r"error", r"debug"]}
            },
            "size_filters": {
                r"큰\s*파일|대용량": {"min_size": 5 * 1024 * 1024},  # 5MB 이상
                r"작은\s*파일": {"max_size": 1 * 1024 * 1024},  # 1MB 이하
            },
            "source_filters": {
                r"인라인|embedded": {"attachment_types": ["inline"]},
                r"첨부파일|attachment": {"attachment_types": ["attachment"]},
                r"대화|conversation": {"source_location": "conversation"},
                r"티켓|ticket": {"source_location": "ticket_description"}
            }
        }
        
        # 카테고리 분류 패턴
        self.category_patterns = {
            "결제": ["결제", "billing", "payment", "요금", "청구", "환불", "refund"],
            "로그인": ["로그인", "login", "auth", "인증", "계정", "account", "비밀번호", "password"],
            "API": ["API", "연동", "integration", "endpoint", "토큰", "token"],
            "기술지원": ["오류", "error", "버그", "bug", "문제", "issue", "기술", "technical"],
            "네트워크": ["연결", "connection", "네트워크", "network", "인터넷", "속도"],
            "보안": ["보안", "security", "해킹", "악성", "바이러스", "virus"],
            "사용법": ["사용법", "how to", "가이드", "guide", "튜토리얼", "tutorial"],
            "설정": ["설정", "config", "configuration", "옵션", "option"]
        }
        
        # 문제 해결 패턴
        self.solution_patterns = {
            "해결책": ["해결", "solution", "fix", "방법", "how", "어떻게"],
            "유사사례": ["비슷한", "similar", "같은", "동일한", "케이스", "case"],
            "단계별": ["단계", "step", "순서", "order", "절차", "procedure"],
            "예시": ["예시", "example", "샘플", "sample", "예제"]
        }
        
        logger.info("EnhancedSearchEngine 초기화 완료")
    
    async def analyze_enhanced_query(self, query: str) -> EnhancedSearchContext:
        """
        자연어 쿼리를 분석하여 고급 검색 컨텍스트 생성
        
        Args:
            query: 사용자의 자연어 쿼리
            
        Returns:
            EnhancedSearchContext: 분석된 검색 컨텍스트
        """
        try:
            logger.info(f"고급 쿼리 분석 시작: '{query[:50]}...'")
            
            # 1. 검색 타입 결정
            search_type = self._determine_search_type(query)
            
            # 2. 기본 키워드 추출
            keywords = self._extract_keywords(query)
            
            # 3. 타입별 특화 분석
            filters = {}
            attachment_filters = None
            category_hints = None
            solution_requirements = None
            
            if search_type == "attachment":
                attachment_filters = self._analyze_attachment_requirements(query)
                filters.update({"has_attachments": True})
            elif search_type == "category":
                category_hints = self._analyze_category_hints(query)
            elif search_type == "solution":
                solution_requirements = self._analyze_solution_requirements(query)
            
            # 4. 공통 필터 추출
            common_filters = self._extract_common_filters(query)
            filters.update(common_filters)
            
            # 5. 의도 분석 (기존 로직 활용)
            intent = self._classify_intent(query)
            
            context = EnhancedSearchContext(
                search_type=search_type,
                intent=intent,
                keywords=keywords,
                filters=filters,
                attachment_filters=attachment_filters,
                category_hints=category_hints,
                solution_requirements=solution_requirements
            )
            
            logger.info(f"고급 쿼리 분석 완료: search_type={search_type}, intent={intent}")
            return context
            
        except Exception as e:
            logger.error(f"고급 쿼리 분석 실패: {e}")
            # 기본 컨텍스트 반환
            return EnhancedSearchContext(
                search_type="general",
                intent="general",
                keywords=[query],
                filters={}
            )
    
    def _determine_search_type(self, query: str) -> str:
        """쿼리의 검색 타입을 결정"""
        query_lower = query.lower()
        
        # 첨부파일 검색 감지
        attachment_indicators = [
            "첨부파일", "파일", "attachment", "이미지", "스크린샷", "문서", 
            "엑셀", "pdf", "워드", "압축", "로그", "다운로드"
        ]
        if any(indicator in query_lower for indicator in attachment_indicators):
            return "attachment"
        
        # 카테고리 검색 감지
        category_indicators = [
            "카테고리", "분류", "종류", "유형", "관련", "문제", "오류"
        ]
        # 카테고리 키워드가 있으면서 구체적인 분야가 언급된 경우
        if any(indicator in query_lower for indicator in category_indicators):
            for category in self.category_patterns.keys():
                if any(keyword in query_lower for keyword in self.category_patterns[category]):
                    return "category"
        
        # 문제 해결 검색 감지
        solution_indicators = [
            "해결", "방법", "어떻게", "단계", "가이드", "해결책", "비슷한", "케이스"
        ]
        if any(indicator in query_lower for indicator in solution_indicators):
            return "solution"
        
        return "general"
    
    def _analyze_attachment_requirements(self, query: str) -> Dict[str, Any]:
        """첨부파일 검색 요구사항 분석"""
        requirements = {}
        query_lower = query.lower()
        
        # 파일 타입 필터
        for pattern, filter_data in self.attachment_patterns["file_types"].items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                requirements.update(filter_data)
                break
        
        # 크기 필터
        for pattern, filter_data in self.attachment_patterns["size_filters"].items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                requirements.update(filter_data)
                break
        
        # 소스 필터
        for pattern, filter_data in self.attachment_patterns["source_filters"].items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                requirements.update(filter_data)
                break
        
        logger.info(f"첨부파일 요구사항 분석: {requirements}")
        return requirements
    
    def _analyze_category_hints(self, query: str) -> List[str]:
        """카테고리 힌트 분석"""
        hints = []
        query_lower = query.lower()
        
        for category, keywords in self.category_patterns.items():
            if any(keyword in query_lower for keyword in keywords):
                hints.append(category)
        
        logger.info(f"카테고리 힌트: {hints}")
        return hints
    
    def _analyze_solution_requirements(self, query: str) -> Dict[str, Any]:
        """문제 해결 요구사항 분석"""
        requirements = {}
        query_lower = query.lower()
        
        for req_type, keywords in self.solution_patterns.items():
            if any(keyword in query_lower for keyword in keywords):
                requirements[req_type] = True
        
        logger.info(f"해결책 요구사항: {requirements}")
        return requirements
    
    def _extract_keywords(self, query: str) -> List[str]:
        """키워드 추출 (기존 로직 개선)"""
        # 기본 키워드 추출
        keywords = []
        
        # 단어 단위 분리
        words = re.findall(r'\b\w+\b', query)
        
        # 불용어 제거
        stop_words = {
            "의", "가", "이", "은", "는", "을", "를", "에", "에서", "로", "으로",
            "와", "과", "그리고", "또는", "하지만", "그러나", "그래서", "따라서",
            "찾아", "보여", "알려", "해줘", "주세요", "어떤", "무엇", "언제", "어디서"
        }
        
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        # 복합어 추출
        compound_patterns = [
            r"API\s*오류", r"로그인\s*문제", r"결제\s*오류", 
            r"네트워크\s*연결", r"데이터베이스\s*오류"
        ]
        
        for pattern in compound_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            keywords.extend(matches)
        
        return keywords[:15]  # 최대 15개
    
    def _extract_common_filters(self, query: str) -> Dict[str, Any]:
        """공통 필터 추출"""
        filters = {}
        query_lower = query.lower()
        
        # 날짜 필터
        if "오늘" in query_lower:
            filters["date_range"] = self._get_date_range(1)
        elif "이번 주" in query_lower or "지난 주" in query_lower:
            filters["date_range"] = self._get_date_range(7)
        elif "최근" in query_lower:
            filters["date_range"] = self._get_date_range(7)
        
        # 우선순위 필터
        if any(word in query_lower for word in ["긴급", "urgent", "중요"]):
            filters["priority"] = ["high", "urgent"]
        
        # 상태 필터
        if "해결된" in query_lower or "solved" in query_lower:
            filters["status"] = ["solved", "closed"]
        elif "진행중" in query_lower or "pending" in query_lower:
            filters["status"] = ["open", "pending"]
        
        return filters
    
    def _classify_intent(self, query: str) -> str:
        """의도 분류 (기존 로직)"""
        query_lower = query.lower()
        
        # 문제 해결 의도
        if any(keyword in query_lower for keyword in ["해결", "문제", "오류", "에러", "방법"]):
            return "problem_solving"
        
        # 정보 수집 의도
        if any(keyword in query_lower for keyword in ["찾아", "검색", "알려", "보여", "확인"]):
            return "info_gathering"
        
        # 학습 의도
        if any(keyword in query_lower for keyword in ["배우", "공부", "가이드", "튜토리얼"]):
            return "learning"
        
        return "general"
    
    def _get_date_range(self, days: int) -> Dict[str, str]:
        """날짜 범위 계산"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
    async def execute_enhanced_search(self, 
                                    context: EnhancedSearchContext,
                                    tenant_id: str,
                                    platform: str = "freshdesk",
                                    top_k: int = 10) -> Dict[str, Any]:
        """
        고급 검색 실행
        
        Args:
            context: 분석된 검색 컨텍스트
            tenant_id: 테넌트 ID
            platform: 플랫폼
            top_k: 결과 수
            
        Returns:
            Dict[str, Any]: 검색 결과
        """
        try:
            logger.info(f"고급 검색 실행: type={context.search_type}, intent={context.intent}")
            
            # 검색 타입별 전용 로직
            if context.search_type == "attachment":
                return await self._search_attachments(context, tenant_id, platform, top_k)
            elif context.search_type == "category":
                return await self._search_by_category(context, tenant_id, platform, top_k)
            elif context.search_type == "solution":
                return await self._search_solutions(context, tenant_id, platform, top_k)
            else:
                return await self._search_general(context, tenant_id, platform, top_k)
                
        except Exception as e:
            logger.error(f"고급 검색 실행 실패: {e}")
            return {
                "documents": [],
                "metadatas": [],
                "ids": [],
                "distances": [],
                "total_results": 0,
                "search_type": context.search_type,
                "error": str(e)
            }
    
    async def _search_attachments(self, 
                                context: EnhancedSearchContext,
                                tenant_id: str, 
                                platform: str, 
                                top_k: int) -> Dict[str, Any]:
        """첨부파일 전용 검색"""
        logger.info("첨부파일 전용 검색 시작")
        
        # 쿼리 임베딩 생성
        search_query = " ".join(context.keywords)
        embeddings = embed_documents_optimized([search_query], mode="multilingual")
        query_embedding = embeddings[0] if embeddings else None
        
        if not query_embedding:
            return {"documents": [], "total_results": 0, "error": "임베딩 생성 실패"}
        
        # 첨부파일이 있는 문서만 검색
        results = self.vector_db.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # 더 많이 검색 후 필터링
            tenant_id=tenant_id,
            platform=platform,
            has_attachments=True  # 첨부파일 필터
        )
        
        # 첨부파일 조건에 맞는 결과만 필터링
        filtered_results = self._filter_attachment_results(results, context.attachment_filters)
        
        # 첨부파일 정보 강화
        enhanced_results = await self._enhance_attachment_metadata(filtered_results)
        
        enhanced_results["search_type"] = "attachment"
        enhanced_results["filter_criteria"] = context.attachment_filters
        
        logger.info(f"첨부파일 검색 완료: {enhanced_results.get('total_results', 0)}개 결과")
        return enhanced_results
    
    async def _search_by_category(self,
                                context: EnhancedSearchContext,
                                tenant_id: str,
                                platform: str,
                                top_k: int) -> Dict[str, Any]:
        """카테고리별 검색"""
        logger.info(f"카테고리 검색 시작: {context.category_hints}")
        
        # 카테고리 키워드로 확장된 쿼리 생성
        category_keywords = []
        if context.category_hints:
            for category in context.category_hints:
                if category in self.category_patterns:
                    category_keywords.extend(self.category_patterns[category])
        
        # 원본 키워드와 카테고리 키워드 결합
        combined_keywords = context.keywords + category_keywords
        search_query = " ".join(combined_keywords)
        
        # 벡터 검색 실행
        embeddings = embed_documents_optimized([search_query], mode="multilingual")
        query_embedding = embeddings[0] if embeddings else None
        
        if not query_embedding:
            return {"documents": [], "total_results": 0, "error": "임베딩 생성 실패"}
        
        results = self.vector_db.search(
            query_embedding=query_embedding,
            top_k=top_k,
            tenant_id=tenant_id,
            platform=platform
        )
        
        # 카테고리 관련성으로 재정렬
        ranked_results = self._rank_by_category_relevance(results, context.category_hints)
        
        ranked_results["search_type"] = "category"
        ranked_results["category_hints"] = context.category_hints
        
        logger.info(f"카테고리 검색 완료: {ranked_results.get('total_results', 0)}개 결과")
        return ranked_results
    
    async def _search_solutions(self,
                              context: EnhancedSearchContext,
                              tenant_id: str,
                              platform: str,
                              top_k: int) -> Dict[str, Any]:
        """문제 해결 중심 검색"""
        logger.info("문제 해결 검색 시작")
        
        # 해결책 중심 키워드 확장
        solution_keywords = context.keywords.copy()
        if context.solution_requirements:
            if context.solution_requirements.get("해결책"):
                solution_keywords.extend(["해결", "solution", "fix", "방법"])
            if context.solution_requirements.get("유사사례"):
                solution_keywords.extend(["similar", "case", "example"])
        
        search_query = " ".join(solution_keywords)
        
        # 벡터 검색 실행
        embeddings = embed_documents_optimized([search_query], mode="multilingual")
        query_embedding = embeddings[0] if embeddings else None
        
        if not query_embedding:
            return {"documents": [], "total_results": 0, "error": "임베딩 생성 실패"}
        
        # 해결된 사례 우선 검색
        results = self.vector_db.search(
            query_embedding=query_embedding,
            top_k=top_k,
            tenant_id=tenant_id,
            platform=platform
        )
        
        # 해결책 관련성으로 재정렬
        solution_ranked = self._rank_by_solution_relevance(results, context.solution_requirements)
        
        solution_ranked["search_type"] = "solution"
        solution_ranked["solution_requirements"] = context.solution_requirements
        
        logger.info(f"해결책 검색 완료: {solution_ranked.get('total_results', 0)}개 결과")
        return solution_ranked
    
    async def _search_general(self,
                            context: EnhancedSearchContext,
                            tenant_id: str,
                            platform: str,
                            top_k: int) -> Dict[str, Any]:
        """일반 검색"""
        logger.info("일반 검색 시작")
        
        search_query = " ".join(context.keywords)
        
        # 벡터 검색 실행
        embeddings = embed_documents_optimized([search_query], mode="multilingual")
        query_embedding = embeddings[0] if embeddings else None
        
        if not query_embedding:
            return {"documents": [], "total_results": 0, "error": "임베딩 생성 실패"}
        
        results = self.vector_db.search(
            query_embedding=query_embedding,
            top_k=top_k,
            tenant_id=tenant_id,
            platform=platform
        )
        
        results["search_type"] = "general"
        return results
    
    def _filter_attachment_results(self, 
                                 results: Dict[str, Any], 
                                 filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """첨부파일 필터링"""
        if not filters or not results.get("metadatas"):
            return results
        
        filtered_docs = []
        filtered_metas = []
        filtered_ids = []
        filtered_distances = []
        
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])
        distances = results.get("distances", [])
        
        for i, (doc, meta, doc_id, distance) in enumerate(zip(documents, metadatas, ids, distances)):
            # 첨부파일 메타데이터 확인
            attachments = meta.get("all_images", []) or meta.get("attachments", [])
            
            if not attachments:
                continue
            
            # 콘텐츠 타입 필터
            if "content_types" in filters:
                target_types = filters["content_types"]
                has_matching_type = any(
                    att.get("content_type") in target_types 
                    for att in attachments
                )
                if not has_matching_type:
                    continue
            
            # 크기 필터
            if "min_size" in filters:
                min_size = filters["min_size"]
                has_large_file = any(
                    att.get("size", 0) >= min_size 
                    for att in attachments
                )
                if not has_large_file:
                    continue
            
            if "max_size" in filters:
                max_size = filters["max_size"]
                has_small_file = any(
                    att.get("size", 0) <= max_size 
                    for att in attachments
                )
                if not has_small_file:
                    continue
            
            # 소스 위치 필터
            if "source_location" in filters:
                target_location = filters["source_location"]
                has_matching_source = any(
                    att.get("source_location") == target_location 
                    for att in attachments
                )
                if not has_matching_source:
                    continue
            
            # 통과한 경우 결과에 추가
            filtered_docs.append(doc)
            filtered_metas.append(meta)
            filtered_ids.append(doc_id)
            filtered_distances.append(distance)
        
        return {
            "documents": filtered_docs,
            "metadatas": filtered_metas,
            "ids": filtered_ids,
            "distances": filtered_distances,
            "total_results": len(filtered_docs)
        }
    
    async def _enhance_attachment_metadata(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """첨부파일 메타데이터 강화"""
        metadatas = results.get("metadatas", [])
        
        for meta in metadatas:
            attachments = meta.get("all_images", []) or meta.get("attachments", [])
            
            # 첨부파일 요약 정보 추가
            if attachments:
                file_types = set()
                total_size = 0
                file_count = len(attachments)
                
                for att in attachments:
                    content_type = att.get("content_type", "")
                    if content_type.startswith("image/"):
                        file_types.add("이미지")
                    elif content_type == "application/pdf":
                        file_types.add("PDF")
                    elif "excel" in content_type or "spreadsheet" in content_type:
                        file_types.add("엑셀")
                    elif "word" in content_type:
                        file_types.add("워드")
                    else:
                        file_types.add("기타")
                    
                    total_size += att.get("size", 0)
                
                meta["attachment_summary"] = {
                    "file_types": list(file_types),
                    "file_count": file_count,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "has_images": any(att.get("content_type", "").startswith("image/") for att in attachments)
                }
        
        return results
    
    def _rank_by_category_relevance(self, 
                                  results: Dict[str, Any], 
                                  category_hints: Optional[List[str]]) -> Dict[str, Any]:
        """카테고리 관련성으로 재정렬"""
        if not category_hints or not results.get("documents"):
            return results
        
        # 카테고리 키워드 목록 생성
        category_keywords = []
        for category in category_hints:
            if category in self.category_patterns:
                category_keywords.extend(self.category_patterns[category])
        
        # 각 문서의 카테고리 관련성 점수 계산
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])
        distances = results.get("distances", [])
        
        scored_results = []
        for i, (doc, meta, doc_id, distance) in enumerate(zip(documents, metadatas, ids, distances)):
            # 문서 내용에서 카테고리 키워드 등장 빈도 계산
            doc_lower = doc.lower()
            category_score = sum(1 for keyword in category_keywords if keyword in doc_lower)
            
            # 메타데이터에서도 카테고리 관련성 확인
            title = meta.get("title", meta.get("subject", "")).lower()
            title_score = sum(1 for keyword in category_keywords if keyword in title)
            
            total_score = category_score + (title_score * 2)  # 제목에 더 높은 가중치
            
            scored_results.append({
                "document": doc,
                "metadata": meta,
                "id": doc_id,
                "distance": distance,
                "category_score": total_score,
                "original_index": i
            })
        
        # 카테고리 점수로 정렬 (높은 점수 우선, 같으면 벡터 거리순)
        scored_results.sort(key=lambda x: (-x["category_score"], x["distance"]))
        
        # 정렬된 결과로 재구성
        return {
            "documents": [r["document"] for r in scored_results],
            "metadatas": [r["metadata"] for r in scored_results],
            "ids": [r["id"] for r in scored_results],
            "distances": [r["distance"] for r in scored_results],
            "total_results": len(scored_results),
            "category_scores": [r["category_score"] for r in scored_results]
        }
    
    def _rank_by_solution_relevance(self, 
                                  results: Dict[str, Any], 
                                  solution_requirements: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """해결책 관련성으로 재정렬"""
        if not solution_requirements or not results.get("documents"):
            return results
        
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])
        distances = results.get("distances", [])
        
        scored_results = []
        
        for i, (doc, meta, doc_id, distance) in enumerate(zip(documents, metadatas, ids, distances)):
            solution_score = 0
            doc_lower = doc.lower()
            
            # 해결책 키워드 점수
            if solution_requirements.get("해결책"):
                solution_keywords = ["해결", "solution", "fix", "방법", "해결방법"]
                solution_score += sum(2 for keyword in solution_keywords if keyword in doc_lower)
            
            # 유사사례 점수
            if solution_requirements.get("유사사례"):
                case_keywords = ["similar", "case", "example", "비슷한", "같은", "케이스"]
                solution_score += sum(1 for keyword in case_keywords if keyword in doc_lower)
            
            # 단계별 가이드 점수
            if solution_requirements.get("단계별"):
                step_keywords = ["단계", "step", "순서", "절차", "1.", "2.", "3."]
                solution_score += sum(1 for keyword in step_keywords if keyword in doc_lower)
            
            # 해결된 티켓인 경우 보너스 점수
            if meta.get("status") in ["solved", "closed"]:
                solution_score += 3
            
            scored_results.append({
                "document": doc,
                "metadata": meta,
                "id": doc_id,
                "distance": distance,
                "solution_score": solution_score,
                "original_index": i
            })
        
        # 해결책 점수로 정렬
        scored_results.sort(key=lambda x: (-x["solution_score"], x["distance"]))
        
        return {
            "documents": [r["document"] for r in scored_results],
            "metadatas": [r["metadata"] for r in scored_results],
            "ids": [r["id"] for r in scored_results],
            "distances": [r["distance"] for r in scored_results],
            "total_results": len(scored_results),
            "solution_scores": [r["solution_score"] for r in scored_results]
        }
    
    async def generate_enhanced_response(self, 
                                       results: Dict[str, Any], 
                                       context: EnhancedSearchContext) -> str:
        """
        검색 타입에 특화된 응답 생성
        
        Args:
            results: 검색 결과
            context: 검색 컨텍스트
            
        Returns:
            str: 타입별 특화 응답
        """
        try:
            if not self.llm_manager or not results.get("documents"):
                return "검색 결과를 확인해주세요."
            
            search_type = context.search_type
            
            if search_type == "attachment":
                return await self._generate_attachment_response(results, context)
            elif search_type == "category":
                return await self._generate_category_response(results, context)
            elif search_type == "solution":
                return await self._generate_solution_response(results, context)
            else:
                return await self._generate_general_response(results, context)
                
        except Exception as e:
            logger.error(f"특화 응답 생성 실패: {e}")
            return "응답 생성 중 오류가 발생했습니다. 검색 결과를 직접 확인해주세요."
    
    async def _generate_attachment_response(self, 
                                          results: Dict[str, Any], 
                                          context: EnhancedSearchContext) -> str:
        """첨부파일 검색 전용 응답 생성"""
        prompt = f"""상담원님께서 첨부파일 검색을 요청하셨습니다.

검색 조건: {context.attachment_filters}
검색 결과: {results.get('total_results', 0)}개의 관련 문서

다음 형식으로 응답해주세요:

📎 **첨부파일 검색 결과**

🔍 **검색된 파일 유형과 내용**
- [각 결과별로 첨부파일 정보 요약]

💡 **상담 활용 가이드**
- [첨부파일을 어떻게 활용할지 안내]

📋 **추천 액션**
- [다음 단계 제안]

검색된 문서들: {self._format_attachment_results(results)}"""
        
        return await self._call_llm(prompt)
    
    async def _generate_category_response(self, 
                                        results: Dict[str, Any], 
                                        context: EnhancedSearchContext) -> str:
        """카테고리 검색 전용 응답 생성"""
        prompt = f"""상담원님께서 '{context.category_hints}' 카테고리 관련 문서를 검색하셨습니다.

검색 결과: {results.get('total_results', 0)}개의 관련 문서

다음 형식으로 응답해주세요:

🏷️ **카테고리별 문서 검색 결과**

📊 **해당 카테고리 주요 이슈**
- [발견된 패턴과 주요 문제점]

🎯 **카테고리별 해결 가이드**
- [이 카테고리에서 일반적인 해결 방법]

📚 **관련 문서 활용법**
- [검색된 문서들을 어떻게 활용할지]

검색된 문서들: {self._format_search_results(results)}"""
        
        return await self._call_llm(prompt)
    
    async def _generate_solution_response(self, 
                                        results: Dict[str, Any], 
                                        context: EnhancedSearchContext) -> str:
        """문제 해결 검색 전용 응답 생성"""
        prompt = f"""상담원님께서 문제 해결 방법을 검색하셨습니다.

해결 요구사항: {context.solution_requirements}
검색 결과: {results.get('total_results', 0)}개의 해결책 문서

다음 형식으로 응답해주세요:

🔧 **문제 해결 가이드**

⚡ **즉시 적용 가능한 해결책**
- [바로 시도할 수 있는 방법들]

📝 **단계별 해결 절차**
- [체계적인 문제 해결 순서]

🎯 **유사 케이스 활용법**
- [비슷한 사례에서 배울 점]

⚠️ **주의사항 및 에스컬레이션**
- [주의할 점과 상위 지원 요청 시점]

관련 해결 사례들: {self._format_search_results(results)}"""
        
        return await self._call_llm(prompt)
    
    async def _generate_general_response(self, 
                                       results: Dict[str, Any], 
                                       context: EnhancedSearchContext) -> str:
        """일반 검색 응답 생성"""
        prompt = f"""상담원님의 검색 요청에 대한 결과입니다.

검색 키워드: {context.keywords}
검색 결과: {results.get('total_results', 0)}개의 관련 문서

다음과 같은 정보를 찾을 수 있었습니다:

{self._format_search_results(results)}

검색 결과를 바탕으로 상담원님께 도움이 되는 가이드를 제공해주세요."""
        
        return await self._call_llm(prompt)
    
    async def _call_llm(self, prompt: str) -> str:
        """LLM 호출 공통 로직"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_manager.generate(
                messages=messages,
                provider=LLMProvider.ANTHROPIC,
                model="claude-3-haiku-20240307",
                max_tokens=1000
            )
            
            if response and response.success:
                return response.content
            else:
                return "응답 생성에 실패했습니다. 검색 결과를 직접 확인해주세요."
                
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return f"응답 생성 중 오류가 발생했습니다: {str(e)[:100]}..."
    
    def _format_attachment_results(self, results: Dict[str, Any]) -> str:
        """첨부파일 결과 포맷팅"""
        formatted = []
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        for i, (doc, meta) in enumerate(zip(documents[:5], metadatas[:5])):
            title = meta.get("title", meta.get("subject", f"문서 {i+1}"))
            attachment_summary = meta.get("attachment_summary", {})
            
            formatted.append(f"""
📄 {title}
📎 첨부파일: {attachment_summary.get('file_types', [])} ({attachment_summary.get('file_count', 0)}개)
📏 크기: {attachment_summary.get('total_size_mb', 0)}MB
내용: {doc[:200]}...
---""")
        
        return "\n".join(formatted)
    
    def _format_search_results(self, results: Dict[str, Any]) -> str:
        """일반 검색 결과 포맷팅"""
        formatted = []
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        for i, (doc, meta) in enumerate(zip(documents[:5], metadatas[:5])):
            title = meta.get("title", meta.get("subject", f"문서 {i+1}"))
            doc_type = meta.get("doc_type", "unknown")
            
            formatted.append(f"""
📄 {title} ({doc_type})
내용: {doc[:300]}...
---""")
        
        return "\n".join(formatted)