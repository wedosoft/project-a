"""
Smart Conversation Filter - 스마트 대화 필터링 시스템

기존 LLMManager의 필터링 기능을 대체하여
대화 수 제한 없는 스마트 필터링을 제공합니다.

주요 기능:
- 3단계 필터링 (노이즈 제거 → 중요도 평가 → 토큰 예산 최적화)
- 다국어 지원 (한국어/영어)
- 맥락 보존 우선
- 적응형 전략 선택
"""

import json
import re
import hashlib
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SmartConversationFilter:
    """
    대화 수 제한 없는 스마트 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 다국어 지원 (한국어/영어)
    """

    def __init__(self, config_path: str = "config/data/multilingual_keywords.json"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self.keyword_patterns = self._load_keyword_patterns(config_path)
        self.token_budget = self.config.get("max_token_budget", 8000)

    def _load_config(self) -> Dict:
        """기본 설정 로드"""
        return {
            "max_token_budget": 8000,
            "preserve_context_flow": True,
            "multilingual_support": True,
            "adaptive_filtering": True,
            "quality_threshold": 0.7,
            "strategies": {
                "tiny": {"max_conv": 10, "mode": "minimal_filter"},
                "small": {"max_conv": 25, "mode": "smart_filter"},
                "medium": {"max_conv": 50, "mode": "aggressive_filter"},
                "large": {"max_conv": 100, "mode": "chunk_filter"}
            }
        }

    def _load_keyword_patterns(self, config_path: str) -> Dict:
        """다국어 키워드 패턴 로드"""
        try:
            # backend/core/llm/filters/ -> backend/ (4번 parent)
            full_path = Path(__file__).parent.parent.parent.parent / config_path
            with open(full_path, 'r', encoding='utf-8') as f:
                self.logger.info(f"키워드 파일 로드 성공: {full_path}")
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"키워드 파일 없음: {config_path} (시도한 경로: {Path(__file__).parent.parent.parent.parent / config_path}), 기본 패턴 사용")
            return self._get_default_patterns()

    def _get_default_patterns(self) -> Dict:
        """기본 패턴 반환 (파일 로드 실패시)"""
        return {
            "noise_patterns": {
                "ko": {"auto_responses": ["감사합니다", "자동 응답"]},
                "en": {"auto_responses": ["thank you", "auto"]}
            },
            "importance_keywords": {
                "ko": {"high": {"problem": ["문제", "오류"]}},
                "en": {"high": {"problem": ["issue", "error"]}}
            }
        }

    def filter_conversations_unlimited(self, conversations: List[Dict]) -> List[Dict]:
        """
        메인 필터링 함수 - 대화 수 제한 없음
        """
        if not conversations:
            return []

        total_conversations = len(conversations)
        strategy = self._select_strategy(total_conversations)

        self.logger.info(f"필터링 시작: {total_conversations}개 대화, 전략: {strategy}")

        if strategy == "minimal_filter":
            return self._minimal_filtering(conversations)
        elif strategy == "smart_filter":
            return self._smart_filtering(conversations)
        elif strategy == "aggressive_filter":
            return self._aggressive_filtering(conversations)
        elif strategy == "chunk_filter":
            return self._chunk_filtering(conversations)
        else:
            return self._smart_filtering(conversations)  # 기본값

    def _select_strategy(self, conversation_count: int) -> str:
        """대화 수에 따른 필터링 전략 선택"""
        strategies = self.keyword_patterns.get("strategies", self.config["strategies"])
        
        for strategy_name, strategy_config in strategies.items():
            if conversation_count <= strategy_config["max_conv"]:
                return strategy_config["mode"]
        
        return "chunk_filter"  # 매우 많은 대화일 때

    def _minimal_filtering(self, conversations: List[Dict]) -> List[Dict]:
        """최소 필터링 - 10개 이하 대화"""
        # 노이즈만 제거하고 대부분 유지
        filtered = []
        for conv in conversations:
            if not self._is_noise_conversation(conv):
                filtered.append(conv)
        
        self.logger.info(f"최소 필터링 완료: {len(conversations)} → {len(filtered)}")
        return filtered

    def _smart_filtering(self, conversations: List[Dict]) -> List[Dict]:
        """스마트 필터링 - 25개 이하 대화"""
        # 1단계: 노이즈 제거
        step1_filtered = []
        for conv in conversations:
            if not self._is_noise_conversation(conv):
                step1_filtered.append(conv)

        # 2단계: 중요도 평가 및 선택
        scored_conversations = []
        for conv in step1_filtered:
            score = self._calculate_importance_score(conv)
            scored_conversations.append((conv, score))

        # 점수순 정렬
        scored_conversations.sort(key=lambda x: x[1], reverse=True)

        # 3단계: 토큰 예산 내 선택
        final_conversations = self._select_within_token_budget(scored_conversations)

        self.logger.info(f"스마트 필터링 완료: {len(conversations)} → {len(step1_filtered)} → {len(final_conversations)}")
        return final_conversations

    def _aggressive_filtering(self, conversations: List[Dict]) -> List[Dict]:
        """적극적 필터링 - 50개 이하 대화"""
        # 더 엄격한 노이즈 제거 + 중요도 필터링
        filtered = []
        for conv in conversations:
            if self._is_highly_important_conversation(conv):
                filtered.append(conv)

        # 여전히 많으면 토큰 예산으로 추가 제한
        if len(filtered) > 15:
            scored = [(conv, self._calculate_importance_score(conv)) for conv in filtered]
            scored.sort(key=lambda x: x[1], reverse=True)
            filtered = [conv for conv, _ in scored[:15]]

        self.logger.info(f"적극적 필터링 완료: {len(conversations)} → {len(filtered)}")
        return filtered

    def _chunk_filtering(self, conversations: List[Dict]) -> List[Dict]:
        """청크 필터링 - 100개 이상 대화"""
        # 시간대별로 나누어 각 청크에서 핵심 대화만 선택
        time_chunks = self._group_by_time_periods(conversations)
        selected_conversations = []

        for chunk in time_chunks:
            # 각 청크에서 최대 3-5개만 선택
            chunk_filtered = self._smart_filtering(chunk)
            if len(chunk_filtered) > 5:
                chunk_filtered = chunk_filtered[:5]
            selected_conversations.extend(chunk_filtered)

        self.logger.info(f"청크 필터링 완료: {len(conversations)} → {len(selected_conversations)}")
        return selected_conversations

    def _is_noise_conversation(self, conv: Dict) -> bool:
        """노이즈 대화 판별 (1단계 필터링)"""
        body = self._extract_conversation_body(conv).strip()
        language = self._detect_language(body)
        
        noise_patterns = self.keyword_patterns.get("noise_patterns", {}).get(language, {})
        
        # 너무 짧은 대화
        min_length = self.keyword_patterns.get("token_estimation", {}).get(
            f"min_conversation_length_{language}", 10 if language == "ko" else 20
        )
        if len(body) < min_length:
            return True

        # 노이즈 패턴 체크
        body_lower = body.lower()
        for pattern_type, patterns in noise_patterns.items():
            for pattern in patterns:
                if pattern.lower() in body_lower:
                    return True

        return False

    def _calculate_importance_score(self, conv: Dict) -> float:
        """다국어 중요도 점수 계산 (0.0 ~ 1.0)"""
        body = self._extract_conversation_body(conv).strip()
        language = self._detect_language(body)
        
        score = 0.4  # 기본 점수
        
        # 길이 점수 (언어별 다른 기준)
        if language == "ko":
            if 20 <= len(body) <= 200:
                score += 0.2
            elif len(body) > 200:
                score += 0.1
        else:  # 영어
            if 30 <= len(body) <= 300:
                score += 0.2
            elif len(body) > 300:
                score += 0.1

        # 키워드 점수
        importance_keywords = self.keyword_patterns.get("importance_keywords", {}).get(language, {})
        body_lower = body.lower()

        # 높은 중요도 키워드
        for category, keywords in importance_keywords.get("high", {}).items():
            for keyword in keywords:
                if keyword.lower() in body_lower:
                    score += 0.3
                    break

        # 중간 중요도 키워드
        for category, keywords in importance_keywords.get("medium", {}).items():
            for keyword in keywords:
                if keyword.lower() in body_lower:
                    score += 0.2
                    break

        # 위치 점수 (첫 번째와 마지막 대화 높은 가중치)
        # 이 부분은 호출하는 곳에서 인덱스 정보를 전달받아야 함

        return min(score, 1.0)

    def _is_highly_important_conversation(self, conv: Dict) -> bool:
        """고중요도 대화 판별"""
        score = self._calculate_importance_score(conv)
        return score >= 0.7

    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float]], max_tokens: int = None) -> List[Dict]:
        """토큰 예산 내 최적 선택"""
        if max_tokens is None:
            max_tokens = self.token_budget

        selected = []
        total_tokens = 0

        for conv, score in scored_conversations:
            body = self._extract_conversation_body(conv)
            tokens = self._estimate_tokens(body)
            
            if total_tokens + tokens <= max_tokens:
                selected.append(conv)
                total_tokens += tokens
            else:
                break

        return selected

    def _estimate_tokens(self, text: str) -> int:
        """텍스트 토큰 수 추정"""
        language = self._detect_language(text)
        token_config = self.keyword_patterns.get("token_estimation", {})
        
        if language == "ko":
            multiplier = token_config.get("korean_multiplier", 1.5)
            return int(len(text) * multiplier)
        else:
            multiplier = token_config.get("english_multiplier", 1.3)
            return int(len(text.split()) * multiplier)

    def _detect_language(self, text: str) -> str:
        """한글 문자 비율로 언어 감지"""
        korean_chars = len(re.findall(r'[가-힣]', text))
        total_chars = len(re.sub(r'\s', '', text))
        korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
        return "ko" if korean_ratio > 0.3 else "en"

    def _extract_conversation_body(self, conv: Dict) -> str:
        """대화에서 본문 텍스트 추출"""
        # 기존 LLMManager와 동일한 로직
        if "body_text" in conv and conv["body_text"]:
            return conv["body_text"]
        elif "body" in conv and conv["body"]:
            # HTML 태그 제거
            import re
            body = conv["body"]
            body = re.sub(r'<[^>]+>', '', body)
            body = re.sub(r'&[^;]+;', '', body)
            return body.strip()
        return ""

    def _group_by_time_periods(self, conversations: List[Dict]) -> List[List[Dict]]:
        """시간대별로 대화 그룹화"""
        # 간단한 구현: 시간순 정렬 후 5개씩 묶기
        # 실제로는 created_at 필드를 이용해 시간 간격으로 그룹화해야 함
        chunks = []
        chunk_size = 10
        
        for i in range(0, len(conversations), chunk_size):
            chunks.append(conversations[i:i + chunk_size])
        
        return chunks

    def get_filtering_stats(self) -> Dict:
        """필터링 통계 정보 반환"""
        return {
            "token_budget": self.token_budget,
            "config": self.config,
            "keyword_patterns_loaded": bool(self.keyword_patterns)
        }
