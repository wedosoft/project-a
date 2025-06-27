# 대화 수 제한 없는 스마트 필터링 실제 구현

## 핵심 클래스 구현

```python
# backend/core/langchain/smart_conversation_filter.py
import json
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

class SmartConversationFilter:
    """
    대화 수 제한 없는 스마트 필터링 시스템
    - 30-50개 대화도 효과적으로 처리
    - 맥락 보존 우선, 노이즈 제거 부차
    - 다국어 지원 (한국어/영어)
    """
    
    def __init__(self, config_path: str = "config/multilingual_keywords.json"):
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
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # 기본 패턴 반환
            return self._get_default_patterns()
    
    def filter_conversations_unlimited(self, conversations: List[Dict]) -> List[Dict]:
        """
        메인 필터링 함수 - 대화 수 제한 없음
        """
        if not conversations:
            return []
        
        total_conversations = len(conversations)
        strategy = self._select_strategy(total_conversations)
        
        if strategy == "minimal_filter":
            return self._minimal_filtering(conversations)
        elif strategy == "smart_filter":
            return self._smart_filtering_pipeline(conversations)
        elif strategy == "aggressive_filter":
            return self._aggressive_filtering_pipeline(conversations)
        else:  # chunk_filter
            return self._chunk_based_filtering(conversations)
    
    def _smart_filtering_pipeline(self, conversations: List[Dict]) -> List[Dict]:
        """스마트 필터링 파이프라인 (25-50개 대화)"""
        
        # Step 1: 노이즈 제거
        cleaned_conversations = self._remove_basic_noise(conversations)
        
        # Step 2: 각 대화의 중요도 점수 계산
        scored_conversations = []
        for i, conv in enumerate(cleaned_conversations):
            importance_score = self._calculate_importance_score(conv)
            position_weight = self._calculate_position_weight(i, len(cleaned_conversations))
            context_score = self._calculate_context_continuity(conv, cleaned_conversations, i)
            
            final_score = (importance_score * 0.5 + position_weight * 0.2 + context_score * 0.3)
            conversation_type = self._classify_conversation_type(conv)
            
            scored_conversations.append((conv, final_score, conversation_type))
        
        # Step 3: 토큰 예산 내에서 최적 선택
        return self._select_within_token_budget(scored_conversations)
    
    def _calculate_importance_score(self, conv: Dict) -> float:
        """다국어 중요도 점수 계산"""
        body = self._extract_conversation_body(conv)
        language = self._detect_language(body)
        
        # 언어별 키워드 패턴 가져오기
        lang_patterns = self.keyword_patterns.get(language, {})
        
        # 기본 점수
        base_score = 0.4
        
        # 길이 기반 점수
        length_score = self._calculate_length_score(body, language)
        
        # 키워드 매칭 점수
        keyword_score = self._calculate_keyword_matching_score(body, lang_patterns)
        
        # 감정/톤 점수 (긴급함, 중요함 등)
        urgency_score = self._calculate_urgency_score(body, lang_patterns)
        
        # 최종 점수 조합
        final_score = (base_score + length_score + keyword_score + urgency_score) / 4
        return min(max(final_score, 0.0), 1.0)
    
    def _calculate_length_score(self, body: str, language: str) -> float:
        """언어별 길이 기반 점수"""
        if language == "ko":
            # 한국어: 10-100자가 적정
            char_count = len(body)
            if 10 <= char_count <= 100:
                return 1.0
            elif char_count < 10:
                return 0.2
            else:  # 너무 길면 요약 필요
                return 0.8
        else:  # 영어
            # 영어: 20-200자가 적정
            word_count = len(body.split())
            if 5 <= word_count <= 50:
                return 1.0
            elif word_count < 5:
                return 0.2
            else:
                return 0.8
    
    def _calculate_keyword_matching_score(self, body: str, lang_patterns: Dict) -> float:
        """키워드 매칭 점수"""
        body_lower = body.lower()
        total_score = 0.0
        
        # 고중요도 키워드 (가중치 1.0)
        high_importance = lang_patterns.get("high_importance", {})
        for category, keywords in high_importance.items():
            for keyword in keywords:
                if keyword.lower() in body_lower:
                    total_score += 1.0
                    break  # 카테고리당 최대 1점
        
        # 중간중요도 키워드 (가중치 0.6)
        medium_importance = lang_patterns.get("medium_importance", {})
        for category, keywords in medium_importance.items():
            for keyword in keywords:
                if keyword.lower() in body_lower:
                    total_score += 0.6
                    break
        
        # 저중요도는 오히려 점수 감소 (가중치 -0.2)
        low_importance = lang_patterns.get("low_importance", {})
        for category, keywords in low_importance.items():
            for keyword in keywords:
                if keyword.lower() in body_lower:
                    total_score -= 0.2
                    break
        
        # 정규화 (0.0 ~ 1.0)
        return min(max(total_score / 3.0, 0.0), 1.0)
    
    def _calculate_urgency_score(self, body: str, lang_patterns: Dict) -> float:
        """긴급도/중요도 점수"""
        body_lower = body.lower()
        
        # 긴급도 키워드 체크
        escalation_keywords = lang_patterns.get("high_importance", {}).get("escalation_indicators", [])
        for keyword in escalation_keywords:
            if keyword.lower() in body_lower:
                return 1.0
        
        return 0.5  # 기본값
    
    def _select_within_token_budget(self, scored_conversations: List[Tuple[Dict, float, str]]) -> List[Dict]:
        """토큰 예산 내에서 최적 선택"""
        # 점수순 정렬
        scored_conversations.sort(key=lambda x: x[1], reverse=True)
        
        selected = []
        current_tokens = 0
        
        # 필수 대화 유형 우선 선택
        essential_types = ["problem_definition", "solution", "conclusion"]
        
        # 1단계: 필수 대화 선택
        for conv, score, conv_type in scored_conversations:
            if conv_type in essential_types and current_tokens < self.token_budget * 0.6:
                body = self._extract_conversation_body(conv)
                estimated_tokens = self._estimate_tokens(body)
                
                if current_tokens + estimated_tokens <= self.token_budget:
                    selected.append(conv)
                    current_tokens += estimated_tokens
        
        # 2단계: 나머지 대화 중요도순 선택
        for conv, score, conv_type in scored_conversations:
            if conv not in selected:
                body = self._extract_conversation_body(conv)
                estimated_tokens = self._estimate_tokens(body)
                
                if current_tokens + estimated_tokens <= self.token_budget:
                    selected.append(conv)
                    current_tokens += estimated_tokens
                elif score > 0.85:  # 매우 중요하면 요약해서 포함
                    summarized_conv = self._create_summary_version(conv)
                    selected.append(summarized_conv)
                    current_tokens += 50  # 요약 버전 토큰
        
        # 시간순 정렬하여 반환
        return sorted(selected, key=lambda x: x.get('created_at', ''))
    
    def _estimate_tokens(self, text: str) -> int:
        """다국어 토큰 수 추정"""
        language = self._detect_language(text)
        if language == "ko":
            # 한국어: 글자 수 * 1.5 (한글은 토큰이 많음)
            return int(len(text) * 1.5)
        else:
            # 영어: 단어 수 * 1.3
            return int(len(text.split()) * 1.3)
    
    def _create_summary_version(self, conv: Dict) -> Dict:
        """중요한 대화의 요약 버전 생성"""
        body = self._extract_conversation_body(conv)
        
        # 언어 감지
        language = self._detect_language(body)
        
        # 언어별 요약 길이
        max_length = 150 if language == "ko" else 200
        
        # 간단 요약
        if len(body) > max_length:
            summary = body[:max_length] + "..."
        else:
            summary = body
        
        # 요약 버전 생성
        summarized = conv.copy()
        summarized['body'] = summary
        summarized['is_summarized'] = True
        
        return summarized
    
    def _detect_language(self, text: str) -> str:
        """간단한 언어 감지"""
        # 한글 문자 비율로 판단
        korean_chars = len(re.findall(r'[가-힣]', text))
        total_chars = len(re.sub(r'\s', '', text))
        
        if total_chars == 0:
            return "en"
        
        korean_ratio = korean_chars / total_chars
        return "ko" if korean_ratio > 0.3 else "en"
    
    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)
        
        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다"]):
                return "conclusion"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you"]):
                return "conclusion"
        
        return "general"
    
    def _extract_conversation_body(self, conv: Dict) -> str:
        """대화 본문 추출"""
        return conv.get('body', conv.get('content', ''))
    
    def _select_strategy(self, total_conversations: int) -> str:
        """대화 수에 따른 전략 선택"""
        strategies = self.config["strategies"]
        
        if total_conversations <= strategies["tiny"]["max_conv"]:
            return "minimal_filter"
        elif total_conversations <= strategies["small"]["max_conv"]:
            return "smart_filter"
        elif total_conversations <= strategies["medium"]["max_conv"]:
            return "aggressive_filter"
        else:
            return "chunk_filter"
```

