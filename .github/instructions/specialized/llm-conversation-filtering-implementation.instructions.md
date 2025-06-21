---
applyTo: "backend/core/**,backend/api/**"
priority: "high"
domain: "llm-conversation-filtering"
---

# 🛠️ LLM 대화 필터링 구현 지침서

_AI 참조 최적화 버전 - 스마트 대화 필터링 시스템 실제 구현 가이드_

## 🚀 **TL;DR - 핵심 구현 패턴**

### 💡 **즉시 참조용 구현 포인트**

**핵심 클래스**:

- `SmartConversationFilter`: 메인 필터링 엔진
- `MultilinguualKeywordManager`: 다국어 키워드 관리
- `TokenBudgetOptimizer`: 토큰 예산 최적화

**주요 함수**:

- `filter_conversations_unlimited()`: 대화 수 제한 없는 메인 필터링
- `_calculate_importance_score()`: 다국어 중요도 점수 계산
- `_select_within_token_budget()`: 토큰 예산 내 최적 선택

**설정 파일**:

- `backend/config/multilingual_keywords.json`: 메인 다국어 키워드
- `backend/config/conversation_filter_config.json`: 필터링 설정

---

## 🏗️ **핵심 클래스 구현**

### **SmartConversationFilter 클래스**

```python
# backend/core/langchain/smart_conversation_filter.py
import json
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging

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
        self.logger = logging.getLogger(__name__)

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
            full_path = Path(__file__).parent.parent.parent / config_path
            with open(full_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"키워드 파일 없음: {config_path}, 기본 패턴 사용")
            return self._get_default_patterns()

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
            return self._smart_filtering_pipeline(conversations)
        elif strategy == "aggressive_filter":
            return self._aggressive_filtering_pipeline(conversations)
        else:  # chunk_filter
            return self._chunk_based_filtering(conversations)

    def _smart_filtering_pipeline(self, conversations: List[Dict]) -> List[Dict]:
        """스마트 필터링 파이프라인 (25-50개 대화)"""

        # Step 1: 노이즈 제거
        cleaned_conversations = self._remove_basic_noise(conversations)
        self.logger.debug(f"노이즈 제거 후: {len(cleaned_conversations)}개")

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
        selected = self._select_within_token_budget(scored_conversations)
        self.logger.info(f"최종 선택: {len(selected)}개 대화")

        return selected

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
        korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
        return "ko" if korean_ratio > 0.3 else "en"

    def _classify_conversation_type(self, conv: Dict) -> str:
        """대화 유형 분류"""
        body = self._extract_conversation_body(conv).lower()
        language = self._detect_language(body)

        # 언어별 패턴 매칭
        if language == "ko":
            if any(word in body for word in ["문제", "오류", "에러", "안됩니다", "고장"]):
                return "problem_definition"
            elif any(word in body for word in ["해결", "방법", "시도", "확인해보세요"]):
                return "solution"
            elif any(word in body for word in ["해결됐습니다", "완료", "감사합니다", "닫기"]):
                return "conclusion"
        else:  # English
            if any(word in body for word in ["issue", "problem", "error", "not working"]):
                return "problem_definition"
            elif any(word in body for word in ["solution", "try", "fix", "resolve"]):
                return "solution"
            elif any(word in body for word in ["resolved", "fixed", "thank you", "close"]):
                return "conclusion"

        return "general"

    def _extract_conversation_body(self, conv: Dict) -> str:
        """대화 본문 추출"""
        return conv.get('body', conv.get('content', ''))

    def _select_strategy(self, total_conversations: int) -> str:
        """대화 수에 따른 전략 선택"""
        if total_conversations <= 10:
            return "minimal_filter"
        elif total_conversations <= 25:
            return "smart_filter"
        elif total_conversations <= 50:
            return "aggressive_filter"
        else:
            return "chunk_filter"

    def _get_default_patterns(self) -> Dict:
        """기본 키워드 패턴 반환"""
        return {
            "ko": {
                "high_importance": {
                    "problem_indicators": ["문제", "오류", "에러", "안됩니다", "작동하지"],
                    "solution_indicators": ["해결", "방법", "시도해보세요", "확인해주세요"],
                    "escalation_indicators": ["긴급", "심각", "즉시", "빨리"]
                },
                "low_importance": {
                    "noise_patterns": ["감사합니다", "안녕하세요", "수고하세요"]
                }
            },
            "en": {
                "high_importance": {
                    "problem_indicators": ["issue", "error", "problem", "not working"],
                    "solution_indicators": ["solution", "try", "please check", "resolve"],
                    "escalation_indicators": ["urgent", "critical", "immediately"]
                },
                "low_importance": {
                    "noise_patterns": ["thank you", "hello", "hi", "regards"]
                }
            }
        }

    # 추가 헬퍼 메서드들
    def _remove_basic_noise(self, conversations: List[Dict]) -> List[Dict]:
        """기본 노이즈 제거"""
        # 구현 로직...
        pass

    def _calculate_position_weight(self, index: int, total: int) -> float:
        """위치 기반 가중치"""
        # 구현 로직...
        pass

    def _calculate_context_continuity(self, conv: Dict, all_conversations: List[Dict], index: int) -> float:
        """컨텍스트 연결성"""
        # 구현 로직...
        pass
```

