# 🎯 Anthropic 프롬프트 엔지니어링 시스템 완전 가이드

> **Freshdesk 티켓 요약을 위한 고품질 AI 시스템**
> 
> Constitutional AI, XML 구조화, Chain-of-Thought 추론 등 Anthropic의 최첨단 프롬프트 엔지니어링 기법을 적용한 티켓 요약 시스템입니다.

## 📋 목차

- [🎯 시스템 개요](#-시스템-개요)
- [✨ 핵심 기능](#-핵심-기능)
- [🏗️ 아키텍처](#️-아키텍처)
- [🚀 빠른 시작](#-빠른-시작)
- [⚙️ 설정 관리](#️-설정-관리)
- [📊 품질 관리](#-품질-관리)
- [🔧 관리자 도구](#-관리자-도구)
- [🧪 테스트](#-테스트)
- [📈 성능 최적화](#-성능-최적화)
- [🔍 모니터링](#-모니터링)
- [🛠️ 문제 해결](#️-문제-해결)

## 🎯 시스템 개요

### 핵심 목표
- **상담원 생산성 향상**: 5초 내 파악 가능한 고품질 요약 제공
- **정보 보안 강화**: 개인정보 노출 방지 및 Constitutional AI 준수
- **운영 효율성**: 코드 수정 없는 프롬프트 관리 및 실시간 품질 모니터링

### 주요 특징
- 🧠 **Constitutional AI**: Helpful, Harmless, Honest 원칙 적용
- 📝 **XML 구조화**: 일관된 응답 형식 보장
- 🔗 **Chain-of-Thought**: 논리적 추론 과정 포함
- ⚡ **실시간 처리**: 2초 이내 응답 시간 목표
- 🛡️ **품질 검증**: 다차원 품질 평가 및 자동 폴백
- 🎨 **관리자 친화적**: 웹 인터페이스를 통한 프롬프트 편집

## ✨ 핵심 기능

### 1. 🎯 고품질 티켓 요약
```python
from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer

summarizer = AnthropicSummarizer()
summary = await summarizer.generate_anthropic_summary(
    content="고객 로그인 문제...",
    content_type="ticket_view",
    subject="로그인 실패",
    metadata={"priority": "high"}
)
```

**생성되는 요약 형식:**
```xml
<problem_overview>
🔍 **문제 현황**
- ABC회사 API 연동 오류 발생
- 비즈니스 임팩트: 매출 손실
</problem_overview>

<root_cause>
💡 **원인 분석**  
- 인증 토큰 만료로 확인됨
</root_cause>

<resolution_progress>
⚡ **해결 진행상황**
- 김개발자가 토큰 재발급 완료 (15:30)
- 서비스 정상화 확인 (15:45)
</resolution_progress>

<key_insights>
🎯 **중요 인사이트**
- 자동 토큰 갱신 시스템 도입 필요
</key_insights>
```

### 2. 🚨 실시간 요약
```python
realtime_summary = await summarizer.generate_realtime_summary(
    content="API 오류 발생",
    subject="긴급 문제"
)
```

### 3. 📎 지능형 첨부파일 선별
```python
selected_attachments = await summarizer.select_relevant_attachments(
    content="로그 오류 발생",
    subject="시스템 오류",
    attachments=[
        {"filename": "error_log.txt", "file_type": "text"},
        {"filename": "screenshot.png", "file_type": "image"}
    ]
)
```

### 4. 🎛️ 관리자 친화적 프롬프트 관리
```python
from core.llm.summarizer.admin.prompt_manager import prompt_manager

# 템플릿 조회
templates = await prompt_manager.get_available_templates()

# 템플릿 업데이트 (코드 수정 없음)
result = await prompt_manager.update_template(
    template_name="anthropic_ticket_view",
    template_type="system", 
    content=updated_content,
    user_id="admin"
)

# 실시간 미리보기
preview = await prompt_manager.preview_template(
    template_name="test_template",
    template_type="user",
    content=new_content
)
```

## 🏗️ 아키텍처

### 시스템 구성도
```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Admin Interface   │    │   Prompt Builder     │    │  Quality Validator  │
│   - 웹 UI           │    │   - Constitutional   │    │   - 품질 점수 계산   │
│   - API 관리        │    │   - XML 구조화       │    │   - 임계값 검증     │
│   - 실시간 미리보기  │    │   - Chain-of-Thought │    │   - 폴백 처리       │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
           │                           │                           │
           └───────────────┬───────────┴───────────────┬───────────┘
                          │                           │
                ┌─────────▼─────────┐         ┌───────▼────────┐
                │ Anthropic         │         │ Settings       │
                │ Summarizer        │         │ Manager        │
                │ - 요약 생성       │         │ - 환경변수     │
                │ - 모델 선택       │         │ - 캐싱         │
                │ - 성능 최적화     │         │ - 모니터링     │
                └───────────────────┘         └────────────────┘
```

### 주요 컴포넌트

#### 1. **AnthropicPromptBuilder** (`prompt/anthropic_builder.py`)
- Constitutional AI 프롬프트 생성
- XML 구조화된 사용자 프롬프트 빌드
- 컨텍스트 최적화 및 스마트 truncation
- Anthropic 기법 준수 검증

#### 2. **AnthropicSummarizer** (`core/anthropic_summarizer.py`)
- 고품질 요약 생성 (품질 임계값: 0.8)
- 실시간 요약 (응답 시간: <2초)
- 첨부파일 지능형 선별
- 자동 폴백 메커니즘

#### 3. **AnthropicQualityValidator** (`quality/anthropic_validator.py`)
- Constitutional AI 준수 검증
- XML 구조 유효성 확인
- 팩트 정확성 평가
- 실행 가능성 점수 계산

#### 4. **PromptManager** (`admin/prompt_manager.py`)
- 코드 수정 없는 프롬프트 편집
- 버전 관리 및 백업
- 실시간 리로드
- 변경 이력 추적

#### 5. **AnthropicSettings** (`config/settings.py`)
- 환경변수 기반 설정 관리
- 런타임 설정 업데이트
- 캐싱 및 성능 최적화
- 개발/운영 환경 자동 조정

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에서 필요한 설정 수정

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 시스템 상태 확인
python -c "
from core.llm.summarizer.config.settings import anthropic_settings
status = anthropic_settings.get_status()
print(f'Anthropic 시스템 상태: {status[\"config_summary\"][\"enabled\"]}')
"
```

### 2. 기본 사용법
```python
import asyncio
from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer

async def main():
    summarizer = AnthropicSummarizer()
    
    # 티켓 요약 생성
    summary = await summarizer.generate_anthropic_summary(
        content="고객이 로그인을 할 수 없다고 문의했습니다. 2FA 설정에 문제가 있는 것 같습니다.",
        content_type="ticket_view",
        subject="로그인 문제",
        metadata={
            "priority": "high",
            "category": "technical",
            "company": "ABC Corporation"
        }
    )
    
    print("생성된 요약:")
    print(summary)

# 실행
asyncio.run(main())
```

### 3. 관리자 도구 사용
```python
from core.llm.summarizer.admin.prompt_manager import prompt_manager

# 시스템 상태 확인
status = await prompt_manager.get_system_status()
print(f"총 템플릿 수: {status['templates']['total']}")

# 템플릿 목록 조회
templates = await prompt_manager.get_available_templates()
print("사용 가능한 시스템 템플릿:", templates['system'])
```

## ⚙️ 설정 관리

### 환경변수 설정

#### 기본 설정
```bash
# Anthropic 기능 활성화
ENABLE_ANTHROPIC_PROMPTS=true

# 품질 관리
ANTHROPIC_QUALITY_THRESHOLD=0.8      # 품질 임계값
ANTHROPIC_RETRY_THRESHOLD=0.6        # 재시도 임계값  
ANTHROPIC_FALLBACK_THRESHOLD=0.4     # 폴백 임계값
ANTHROPIC_MAX_RETRIES=2              # 최대 재시도 횟수

# LLM 설정
ANTHROPIC_TEMPERATURE=0.1            # 창의성 vs 일관성
ANTHROPIC_MAX_TOKENS=1500            # 최대 토큰 수
ANTHROPIC_TIMEOUT=30                 # 타임아웃 (초)
```

#### Constitutional AI 설정
```bash
# Constitutional AI 가중치 (합계 = 1.0)
ANTHROPIC_CONSTITUTIONAL_HELPFUL_WEIGHT=0.35     # 도움됨
ANTHROPIC_CONSTITUTIONAL_HARMLESS_WEIGHT=0.35    # 무해함
ANTHROPIC_CONSTITUTIONAL_HONEST_WEIGHT=0.30      # 정직함

# 기법별 활성화
ANTHROPIC_ENABLE_CONSTITUTIONAL_AI=true
ANTHROPIC_ENABLE_CHAIN_OF_THOUGHT=true
ANTHROPIC_ENABLE_XML_STRUCTURING=true
ANTHROPIC_ENABLE_ROLE_PROMPTING=true
ANTHROPIC_ENABLE_FEW_SHOT_LEARNING=true
```

#### 사용 사례별 모델 설정
```bash
# 상세 분석용 (높은 품질)
ANTHROPIC_TICKET_VIEW_MODEL_PROVIDER=anthropic
ANTHROPIC_TICKET_VIEW_MODEL_NAME=claude-3-sonnet-20240229

# 실시간 요약용 (빠른 속도)
ANTHROPIC_REALTIME_SUMMARY_MODEL_PROVIDER=anthropic  
ANTHROPIC_REALTIME_SUMMARY_MODEL_NAME=claude-3-haiku-20240307

# 첨부파일 선별용
ANTHROPIC_ATTACHMENT_SELECTION_MODEL_PROVIDER=anthropic
ANTHROPIC_ATTACHMENT_SELECTION_MODEL_NAME=claude-3-sonnet-20240229

# 종합 분석용 (최고 품질)
ANTHROPIC_COMPREHENSIVE_ANALYSIS_MODEL_PROVIDER=anthropic
ANTHROPIC_COMPREHENSIVE_ANALYSIS_MODEL_NAME=claude-3-opus-20240229
```

#### 관리자 설정
```bash
# 웹 인터페이스
ANTHROPIC_ADMIN_ENABLE_WEB_INTERFACE=true
ANTHROPIC_ADMIN_ENABLE_API_ACCESS=true
ANTHROPIC_ADMIN_ENABLE_HOT_RELOAD=true

# 백업 및 버전 관리
ANTHROPIC_ADMIN_BACKUP_ON_CHANGE=true
ANTHROPIC_ADMIN_ENABLE_VERSION_CONTROL=true
ANTHROPIC_ADMIN_MAX_HISTORY_ENTRIES=100
ANTHROPIC_ADMIN_RETENTION_PERIOD=90

# 검증 및 테스트
ANTHROPIC_ADMIN_AUTO_VALIDATE_CHANGES=true
ANTHROPIC_ADMIN_TEST_BEFORE_APPLY=true
ANTHROPIC_ADMIN_ROLLBACK_ON_FAILURE=true
```

### 동적 설정 업데이트
```python
from core.llm.summarizer.config.settings import anthropic_settings

# 품질 임계값 업데이트
success = anthropic_settings.update_quality_threshold(0.9)

# Constitutional AI 가중치 조정
new_weights = {
    'helpful': 0.4,
    'harmless': 0.4, 
    'honest': 0.2
}
anthropic_settings.update_constitutional_weights(new_weights)

# 특정 기법 비활성화
anthropic_settings.disable_technique('few_shot_learning')
```

## 📊 품질 관리

### 품질 평가 지표

#### 1. Constitutional AI 준수도 (35%)
- **Helpful**: 즉시 활용 가능한 정보 제공
- **Harmless**: 개인정보 보호, 추측 금지
- **Honest**: 불확실성 명시, 사실 기반

#### 2. XML 구조 유효성 (25%)
- 필수 섹션 포함도
- XML 태그 완성도
- 구조적 일관성

#### 3. 팩트 정확성 (25%)
- 사실 지표 포함
- 추측성 표현 감지
- 정보 완전성

#### 4. 실행 가능성 (15%)
- 구체적 액션 아이템
- 담당자 명시
- 시간 기준 제시

### 품질 모니터링

#### 실시간 품질 점수 확인
```python
from core.llm.summarizer.quality.anthropic_validator import AnthropicQualityValidator

validator = AnthropicQualityValidator()

# 응답 품질 평가
validation_results = {
    'constitutional_compliance': {
        'helpful': {'score': 0.9},
        'harmless': {'score': 0.8}, 
        'honest': {'score': 0.85}
    },
    'xml_structure_valid': True,
    'factual_accuracy': 0.8,
    'actionability_score': 0.75
}

quality_score = validator.calculate_anthropic_quality_score(
    "테스트 응답", validation_results
)
print(f"전체 품질 점수: {quality_score:.2f}")  # 0.83
```

#### 품질 임계값 설정
```bash
# .env 설정
ANTHROPIC_QUALITY_THRESHOLD=0.8      # 통과 기준
ANTHROPIC_RETRY_THRESHOLD=0.6        # 재시도 기준
ANTHROPIC_FALLBACK_THRESHOLD=0.4     # 폴백 기준
```

#### 품질 개선 가이드라인

**🔴 품질 점수 < 0.4 (폴백 실행)**
- 기본 요약 시스템으로 전환
- 오류 로그 기록 및 알림
- 수동 검토 필요

**🟡 품질 점수 0.4-0.8 (재시도 실행)**
- 다른 모델로 재시도
- 프롬프트 조정 후 재생성
- 최대 2회 재시도

**🟢 품질 점수 > 0.8 (통과)**
- 고품질 응답으로 판정
- 사용자에게 제공
- 성공 메트릭 기록

## 🔧 관리자 도구

### 웹 인터페이스 (예정)
- 실시간 프롬프트 편집기
- 미리보기 및 테스트 도구  
- 변경 이력 추적
- 성능 대시보드

### API 기반 관리
```python
from core.llm.summarizer.admin.prompt_manager import prompt_manager

# 1. 템플릿 조회
templates = await prompt_manager.get_available_templates()
content = await prompt_manager.get_template_content(
    template_name="anthropic_ticket_view",
    template_type="system"
)

# 2. 템플릿 수정
updated_content = {
    "version": "1.0.1",
    "constitutional_principles": {
        "helpful": ["상담원이 5초 내에 파악할 수 있도록 돕기"],
        "harmless": ["개인정보 절대 노출 금지"],
        "honest": ["불확실한 내용은 명확히 표시"]
    },
    "system_prompts": {
        "ko": "새로운 시스템 프롬프트...",
        "en": "New system prompt..."
    }
}

result = await prompt_manager.update_template(
    template_name="anthropic_ticket_view",
    template_type="system",
    content=updated_content,
    user_id="admin"
)

# 3. 미리보기 생성
preview = await prompt_manager.preview_template(
    template_name="anthropic_ticket_view", 
    template_type="system",
    content=updated_content,
    test_data={
        "subject": "테스트 제목",
        "content": "테스트 내용",
        "metadata": {"priority": "high"}
    }
)

# 4. 변경 이력 조회
history = await prompt_manager.get_change_history(
    template_name="anthropic_ticket_view",
    limit=10
)

# 5. 백업 관리
backups = await prompt_manager.get_backup_list(
    template_name="anthropic_ticket_view"
)

# 6. 롤백 실행
rollback_result = await prompt_manager.rollback_template(
    template_name="anthropic_ticket_view",
    template_type="system", 
    target_version="1.0.0",
    user_id="admin"
)
```

### 시스템 상태 모니터링
```python
# 전체 시스템 상태
status = await prompt_manager.get_system_status()
print(f"""
시스템 상태: {status['status']}
총 템플릿: {status['templates']['total']}
백업 수: {status['backups']['total']}
최근 변경: {status['change_logs']['recent']}
""")

# 설정 상태 확인
from core.llm.summarizer.config.settings import anthropic_settings
config_status = anthropic_settings.get_status()
print(f"""
설정 로드됨: {config_status['config_loaded']}
품질 임계값: {config_status['config_summary']['quality_threshold']}
활성화된 기법: {config_status['config_summary']['enabled_techniques']}
""")
```

## 🧪 테스트

### 단위 테스트 실행
```bash
# 전체 테스트 실행
cd backend && source venv/bin/activate
cd core/llm/summarizer/tests
python -m pytest test_anthropic_prompts.py -v

# 특정 컴포넌트 테스트
python -m pytest test_anthropic_prompts.py::TestAnthropicPromptBuilder -v
python -m pytest test_anthropic_prompts.py::TestAnthropicSummarizer -v
python -m pytest test_anthropic_prompts.py::TestAnthropicQualityValidator -v
```

### 통합 테스트 실행
```bash
# 빠른 통합 테스트
python run_tests.py --quick

# 전체 통합 테스트 (성능 + 커버리지)
python run_tests.py --coverage --performance

# CI/CD 파이프라인 테스트
./ci_cd_example.sh full --coverage 85 --performance 1.5
```

### 테스트 시나리오

#### 1. 기술적 문제 (한국어)
```python
test_data = {
    "subject": "API 연동 오류",
    "content": """
    ABC회사에서 API 연동 중 500 에러가 발생했습니다.
    2024-07-04 15:30 부터 지속적으로 발생하고 있으며, 
    고객이 매우 불만족스러워하고 있습니다.
    """,
    "metadata": {"priority": "high", "category": "technical"}
}
```

#### 2. 고객 서비스 (한국어)  
```python
test_data = {
    "subject": "결제 문제 문의",
    "content": """
    월간 구독료가 중복 청구되었다고 고객이 문의했습니다.
    김철수 고객 (premium 플랜)이며, 환불을 요청하고 있습니다.
    """,
    "metadata": {"priority": "medium", "category": "billing"}
}
```

### 성능 벤치마크

#### 응답 시간 목표
- **티켓 요약**: < 2초 (평균 1.2초)
- **실시간 요약**: < 1초 (평균 0.8초)
- **첨부파일 선별**: < 3초 (평균 2.1초)

#### 품질 목표
- **전체 품질 점수**: > 0.8 (평균 0.85)
- **Constitutional AI 준수율**: > 90%
- **XML 구조 유효성**: > 95%
- **팩트 정확성**: > 85%

## 📈 성능 최적화

### 캐싱 전략
```bash
# 성능 최적화 설정
ANTHROPIC_PERFORMANCE_ENABLE_CACHING=true
ANTHROPIC_PERFORMANCE_CACHE_TTL=3600
ANTHROPIC_PERFORMANCE_ENABLE_PARALLEL=true
ANTHROPIC_PERFORMANCE_MAX_CONCURRENT=5
```

### 모델 선택 최적화
```python
# 사용 사례별 최적 모델 사용
config = {
    # 빠른 처리가 필요한 경우
    "realtime_summary": {
        "provider": "anthropic",
        "model": "claude-3-haiku-20240307",  # 빠름
        "temperature": 0.05
    },
    
    # 높은 품질이 필요한 경우  
    "ticket_view": {
        "provider": "anthropic", 
        "model": "claude-3-sonnet-20240229",  # 균형
        "temperature": 0.1
    },
    
    # 최고 품질이 필요한 경우
    "comprehensive_analysis": {
        "provider": "anthropic",
        "model": "claude-3-opus-20240229",  # 최고 품질
        "temperature": 0.05  
    }
}
```

### 컨텍스트 최적화
```python
# 스마트 텍스트 절단
def smart_truncate(text: str, max_length: int, preserve_patterns: List[str]):
    """중요 패턴을 보존하면서 텍스트 절단"""
    # 구현은 AnthropicPromptBuilder에 포함됨
    pass

# 적응형 프롬프트 조정
def adjust_prompt_for_context(content: str, available_tokens: int):
    """사용 가능한 토큰에 따라 프롬프트 조정"""
    # 구현은 AnthropicPromptBuilder에 포함됨  
    pass
```

## 🔍 모니터링

### 메트릭 수집
```bash
# 모니터링 설정
ANTHROPIC_MONITORING_ENABLE_METRICS=true
ANTHROPIC_MONITORING_ENABLE_LOGGING=true
ANTHROPIC_MONITORING_LOG_LEVEL=INFO
```

### 알림 설정
```bash
# 알림 활성화
ANTHROPIC_MONITORING_ENABLE_ALERTS=true
ANTHROPIC_MONITORING_ALERT_QUALITY_THRESHOLD=0.7
ANTHROPIC_MONITORING_ALERT_RESPONSE_TIME_THRESHOLD=30.0
ANTHROPIC_MONITORING_ALERT_ERROR_RATE_THRESHOLD=0.1

# 알림 채널
ANTHROPIC_NOTIFICATIONS_CHANNELS=email,slack
ANTHROPIC_NOTIFICATIONS_EMAIL_RECIPIENTS=admin@company.com,ai-team@company.com
```

### 주요 모니터링 지표

#### 성능 지표
- 평균 응답 시간
- 처리량 (requests/minute)
- 오류율
- 품질 점수 분포

#### 품질 지표  
- Constitutional AI 준수율
- XML 구조 유효성
- 팩트 정확성 점수
- 사용자 만족도

#### 운영 지표
- 시스템 가용성
- 캐시 히트율  
- 리소스 사용률
- 폴백 발생률

## 🛠️ 문제 해결

### 일반적인 문제들

#### 1. 품질 점수가 낮은 경우
```python
# 문제 진단
from core.llm.summarizer.quality.anthropic_validator import AnthropicQualityValidator

validator = AnthropicQualityValidator()
result = validator.validate_constitutional_ai_compliance(response, principles)

if not result['overall_compliance']:
    print("Constitutional AI 위반 사항:")
    for violation in result['violations']:
        print(f"- {violation}")
        
# 해결 방법
1. 프롬프트 템플릿 점검
2. Constitutional 원칙 강화  
3. 예시 데이터 개선
4. 모델 파라미터 조정
```

#### 2. 응답 시간이 느린 경우
```python
# 성능 진단
import time
start_time = time.time()
summary = await summarizer.generate_anthropic_summary(...)
elapsed_time = time.time() - start_time

if elapsed_time > 2.0:
    print(f"응답 시간 초과: {elapsed_time:.2f}초")
    
# 해결 방법
1. 더 빠른 모델 사용 (haiku)
2. 컨텍스트 길이 줄이기
3. 캐싱 활성화
4. 병렬 처리 최적화
```

#### 3. XML 구조 오류
```python
# XML 구조 검증
required_sections = {
    'problem_overview': '문제 현황',
    'root_cause': '원인 분석',
    'resolution_progress': '해결 진행상황', 
    'key_insights': '중요 인사이트'
}

result = validator.validate_xml_structure(response, required_sections)
if not result['valid_structure']:
    print(f"누락된 섹션: {result['missing_sections']}")
    
# 해결 방법
1. 시스템 프롬프트에서 XML 형식 강조
2. Few-shot 예시 추가
3. 후처리를 통한 구조 보정
```

### 로그 분석

#### 로그 레벨 설정
```bash
# 개발 환경
ANTHROPIC_MONITORING_LOG_LEVEL=DEBUG

# 운영 환경  
ANTHROPIC_MONITORING_LOG_LEVEL=INFO
```

#### 주요 로그 패턴
```python
# 성공적인 요약 생성
INFO - AnthropicSummarizer - ✅ 고품질 요약 생성 완료: quality_score=0.87

# 품질 임계값 미달로 재시도
WARNING - AnthropicSummarizer - ⚠️ 품질 점수 미달 (0.65), 재시도 중...

# 폴백 실행
ERROR - AnthropicSummarizer - ❌ 품질 기준 미달, 기본 요약으로 폴백

# 프롬프트 템플릿 변경
INFO - PromptManager - ✅ 템플릿 업데이트 성공: anthropic_ticket_view (v1.0.1)
```

### 지원 문의

#### 개발팀 연락처
- **이메일**: ai-team@company.com
- **Slack**: #ai-alerts
- **문서**: `docs/` 폴더 참조

#### 이슈 보고
1. 오류 메시지 전체 복사
2. 입력 데이터 및 설정 정보
3. 재현 단계 상세 기록
4. 기대 결과 vs 실제 결과

---

## 📚 추가 리소스

### 관련 문서
- [Anthropic 프롬프트 엔지니어링 가이드](docs/ticket-summary-yaml-guide.md)
- [관리자 도구 사용법](docs/claude-guide-manager-guide.md)
- [API 참조 문서](api/README.md)

### 외부 참조
- [Anthropic Constitutional AI 논문](https://arxiv.org/abs/2212.08073)
- [Claude 모델 문서](https://docs.anthropic.com/claude/docs)
- [프롬프트 엔지니어링 모범 사례](https://docs.anthropic.com/claude/docs/prompt-engineering)

---

**© 2024 Freshdesk AI Assistant Team. All rights reserved.**

> 🎯 **목표**: 상담원이 5초 내에 티켓을 파악할 수 있는 고품질 AI 요약 시스템
> 
> 💡 **핵심**: Constitutional AI + XML 구조화 + 관리자 친화적 운영