# Anthropic 프롬프트 엔지니어링 시스템 통합 테스트

이 디렉토리는 Anthropic 기법이 적용된 프롬프트 엔지니어링 시스템의 종합적인 테스트를 제공합니다.

## 📋 테스트 구성

### 1. 통합 테스트 (`integration_test.py`)
- **목적**: 전체 시스템의 종단간 테스트
- **범위**: Constitutional AI, XML 구조화, 품질 검증, 폴백 메커니즘
- **시나리오**: 기술적 문제, 고객 서비스, 다국어 지원, 보안 사고

### 2. 테스트 실행기 (`run_tests.py`)
- **목적**: 자동화된 테스트 실행 및 보고서 생성
- **기능**: 단위 테스트, 통합 테스트, 커버리지 분석, 성능 벤치마킹
- **지원**: CI/CD 통합, 다양한 보고서 형식

### 3. 단위 테스트 (`test_anthropic_prompts.py`)
- **목적**: 개별 컴포넌트의 단위 테스트
- **범위**: 프롬프트 빌더, 품질 검증기, 설정 관리

## 🚀 빠른 시작

### 환경 설정

```bash
# 필수 환경변수 설정
export ANTHROPIC_ENABLED=true
export ANTHROPIC_API_KEY=your_api_key
export OPENAI_API_KEY=your_openai_key

# 의존성 설치
pip install pytest pytest-asyncio pytest-cov pyyaml
```

### 기본 테스트 실행

```bash
# 모든 테스트 실행
python run_tests.py

# 빠른 체크 (CI/CD용)
python run_tests.py --quick

# 커버리지 포함 실행
python run_tests.py --coverage

# 설정 파일 사용
python run_tests.py --config test_config.yaml
```

### 통합 테스트만 실행

```bash
# 직접 실행
python integration_test.py

# pytest로 실행
pytest integration_test.py -v
```

## 📊 테스트 시나리오

### 1. 기술적 API 오류 시나리오
```yaml
시나리오: 결제 API 연동 실패 - 긴급
내용: 
  - 500 Internal Server Error 발생
  - 시간당 1000만원 매출 손실
  - 김개발자의 단계별 처리 과정
검증 요소:
  - XML 구조화된 응답
  - Constitutional AI 원칙 준수
  - 실행 가능한 인사이트 포함
```

### 2. 고객 서비스 결제 문제
```yaml
시나리오: Premium 고객 환불 처리 지연
내용:
  - VIP 고객 7일 처리 지연
  - 서비스 해지 위협
  - 재무팀 승인 프로세스 지연
검증 요소:
  - 에스컬레이션 정보 포함
  - 고객 관리 방안 제시
  - 프로세스 개선 권장사항
```

### 3. 다국어 지원 테스트
```yaml
시나리오: Database Performance Issue (영어)
내용:
  - 쿼리 응답 시간 증가 (100ms → 5000ms)
  - John Smith의 처리 과정
  - 인덱스 최적화로 해결
검증 요소:
  - 영어 섹션 제목 사용
  - 언어별 응답 형식 준수
```

### 4. 보안 사고 처리
```yaml
시나리오: 의심스러운 로그인 시도 감지
내용:
  - 여러 IP에서 로그인 시도
  - 비정상적인 지역 접속
  - 보안 조치 적용
검증 요소:
  - 개인정보 노출 없음
  - 보안 조치 내용 포함
  - Constitutional AI 원칙 준수
```

## 🧪 테스트 카테고리

### Constitutional AI 준수 테스트
- **Helpful**: 상담원에게 즉시 유용한 정보 제공
- **Harmless**: 개인정보 보호, 추측 정보 배제
- **Honest**: 불확실성 명시, 투명한 정보 제공

### XML 구조화 테스트
```xml
<problem_overview>🔍 **문제 현황**</problem_overview>
<root_cause>💡 **원인 분석**</root_cause>
<resolution_progress>⚡ **해결 진행상황**</resolution_progress>
<key_insights>🎯 **중요 인사이트**</key_insights>
```

### 품질 검증 테스트
- **구조 점수**: XML 태그 완성도
- **내용 품질**: 실행 가능성, 정확성
- **언어 품질**: 문법, 어조, 전문성

### 폴백 메커니즘 테스트
- **API 실패**: 연결 오류 시 폴백
- **품질 미달**: 낮은 품질 점수 시 재시도
- **시간 초과**: 응답 지연 시 대체 처리

## 📈 성능 벤치마킹

### 응답 시간 기준
- **평균 응답 시간**: 2초 이하
- **최대 응답 시간**: 5초 이하
- **처리량**: 초당 10요청 이상

### 메모리 사용량
- **기본 메모리**: 512MB 이하
- **피크 메모리**: 1GB 이하
- **메모리 누수**: 없음

## 🔧 설정 옵션