---

## 📁 **설정 파일 구조**

### **다국어 키워드 파일 (multilingual_keywords.json)**

```json
{
  "ko": {
    "high_importance": {
      "problem_indicators": [
        "문제",
        "오류",
        "에러",
        "버그",
        "고장",
        "안됩니다",
        "작동하지 않습니다",
        "실패",
        "에러가 발생",
        "문제가 있습니다",
        "이상합니다"
      ],
      "solution_indicators": [
        "해결",
        "해결방법",
        "방법",
        "시도해보세요",
        "확인해주세요",
        "설정",
        "수정",
        "고치기",
        "해결책",
        "조치"
      ],
      "escalation_indicators": [
        "긴급",
        "심각",
        "즉시",
        "빨리",
        "우선순위",
        "중요",
        "급합니다"
      ]
    },
    "medium_importance": {
      "user_feedback": [
        "해결됐습니다",
        "해결되었습니다",
        "여전히",
        "아직도",
        "다시",
        "추가로",
        "또",
        "그런데",
        "하지만"
      ],
      "additional_info": [
        "스크린샷",
        "로그",
        "로그파일",
        "버전",
        "환경",
        "재현",
        "단계",
        "첨부파일",
        "이미지"
      ]
    },
    "low_importance": {
      "auto_responses": [
        "감사합니다",
        "티켓이 접수되었습니다",
        "자동 응답",
        "자동으로",
        "시스템에서",
        "확인했습니다"
      ],
      "simple_greetings": [
        "안녕하세요",
        "수고하세요",
        "실례합니다",
        "죄송합니다",
        "번거롭게",
        "안녕히"
      ]
    }
  },
  "en": {
    "high_importance": {
      "problem_indicators": [
        "issue",
        "error",
        "problem",
        "bug",
        "not working",
        "failed",
        "unable",
        "cannot",
        "doesn't work",
        "broken",
        "crash"
      ],
      "solution_indicators": [
        "solution",
        "fix",
        "resolve",
        "try",
        "please check",
        "configure",
        "setting",
        "workaround",
        "troubleshoot"
      ],
      "escalation_indicators": [
        "urgent",
        "critical",
        "immediately",
        "asap",
        "priority",
        "important",
        "escalate"
      ]
    },
    "medium_importance": {
      "user_feedback": [
        "resolved",
        "fixed",
        "still",
        "again",
        "additional",
        "another",
        "however",
        "but",
        "also"
      ],
      "additional_info": [
        "screenshot",
        "log",
        "version",
        "environment",
        "reproduce",
        "steps",
        "attachment",
        "image",
        "file"
      ]
    },
    "low_importance": {
      "auto_responses": [
        "thank you",
        "ticket has been",
        "auto",
        "automatic",
        "system",
        "acknowledged",
        "received"
      ],
      "simple_greetings": [
        "hello",
        "hi",
        "thanks",
        "regards",
        "best",
        "sincerely"
      ]
    }
  }
}
```

