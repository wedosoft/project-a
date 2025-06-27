---
applyTo: "backend/core/**,backend/api/**"
priority: "high"
domain: "llm-conversation-filtering"
---

# 🧠 LLM 대화 필터링 전략 지침서

_AI 참조 최적화 버전 - LLM 요약 생성 시 대화 필터링 개선 전략_

## 🚀 **TL;DR - 핵심 전략 요약**

### 💡 **즉시 참조용 핵심 포인트**

**기존 문제점**:

- 5개 대화 제한으로 인한 맥락 손실
- 다국어 환경 미고려 (한국어/영어 혼재)
- 단순한 최신순 선택의 한계

**해결 전략**:

- 대화 수 제한 제거 + 3단계 스마트 필터링
- 다국어 키워드 패턴 기반 중요도 평가
- 토큰 예산 내 최적 선택 알고리즘

**핵심 원칙**:

- **맥락 보존 우선**: 노이즈 제거는 부차적
- **언어별 맞춤**: 한국어/영어 다른 필터링 규칙
- **적응형 선택**: 티켓 복잡도에 따른 동적 조정

---

## 📋 **현재 상황 분석**

### **기존 대화 처리 로직의 한계**

```python
# 현재: backend/core/langchain/llm_manager.py:730-750
if len(sorted_conversations) > 5:
    # 최근 5개 대화만 포함 - 맥락 손실 발생!
    recent_conversations = sorted_conversations[-5:]
```

**문제점**:

1. **맥락 단절**: 초기 문제 정의와 최종 해결 과정 누락
2. **다국어 미고려**: 한국어/영어 혼재 환경에서 부적절한 선택
3. **경직된 제한**: 티켓 복잡도와 무관한 고정된 5개 제한

---

## 🎯 **3단계 스마트 필터링 전략**

### **1단계: 기본 노이즈 제거 (Pre-filtering)**

#### **다국어 노이즈 패턴**

```python
NOISE_PATTERNS = {
    "ko": {
        "auto_responses": ["감사합니다", "티켓이 접수되었습니다", "자동 응답"],
        "simple_greetings": ["안녕하세요", "수고하세요", "실례합니다"],
        "system_messages": ["첨부파일", "상태 변경", "우선순위 변경"]
    },
    "en": {
        "auto_responses": ["thank you", "ticket has been", "auto", "acknowledged"],
        "simple_greetings": ["hello", "hi", "thanks", "regards"],
        "system_messages": ["attachment", "status changed", "priority", "assigned"]
    }
}
```

#### **중복 제거 로직**

- 85% 이상 유사도 대화 병합
- 첫 100자 해시 기반 중복 탐지
- 의미 있는 길이 기준: 한국어 10자, 영어 20자

### **2단계: 지능형 중요도 평가 (Smart Scoring)**

#### **다국어 중요도 키워드**

```python
IMPORTANCE_KEYWORDS = {
    "ko": {
        "high": {
            "problem": ["문제", "오류", "에러", "안됩니다", "작동하지", "실패"],
            "solution": ["해결", "방법", "시도해보세요", "설정", "확인해주세요"],
            "escalation": ["긴급", "심각", "즉시", "빨리", "우선순위"]
        },
        "medium": {
            "feedback": ["해결됐습니다", "여전히", "다시", "추가로"],
            "info": ["스크린샷", "로그", "버전", "환경", "재현"]
        }
    },
    "en": {
        "high": {
            "problem": ["issue", "error", "problem", "not working", "failed"],
            "solution": ["solution", "try", "please check", "configure", "resolve"],
            "escalation": ["urgent", "critical", "immediately", "asap", "priority"]
        },
        "medium": {
            "feedback": ["resolved", "still", "again", "additional", "another"],
            "info": ["screenshot", "log", "version", "environment", "reproduce"]
        }
    }
}
```

#### **중요도 점수 계산**