### 테스트 실행 설정
```yaml
test_suites:
  unit_tests:
    enabled: true
    timeout: 300
  integration_tests:
    enabled: true
    timeout: 600
  anthropic_tests:
    enabled: true
    timeout: 300
```

### 커버리지 설정
```yaml
coverage:
  enabled: true
  min_coverage: 80
  target_coverage: 90
  exclude_patterns:
    - "test_*"
    - "__pycache__"
```

### 보고서 설정
```yaml
reporting:
  formats: ["json", "html", "console"]
  output_dir: "test_reports"
  include_performance: true
  include_coverage: true
```

## 📊 보고서 형식

### JSON 보고서
```json
{
  "test_session": {
    "start_time": "2025-07-04T10:30:00",
    "end_time": "2025-07-04T10:35:00",
    "duration": 300
  },
  "test_suites": {
    "integration_tests": {
      "total_tests": 15,
      "passed_tests": 14,
      "failed_tests": 1,
      "success_rate": 0.93
    }
  }
}
```

### HTML 보고서
- 시각적 대시보드
- 테스트 결과 차트
- 커버리지 바
- 성능 그래프

### 콘솔 보고서
```
🧪 ANTHROPIC 테스트 실행 결과
================================
📊 전체 성공률: 93.3%
⏱️  총 실행 시간: 180.50초
📈 코드 커버리지: 85.2%
⚡ 성능 기준: 통과
🎯 전체 결과: ✅ 성공
```

## 🔄 CI/CD 통합

### GitHub Actions 예시
```yaml
name: Anthropic Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run tests
        env:
          ANTHROPIC_ENABLED: true
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python backend/core/llm/summarizer/tests/run_tests.py --quick
```

### Jenkins 파이프라인
```groovy
pipeline {
    agent any
    environment {
        ANTHROPIC_ENABLED = 'true'
        ANTHROPIC_API_KEY = credentials('anthropic-api-key')
    }
    stages {
        stage('Test') {
            steps {
                sh 'python backend/core/llm/summarizer/tests/run_tests.py'
            }
        }
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'test_reports/**/*'
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'test_reports',
                    reportFiles: 'test_report_*.html',
                    reportName: 'Test Report'
                ])
            }
        }
    }
}
```

## 🐛 문제 해결

### 환경변수 미설정
```bash
Error: ANTHROPIC_API_KEY not found
해결: export ANTHROPIC_API_KEY=your_key
```

### 모듈 import 오류
```bash
Error: ModuleNotFoundError: No module named 'anthropic_summarizer'
해결: PYTHONPATH 설정 또는 패키지 설치
```

### 테스트 시간 초과
```bash
Error: Test timeout after 300 seconds
해결: --config로 timeout 증가 또는 --quick 옵션 사용
```

### 메모리 부족
```bash
Error: MemoryError during test execution
해결: 테스트 병렬 실행 비활성화 또는 메모리 증설
```

## 📚 추가 자료

### 개발 가이드
- [Constitutional AI 구현 가이드](../config/anthropic_config.py)
- [XML 구조화 패턴](../prompt/templates/system/anthropic_ticket_view.yaml)
- [품질 검증 기준](../quality/anthropic_validator.py)

### API 문서
- [AnthropicSummarizer API](../core/anthropic_summarizer.py)
- [PromptManager API](../admin/prompt_manager.py)
- [Settings API](../config/settings.py)

### 예제 코드
```python
# 통합 테스트 직접 실행
from integration_test import AnthropicIntegrationTest

async def run_custom_test():
    test_runner = AnthropicIntegrationTest()
    await test_runner.setup_test_environment()
    result = await test_runner.test_constitutional_ai_compliance()
    print(f"테스트 결과: {result}")

# 설정 기반 테스트 실행
from run_tests import TestRunner

async def run_configured_test():
    runner = TestRunner("custom_config.yaml")
    results = await runner.run_all_tests()
    print(f"전체 결과: {results['final_result']}")
```

## 🤝 기여 가이드

### 새 테스트 시나리오 추가
1. `integration_test.py`의 `test_scenarios` 배열에 시나리오 추가
2. 기대 요소와 품질 기준 정의
3. Mock 응답 패턴 작성

### 새 검증 규칙 추가
1. `AnthropicQualityValidator`에 검증 메서드 추가
2. 통합 테스트에서 검증 호출
3. 테스트 케이스 작성

### 성능 메트릭 추가
1. `_analyze_performance()` 메서드 확장
2. 새 임계값 설정 추가
3. 보고서 형식 업데이트

---

## 📞 지원

문제가 발생하거나 개선 제안이 있으시면:

1. **이슈 등록**: GitHub Issues에 상세한 정보와 함께 등록
2. **로그 첨부**: `test_reports/` 디렉토리의 로그 파일 포함
3. **환경 정보**: Python 버전, OS, 설정 파일 등 제공

**Happy Testing! 🧪✨**