"""
Progressive Filter Upgrade - 점진적 필터 업그레이드 시스템

기존 데이터 재처리 없이 새 데이터만 개선된 필터링 적용하고
런타임에 버전별 가중치로 품질 차이 보상하는 Zero-Cost 솔루션
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ProgressiveFilterUpgrade:
    """
    점진적 필터 업그레이드 관리자
    
    - 기존 데이터 재처리 없음 (Zero-Cost)
    - 신규 데이터만 스마트 필터링 적용
    - 런타임 가중치로 품질 차이 보상
    - 자연스러운 품질 향상
    """
    
    def __init__(self):
        self.version_markers = {
            "legacy": "v1_unfiltered",
            "smart": "v2_smart_filtered"
        }
        self.version_weights = {
            "v2_smart_filtered": 1.3,  # 신규 데이터 부스팅
            "v1_unfiltered": 0.7       # 레거시 데이터 페널티
        }
        
    def add_version_metadata(self, metadata: Dict[str, Any], is_smart_filtered: bool = True) -> Dict[str, Any]:
        """
        벡터 DB 저장 시 버전 정보 추가
        
        Args:
            metadata: 기존 메타데이터
            is_smart_filtered: 스마트 필터링 적용 여부
            
        Returns:
            버전 정보가 추가된 메타데이터
        """
        enhanced_metadata = metadata.copy()
        
        if is_smart_filtered:
            enhanced_metadata.update({
                "conversation_version": self.version_markers["smart"],
                "filter_applied": True,
                "filter_mode": "smart_balanced",
                "upgrade_date": datetime.now().isoformat()
            })
        else:
            enhanced_metadata.update({
                "conversation_version": self.version_markers["legacy"],
                "filter_applied": False,
                "filter_mode": "none"
            })
            
        return enhanced_metadata
    
    def apply_runtime_weights(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색 결과에 버전별 가중치 적용
        
        Args:
            search_results: 벡터 검색 결과
            
        Returns:
            가중치가 적용된 검색 결과
        """
        weighted_results = []
        
        for result in search_results:
            weighted_result = result.copy()
            version = result.get("conversation_version", "v1_unfiltered")
            
            # 원본 점수에 버전별 가중치 적용
            original_score = weighted_result.get("score", 0.0)
            version_weight = self.version_weights.get(version, 1.0)
            weighted_result["score"] = original_score * version_weight
            
            # 디버깅 정보 추가
            weighted_result["weight_applied"] = version_weight
            weighted_result["original_score"] = original_score
            
            weighted_results.append(weighted_result)
        
        # 가중치 적용 후 재정렬
        weighted_results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"런타임 가중치 적용 완료: {len(weighted_results)}개 결과")
        return weighted_results
    
    def get_upgrade_statistics(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        업그레이드 진행 상황 통계 생성
        
        Args:
            search_results: 검색 결과
            
        Returns:
            업그레이드 통계 정보
        """
        total_count = len(search_results)
        smart_count = sum(1 for r in search_results 
                         if r.get("conversation_version") == "v2_smart_filtered")
        legacy_count = total_count - smart_count
        
        upgrade_ratio = (smart_count / total_count * 100) if total_count > 0 else 0
        
        return {
            "total_results": total_count,
            "smart_filtered_count": smart_count,
            "legacy_count": legacy_count,
            "upgrade_progress": f"{upgrade_ratio:.1f}%",
            "quality_improvement": "점진적 향상 중" if upgrade_ratio < 90 else "업그레이드 완료"
        }


class RuntimeConversationRanker:
    """
    런타임 대화 관련성 재평가 시스템
    
    이미 저장된 대화들을 사용자 쿼리와의 관련성으로 재순위하여
    필터링 부족을 런타임에 보완
    """
    
    def __init__(self):
        self.relevance_keywords = {
            "problem": ["문제", "오류", "에러", "error", "issue", "problem"],
            "solution": ["해결", "solution", "fix", "resolve", "답변"],
            "request": ["요청", "request", "문의", "질문", "help"],
            "urgent": ["긴급", "urgent", "빨리", "즉시", "immediately"]
        }
    
    def calculate_conversation_relevance(self, conversation: Dict[str, Any], user_query: str) -> float:
        """
        대화와 사용자 쿼리 간의 관련성 점수 계산
        
        Args:
            conversation: 대화 데이터
            user_query: 사용자 쿼리
            
        Returns:
            관련성 점수 (0.0-1.0)
        """
        conv_text = self._extract_conversation_text(conversation).lower()
        query_lower = user_query.lower()
        
        relevance_score = 0.0
        
        # 1. 키워드 매칭 점수
        for category, keywords in self.relevance_keywords.items():
            for keyword in keywords:
                if keyword in query_lower and keyword in conv_text:
                    relevance_score += 0.2
        
        # 2. 텍스트 유사성 (간단한 토큰 오버랩)
        query_tokens = set(query_lower.split())
        conv_tokens = set(conv_text.split())
        overlap = len(query_tokens & conv_tokens)
        max_tokens = max(len(query_tokens), len(conv_tokens))
        
        if max_tokens > 0:
            relevance_score += (overlap / max_tokens) * 0.5
        
        # 3. 대화 길이 및 품질 보너스
        if len(conv_text) > 50:  # 의미있는 길이
            relevance_score += 0.1
        
        return min(relevance_score, 1.0)
    
    def rerank_conversations(self, conversations: List[Dict[str, Any]], 
                           user_query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        대화들을 쿼리 관련성으로 재순위
        
        Args:
            conversations: 대화 목록
            user_query: 사용자 쿼리
            top_k: 반환할 상위 대화 수
            
        Returns:
            관련성 순으로 정렬된 대화 목록
        """
        scored_conversations = []
        
        for conv in conversations:
            relevance_score = self.calculate_conversation_relevance(conv, user_query)
            scored_conversations.append((conv, relevance_score))
        
        # 관련성 점수로 정렬
        scored_conversations.sort(key=lambda x: x[1], reverse=True)
        
        # 상위 k개 반환
        top_conversations = [conv for conv, score in scored_conversations[:top_k]]
        
        logger.info(f"대화 재순위 완료: {len(conversations)}개 → {len(top_conversations)}개 (관련성 기준)")
        return top_conversations
    
    def _extract_conversation_text(self, conversation: Dict[str, Any]) -> str:
        """대화에서 텍스트 추출"""
        for field in ["body_text", "body", "text", "content", "message"]:
            if field in conversation and conversation[field]:
                return str(conversation[field])
        return ""


class HybridFilteringStrategy:
    """
    하이브리드 필터링 전략
    
    - 신규 데이터: 스마트 필터링
    - 기존 데이터: 런타임 재순위
    - 점진적 품질 향상
    """
    
    def __init__(self):
        self.progressive_upgrade = ProgressiveFilterUpgrade()
        self.runtime_ranker = RuntimeConversationRanker()
    
    async def apply_hybrid_filtering(self, all_conversations: List[Dict[str, Any]], 
                                   user_query: str = None) -> List[Dict[str, Any]]:
        """
        하이브리드 필터링 적용
        
        Args:
            all_conversations: 전체 대화 목록
            user_query: 사용자 쿼리 (있으면 관련성 재순위)
            
        Returns:
            하이브리드 필터링된 대화 목록
        """
        # 1. 버전별 분리
        smart_filtered = [c for c in all_conversations 
                         if c.get("conversation_version") == "v2_smart_filtered"]
        legacy_conversations = [c for c in all_conversations 
                              if c.get("conversation_version") == "v1_unfiltered"]
        
        # 2. 신규 데이터는 그대로 우선 사용
        final_conversations = smart_filtered.copy()
        
        # 3. 레거시 데이터는 런타임 재순위 후 보조 사용
        if user_query and legacy_conversations:
            ranked_legacy = self.runtime_ranker.rerank_conversations(
                legacy_conversations, user_query, top_k=5
            )
            final_conversations.extend(ranked_legacy)
        elif legacy_conversations:
            # 쿼리가 없으면 최근 대화 우선
            sorted_legacy = sorted(legacy_conversations, 
                                 key=lambda x: x.get("created_at", 0), reverse=True)
            final_conversations.extend(sorted_legacy[:5])
        
        # 4. 최종 중복 제거 및 정렬
        seen_ids = set()
        unique_conversations = []
        for conv in final_conversations:
            conv_id = conv.get("id") or conv.get("conversation_id", "")
            if conv_id and conv_id not in seen_ids:
                unique_conversations.append(conv)
                seen_ids.add(conv_id)
        
        logger.info(f"하이브리드 필터링 완료: 신규 {len(smart_filtered)}개 + 레거시 {len(legacy_conversations)}개 → 최종 {len(unique_conversations)}개")
        
        return unique_conversations