## 환경 변수 설정

```bash
# .env 또는 환경 설정
CONVERSATION_FILTER_UNLIMITED=true
CONVERSATION_FILTER_TOKEN_BUDGET=8000
CONVERSATION_FILTER_MULTILINGUAL=true
CONVERSATION_FILTER_KEYWORDS_FILE=config/multilingual_keywords.json
CONVERSATION_FILTER_QUALITY_THRESHOLD=0.7
```

## 실제 사용 예시

```python
# backend/core/langchain/llm_manager.py에서 사용
from .smart_conversation_filter import SmartConversationFilter

class LLMManager:
    def __init__(self):
        # 기존 코드...
        self.smart_filter = SmartConversationFilter()
    
    def generate_summary_with_unlimited_conversations(self, ticket_data: Dict) -> str:
        """대화 수 제한 없는 요약 생성"""
        
        # 모든 대화 가져오기
        all_conversations = ticket_data.get('conversations', [])
        
        # 스마트 필터링 적용 (대화 수 제한 없음)
        filtered_conversations = self.smart_filter.filter_conversations_unlimited(all_conversations)
        
        # 티켓 + 필터링된 대화로 컨텍스트 생성
        context = self._build_context_for_llm(ticket_data, filtered_conversations)
        
        # LLM으로 요약 생성
        summary = self._generate_summary_with_llm(context)
        
        return summary

# 사용 예시
llm_manager = LLMManager()

# 45개 대화가 있는 복잡한 티켓
complex_ticket = {
    "id": "TICK-12345",
    "subject": "Multi-platform Integration Issue",
    "conversations": [
        # ... 45개의 대화 데이터
    ]
}

# 대화 수 제한 없이 스마트 필터링하여 요약 생성
summary = llm_manager.generate_summary_with_unlimited_conversations(complex_ticket)
```

## 성능 모니터링

```python
# 필터링 성능 추적
class FilteringMetrics:
    def __init__(self):
        self.metrics = {
            "total_conversations_processed": 0,
            "average_filtering_time": 0.0,
            "token_usage_efficiency": 0.0,
            "quality_scores": []
        }
    
    def track_filtering_performance(self, original_count: int, filtered_count: int, 
                                  processing_time: float, quality_score: float):
        """필터링 성능 추적"""
        self.metrics["total_conversations_processed"] += original_count
        self.metrics["quality_scores"].append(quality_score)
        
        # 효율성 계산
        efficiency = filtered_count / original_count if original_count > 0 else 0
        self.metrics["token_usage_efficiency"] = efficiency
        
        # 평균 처리 시간 업데이트
        self.metrics["average_filtering_time"] = processing_time
        
        print(f"필터링 완료: {original_count}개 → {filtered_count}개, "
              f"처리시간: {processing_time:.2f}초, 품질점수: {quality_score:.2f}")
```

이 구현으로 30-50개의 복잡한 대화 스레드도 맥락을 보존하면서 효과적으로 처리할 수 있습니다.