---

## 🔗 **LLMManager 통합**

### **기존 LLMManager에 통합하는 방법**

```python
# backend/core/langchain/llm_manager.py에서 사용
from .smart_conversation_filter import SmartConversationFilter

class LLMManager:
    def __init__(self):
        # ...기존 코드...
        self.smart_filter = SmartConversationFilter()

    def generate_summary_with_unlimited_conversations(self, ticket_data: Dict) -> str:
        """대화 수 제한 없는 요약 생성"""
        conversations = ticket_data.get('conversations', [])

        # 스마트 필터링 적용
        filtered_conversations = self.smart_filter.filter_conversations_unlimited(conversations)

        # 기존 요약 생성 로직 사용
        return self._generate_summary_from_conversations(ticket_data, filtered_conversations)

    def _generate_summary_from_conversations(self, ticket_data: Dict, conversations: List[Dict]) -> str:
        """필터링된 대화로 요약 생성"""
        # 기존 요약 생성 로직 재사용
        # ...
```

---

## 🔧 **환경 변수 설정**

```bash
# .env 또는 환경 설정
CONVERSATION_FILTER_UNLIMITED=true
CONVERSATION_FILTER_TOKEN_BUDGET=8000
CONVERSATION_FILTER_MULTILINGUAL=true
CONVERSATION_FILTER_KEYWORDS_FILE=config/multilingual_keywords.json
CONVERSATION_FILTER_QUALITY_THRESHOLD=0.7

# 언어별 최소 길이
CONVERSATION_MIN_LENGTH_KO=10
CONVERSATION_MIN_LENGTH_EN=20

# 필터링 로그 레벨
CONVERSATION_FILTER_LOG_LEVEL=INFO
```

---

## 📊 **성능 모니터링**

### **필터링 메트릭 클래스**

```python
class FilteringMetrics:
    def __init__(self):
        self.metrics = {
            "total_conversations": 0,
            "filtered_conversations": 0,
            "processing_time": 0.0,
            "token_usage": 0,
            "language_distribution": {"ko": 0, "en": 0},
            "filtering_ratio": 0.0
        }

    def track_filtering_performance(self,
                                  original_count: int,
                                  filtered_count: int,
                                  processing_time: float,
                                  token_usage: int,
                                  languages: Dict[str, int]):
        """필터링 성능 추적"""
        self.metrics.update({
            "total_conversations": original_count,
            "filtered_conversations": filtered_count,
            "processing_time": processing_time,
            "token_usage": token_usage,
            "language_distribution": languages,
            "filtering_ratio": filtered_count / original_count if original_count > 0 else 0
        })

    def get_performance_report(self) -> Dict:
        """성능 리포트 생성"""
        return self.metrics.copy()
```

---

## ⚠️ **구현 시 주의사항**

### **메모리 관리**

- 대화 수가 많을 때 메모리 효율성 고려
- 키워드 패턴 캐싱으로 성능 최적화
- 정규식 컴파일 최적화

### **에러 처리**

- 키워드 파일 로드 실패 시 기본 패턴 사용
- 언어 감지 실패 시 영어로 기본 처리
- 토큰 예산 초과 시 적절한 폴백

### **확장성**

- 새로운 언어 추가 용이하게 설계
- 키워드 패턴 동적 업데이트 지원
- 도메인별 맞춤 필터링 확장 가능

이 구현으로 30-50개의 복잡한 대화 스레드도 맥락을 보존하면서 효과적으로 처리할 수 있습니다.