- **기본 점수**: 0.4 (베이스라인)
- **길이 점수**: 언어별 적정 길이 고려
- **키워드 점수**: 중요도별 가중치 (고: 1.0, 중: 0.6, 저: -0.2)
- **위치 점수**: 시작/끝 부분 높은 가중치
- **연결성 점수**: 이전 대화와의 맥락 연결성

### **3단계: 토큰 예산 기반 최적 선택 (Token-aware Selection)**

#### **선택 전략**

1. **필수 대화 우선**: problem_definition, solution, conclusion
2. **중요도순 선택**: 남은 예산으로 점수 높은 순
3. **적응형 요약**: 중요하지만 예산 초과 시 요약 포함

#### **토큰 추정 공식**

```python
def estimate_tokens(text: str, language: str) -> int:
    if language == "ko":
        return int(len(text) * 1.5)  # 한글은 토큰이 많음
    else:
        return int(len(text.split()) * 1.3)  # 영어 단어 기준
```

---

## 🔧 **구현 패턴**

### **핵심 필터링 함수 시그니처**

```python
def filter_conversations_unlimited(self, conversations: List[Dict]) -> List[Dict]:
    """
    대화 수 제한 없는 스마트 필터링
    - 30-50개 대화도 효과적 처리
    - 다국어 지원 (한국어/영어)
    - 맥락 보존 우선
    """

def _calculate_importance_score(self, conv: Dict) -> float:
    """다국어 중요도 점수 계산 (0.0 ~ 1.0)"""

def _detect_language(self, text: str) -> str:
    """한글 문자 비율로 언어 감지"""
    korean_chars = len(re.findall(r'[가-힣]', text))
    total_chars = len(re.sub(r'\s', '', text))
    korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
    return "ko" if korean_ratio > 0.3 else "en"
```

### **환경 변수 설정**

```bash
# 필터링 활성화
CONVERSATION_FILTERING_ENABLED=true
CONVERSATION_FILTERING_STRATEGY=smart

# 다국어 키워드 파일
MULTILINGUAL_KEYWORDS_PATH=backend/config/multilingual_keywords.json

# 토큰 예산 및 품질 임계값
CONVERSATION_TOKEN_BUDGET=8000
CONVERSATION_IMPORTANCE_THRESHOLD=0.3
```

---

## 🎯 **적용 우선순위**

### **Phase 1: 즉시 적용 (1주)**

- 기본 노이즈 제거 패턴 적용
- 다국어 키워드 파일 생성
- 기존 5개 제한 제거

### **Phase 2: 스마트 필터링 (2주)**

- 중요도 점수 기반 선택
- 토큰 예산 관리
- 성능 모니터링

### **Phase 3: 고도화 (1개월)**

- AI 기반 중요도 평가
- 자동 학습 기반 개선
- 도메인별 맞춤 필터링

---

## ⚠️ **주의사항 및 함정**

### **다국어 처리 주의점**

- 한국어 조사/어미 변형 고려
- 영어 단복수/시제 변형 고려
- 코드 스위칭(언어 혼용) 대응

### **성능 최적화**

- 키워드 패턴 캐싱 필수
- 정규식 컴파일 최적화
- 대화 수가 많을 때 메모리 관리

### **품질 보장**

- 중요 맥락 누락 모니터링
- 필터링 전후 품질 비교
- 사용자 피드백 기반 개선

---

## 📊 **성공 지표 (KPI)**

### **정량적 지표**

- **필터링 효율성**: 30~50개 → 10~15개 효과적 축소
- **맥락 보존률**: 중요 정보 95% 이상 보존
- **처리 속도**: 기존 대비 50% 이상 단축
- **토큰 절약**: LLM 비용 30% 이상 절약

### **정성적 지표**

- **요약 품질**: 사용자 만족도 개선
- **시스템 안정성**: 에러율 1% 미만
- **확장성**: 다른 언어 추가 용이성
- **유지보수성**: 키워드 패턴 업데이트 용이성
