---
applyTo: "**"
---

# 📋 코딩 원칙 및 체크리스트 지침서

_AI 세션 간 일관성 보장을 위한 코딩 원칙과 품질 체크리스트_

## 🎯 **코딩 원칙 목표**

**AI 세션 간 일관된 고품질 코드 유지**

- **기존 코드 재활용**: 90% 이상 기존 코드 재사용으로 세션 간 일관성 유지
- **멀티테넌트 보안**: company_id 기반 완전한 데이터 격리
- **표준화된 패턴**: 검증된 구현 패턴의 일관된 적용
- **품질 보증**: 체계적인 체크리스트를 통한 코드 품질 관리

---

## 🚀 **핵심 코딩 원칙 요약**

### 💡 **즉시 참조용 코딩 원칙**

**AI 세션 간 일관성 핵심**:

- 기존 코드 90% 이상 재활용 (전면 재작성 금지)
- 레거시 로직 보존 (안정적 작동 코드 유지)
- 점진적 개선 (급진적 변경 방지)

**멀티테넌트 보안 원칙**:

- 모든 데이터에 company_id 자동 태깅 필수
- API 호출 시 company_id 헤더 포함
- Qdrant 필터링 시 company_id + platform 조건

**코드 품질 원칙**:

- 함수별 단일 책임 원칙
- 명확한 타입 힌트 사용
- 구조화된 에러 처리

---

## ⚠️ **코딩 철칙 & 설계 원칙**

### 🔄 **기존 코드 재활용 의무**

**목적**: 세션이 바뀌어도 동일한 아키텍처 패턴 유지

```python
# ✅ AI가 따라야 할 패턴 - 기존 코드 개선
def improved_ticket_processor():
    # 기존 process_ticket() 함수 로직을 기반으로
    existing_logic = process_ticket()  # 기존 함수 재사용

    # 성능 최적화나 company_id 태깅만 추가
    if not existing_logic.get('company_id'):
        existing_logic['company_id'] = extract_company_id()

    return enhanced_result

# ❌ 피해야 할 패턴 - 전면 재작성
def new_ticket_processor():
    # 완전히 새로운 로직으로 재작성 (금지)
    pass
```

**재활용 원칙**:

- **90% 이상 기존 코드 재활용**: 새로운 코딩은 최소한으로 제한
- **레거시 로직 보존**: 안정적으로 작동하던 기존 코드의 핵심 로직 유지
- **점진적 개선**: 전면 재작성 대신 기존 코드를 다듬어 사용
- **검증된 패턴 유지**: 기존 비즈니스 로직, 데이터 처리 방식 최대한 보존

---

## 📋 **AI 작업 시 필수 체크포인트**

### **1. 작업 시작 전 체크포인트**

```python
# AI 작업 시작 시 필수 확인 절차
async def ai_work_pre_check(task_description: str, company_id: str):
    """AI 작업 시작 전 필수 체크"""

    checklist = {
        "existing_files_checked": False,
        "company_id_extracted": False,
        "platform_identified": False,
        "error_handling_planned": False
    }

    # 1. 기존 파일 구조 확인
    existing_files = await check_existing_files()
    checklist["existing_files_checked"] = len(existing_files) > 0

    # 2. company_id 자동 추출 패턴 적용
    if company_id and len(company_id) > 0:
        checklist["company_id_extracted"] = True

    # 3. 플랫폼별 추상화 확인
    platform = identify_platform()  # 기본값: "freshdesk"
    checklist["platform_identified"] = platform == "freshdesk"

    # 4. 에러 처리 패턴 계획
    checklist["error_handling_planned"] = True  # 항상 포함

    # 체크리스트 검증
    all_passed = all(checklist.values())
    if not all_passed:
        raise ValueError(f"사전 체크 실패: {checklist}")

    return checklist

async def check_existing_files():
    """기존 파일 구조 확인"""
    # file_search 또는 read_file로 현재 상태 파악
    pass

def identify_platform():
    """플랫폼 식별 (기본: Freshdesk)"""
    return "freshdesk"  # FDK는 Freshdesk 전용
```

### **2. company_id 자동 추출 체크포인트**

```python
# Python 버전 - 백엔드에서 사용
def extract_company_id(domain: str) -> str:
    """도메인에서 company_id 추출"""
    if not domain:
        return "demo"

    # xxx.freshdesk.com -> xxx
    if ".freshdesk.com" in domain:
        return domain.split(".freshdesk.com")[0].split(".")[-1]

    # 기타 도메인에서 첫 번째 부분 추출
    return domain.split(".")[0] or "demo"

# JavaScript 버전 (FDK) - 프론트엔드에서 사용
function extractCompanyId(domain) {
    if (!domain) return 'demo';

    // xxx.freshdesk.com -> xxx
    if (domain.includes('.freshdesk.com')) {
        return domain.split('.freshdesk.com')[0].split('.').pop();
    }

    // 로컬 개발 환경
    if (domain.includes('localhost') || domain.includes('127.0.0.1')) {
        return 'demo';
    }

    return domain.split('.')[0] || 'demo';
}

# 검증 함수
def validate_company_id(company_id: str) -> bool:
    """company_id 유효성 검증"""
    if not company_id or len(company_id) == 0:
        return False

    # 기본값 체크
    if company_id in ["demo", "test", "localhost"]:
        return True  # 개발 환경에서는 허용

    # 영숫자 및 하이픈만 허용
    import re
    pattern = r'^[a-zA-Z0-9\-]{2,50}$'
    return bool(re.match(pattern, company_id))
```

### **3. 멀티테넌트 API 호출 체크포인트**

```python
# 백엔드 API 호출 시 필수 헤더 패턴
def create_api_headers(company_id: str, api_key: Optional[str] = None) -> Dict[str, str]:
    """API 호출용 표준 헤더 생성"""

    headers = {
        'Content-Type': 'application/json',
        'X-Company-ID': company_id,
        'X-Platform': 'freshdesk',
        'User-Agent': 'AI-Assistant/1.0'
    }

    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    return headers

# Qdrant 필터링 패턴
from qdrant_client.models import Filter, FieldCondition, MatchValue

def create_qdrant_filter(company_id: str, platform: str = "freshdesk") -> Filter:
    """Qdrant 멀티테넌트 필터 생성"""

    return Filter(
        must=[
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            ),
            FieldCondition(
                key="platform",
                match=MatchValue(value=platform)
            )
        ]
    )

# API 호출 검증 함수
async def validate_api_call(endpoint: str, headers: Dict[str, str]) -> bool:
    """API 호출 전 검증"""

    required_headers = ['X-Company-ID', 'X-Platform']

    for header in required_headers:
        if header not in headers:
            raise ValueError(f"필수 헤더 누락: {header}")

    company_id = headers.get('X-Company-ID')
    if not validate_company_id(company_id):
        raise ValueError(f"유효하지 않은 company_id: {company_id}")

    return True
```

### **4. 에러 처리 체크포인트**

```python
from typing import Callable, Any
import asyncio
import logging

# 표준 에러 처리 패턴
async def safe_execute_with_retry(
    func: Callable,
    company_id: str,
    operation_name: str,
    max_retries: int = 3
) -> Any:
    """안전한 실행 with 재시도 + 로깅 + 사용자 친화적 메시지"""

    for attempt in range(max_retries + 1):
        try:
            result = await func()

            # 성공 로깅
            logging.info(
                f"작업 성공: operation={operation_name}, "
                f"company_id={company_id}, attempt={attempt}"
            )

            return result

        except Exception as e:
            # 재시도 불가능한 에러 체크
            if not is_retryable_error(e):
                logging.error(
                    f"재시도 불가능한 에러: operation={operation_name}, "
                    f"company_id={company_id}, error={str(e)}"
                )
                raise create_user_friendly_error(e, company_id)

            # 마지막 시도 실패
            if attempt >= max_retries:
                logging.error(
                    f"최대 재시도 초과: operation={operation_name}, "
                    f"company_id={company_id}, error={str(e)}"
                )
                raise create_user_friendly_error(e, company_id)

            # 재시도 대기
            delay = 2 ** attempt
            logging.warning(
                f"재시도 예정: operation={operation_name}, "
                f"company_id={company_id}, attempt={attempt + 1}, delay={delay}s"
            )
            await asyncio.sleep(delay)

def is_retryable_error(error: Exception) -> bool:
    """재시도 가능한 에러인지 확인"""
    retryable_types = [
        ConnectionError,
        TimeoutError,
        # HTTP 5xx 에러 등
    ]

    return any(isinstance(error, error_type) for error_type in retryable_types)

def create_user_friendly_error(error: Exception, company_id: str) -> Exception:
    """사용자 친화적 에러 생성"""
    from .error_handling import UserFriendlyError

    user_error = UserFriendlyError.format_user_error(error, company_id)
    return HTTPException(
        status_code=500,
        detail=user_error
    )
```

---

## 🎯 **AI 세션 간 일관성 보장 체크리스트**

### ✅ **필수 확인사항 (모든 구현 시)**

```python
class ConsistencyChecker:
    """AI 세션 간 일관성 체크"""

    @staticmethod
    def check_company_id_pattern(code_content: str) -> Dict[str, bool]:
        """company_id 패턴 검증"""

        checks = {
            "company_id_extraction": "extract_company_id" in code_content,
            "company_id_validation": "validate_company_id" in code_content,
            "company_id_in_headers": "X-Company-ID" in code_content,
            "company_id_in_filters": "company_id" in code_content and "qdrant" in code_content.lower()
        }

        return checks

    @staticmethod
    def check_platform_identification(code_content: str) -> Dict[str, bool]:
        """플랫폼 식별 패턴 검증"""

        checks = {
            "platform_freshdesk": '"freshdesk"' in code_content,
            "platform_header": "X-Platform" in code_content,
            "fdk_specific": "fdk" in code_content.lower() or "freshdesk" in code_content.lower()
        }

        return checks

    @staticmethod
    def check_error_handling(code_content: str) -> Dict[str, bool]:
        """에러 처리 패턴 검증"""

        checks = {
            "try_except_blocks": "try:" in code_content and "except" in code_content,
            "retry_logic": "retry" in code_content.lower(),
            "logging_included": "logging" in code_content,
            "user_friendly_errors": "user" in code_content.lower() and "error" in code_content.lower()
        }

        return checks

    @staticmethod
    def check_performance_patterns(code_content: str) -> Dict[str, bool]:
        """성능 최적화 패턴 검증"""

        checks = {
            "async_await": "async" in code_content and "await" in code_content,
            "concurrency_control": "Semaphore" in code_content or "asyncio" in code_content,
            "caching_present": "cache" in code_content.lower() or "redis" in code_content.lower(),
            "context_managers": "async with" in code_content or "__aenter__" in code_content
        }

        return checks

    @classmethod
    def run_full_check(cls, code_content: str) -> Dict[str, Dict[str, bool]]:
        """전체 일관성 체크 실행"""

        return {
            "company_id_patterns": cls.check_company_id_pattern(code_content),
            "platform_identification": cls.check_platform_identification(code_content),
            "error_handling": cls.check_error_handling(code_content),
            "performance_patterns": cls.check_performance_patterns(code_content)
        }

    @classmethod
    def generate_checklist_report(cls, check_results: Dict[str, Dict[str, bool]]) -> str:
        """체크리스트 보고서 생성"""

        report_lines = ["# AI 세션 간 일관성 체크 보고서\n"]

        for category, checks in check_results.items():
            report_lines.append(f"## {category.replace('_', ' ').title()}")

            for check_name, passed in checks.items():
                status = "✅" if passed else "❌"
                report_lines.append(f"- {status} {check_name.replace('_', ' ').title()}")

            report_lines.append("")

        # 전체 통과율 계산
        total_checks = sum(len(checks) for checks in check_results.values())
        passed_checks = sum(sum(checks.values()) for checks in check_results.values())
        pass_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0

        report_lines.append(f"**전체 통과율: {pass_rate:.1f}% ({passed_checks}/{total_checks})**")

        return "\n".join(report_lines)

# 사용 예시
def validate_code_consistency(code_content: str) -> bool:
    """코드 일관성 검증"""

    checker = ConsistencyChecker()
    results = checker.run_full_check(code_content)

    # 보고서 생성
    report = checker.generate_checklist_report(results)
    print(report)

    # 필수 패턴 검증 (80% 이상 통과 필요)
    total_checks = sum(len(checks) for checks in results.values())
    passed_checks = sum(sum(checks.values()) for checks in results.values())
    pass_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0

    return pass_rate >= 80.0
```

### 🚨 **자주 발생하는 함정들**

```python
class CommonPitfalls:
    """자주 발생하는 함정들과 해결책"""

    PITFALLS = {
        "fdk_syntax_errors": {
            "description": "FDK JavaScript 중괄호 매칭, 세미콜론 누락",
            "detection": lambda code: ("{" in code and "}" not in code) or code.count("{") != code.count("}"),
            "solution": "fdk validate --verbose로 구문 검증"
        },

        "missing_company_id": {
            "description": "멀티테넌트 데이터 격리 실패",
            "detection": lambda code: "company_id" not in code,
            "solution": "모든 데이터 처리에 company_id 태깅 추가"
        },

        "api_rate_limit": {
            "description": "Freshdesk API 제한 초과",
            "detection": lambda code: "rate" not in code.lower() and "limit" not in code.lower(),
            "solution": "요청 간격 조절 및 재시도 로직 구현"
        },

        "memory_leaks": {
            "description": "aiohttp 세션 정리 누락",
            "detection": lambda code: "aiohttp" in code and "close()" not in code,
            "solution": "async with 컨텍스트 매니저 사용"
        },

        "no_caching": {
            "description": "LLM 비용 폭증",
            "detection": lambda code: "openai" in code and "cache" not in code.lower(),
            "solution": "Redis 캐싱 구현 필수"
        }
    }

    @classmethod
    def check_pitfalls(cls, code_content: str) -> Dict[str, bool]:
        """함정 탐지"""

        pitfall_results = {}

        for pitfall_name, pitfall_info in cls.PITFALLS.items():
            try:
                has_pitfall = pitfall_info["detection"](code_content)
                pitfall_results[pitfall_name] = not has_pitfall  # 함정이 없으면 True
            except Exception:
                pitfall_results[pitfall_name] = False

        return pitfall_results

    @classmethod
    def generate_pitfall_report(cls, pitfall_results: Dict[str, bool]) -> str:
        """함정 보고서 생성"""

        report_lines = ["# 🚨 함정 탐지 보고서\n"]

        for pitfall_name, is_safe in pitfall_results.items():
            pitfall_info = cls.PITFALLS[pitfall_name]

            status = "✅ 안전" if is_safe else "⚠️ 위험"
            report_lines.append(f"## {pitfall_name.replace('_', ' ').title()}")
            report_lines.append(f"**상태**: {status}")
            report_lines.append(f"**설명**: {pitfall_info['description']}")

            if not is_safe:
                report_lines.append(f"**해결책**: {pitfall_info['solution']}")

            report_lines.append("")

        return "\n".join(report_lines)
```

### 📋 **AI 작업 시 표준 프로세스**

```python
class AIWorkflowManager:
    """AI 작업 표준 프로세스 관리"""

    STANDARD_WORKFLOW = [
        {
            "step": 1,
            "name": "기존_코드_확인",
            "description": "file_search → read_file로 현재 상태 파악",
            "required_tools": ["file_search", "read_file"],
            "success_criteria": "기존 파일 구조 파악 완료"
        },
        {
            "step": 2,
            "name": "패턴_적용",
            "description": "체크리스트 기반 구현 패턴 적용",
            "required_patterns": ["company_id_extraction", "error_handling", "async_patterns"],
            "success_criteria": "일관성 체크 80% 이상 통과"
        },
        {
            "step": 3,
            "name": "테스트_실행",
            "description": "FDK validate + 브라우저 개발자 도구 확인",
            "required_tools": ["fdk_validate", "browser_devtools"],
            "success_criteria": "구문 오류 없음, 런타임 오류 없음"
        },
        {
            "step": 4,
            "name": "company_id_검증",
            "description": "모든 API 호출에 company_id 포함 확인",
            "validation_points": ["api_headers", "qdrant_filters", "log_entries"],
            "success_criteria": "company_id 누락 0건"
        },
        {
            "step": 5,
            "name": "문서_업데이트",
            "description": "주요 변경사항 지침서에 기록",
            "update_targets": ["README.md", "관련 지침서"],
            "success_criteria": "변경사항 문서화 완료"
        }
    ]

    @classmethod
    def generate_workflow_checklist(cls) -> str:
        """워크플로우 체크리스트 생성"""

        checklist_lines = ["# 📋 AI 작업 표준 프로세스 체크리스트\n"]

        for step_info in cls.STANDARD_WORKFLOW:
            step_num = step_info["step"]
            step_name = step_info["name"].replace("_", " ").title()

            checklist_lines.append(f"## Step {step_num}: {step_name}")
            checklist_lines.append(f"**설명**: {step_info['description']}")

            if "required_tools" in step_info:
                tools = ", ".join(f"`{tool}`" for tool in step_info["required_tools"])
                checklist_lines.append(f"**필요 도구**: {tools}")

            if "required_patterns" in step_info:
                patterns = ", ".join(step_info["required_patterns"])
                checklist_lines.append(f"**필요 패턴**: {patterns}")

            checklist_lines.append(f"**성공 기준**: {step_info['success_criteria']}")
            checklist_lines.append("- [ ] 완료")
            checklist_lines.append("")

        return "\n".join(checklist_lines)

    @staticmethod
    def validate_workflow_completion(completed_steps: List[int]) -> Dict[str, Any]:
        """워크플로우 완료 상태 검증"""

        total_steps = len(AIWorkflowManager.STANDARD_WORKFLOW)
        completion_rate = (len(completed_steps) / total_steps) * 100

        missing_steps = []
        for step_info in AIWorkflowManager.STANDARD_WORKFLOW:
            if step_info["step"] not in completed_steps:
                missing_steps.append(step_info["name"])

        return {
            "completion_rate": completion_rate,
            "completed_steps": len(completed_steps),
            "total_steps": total_steps,
            "missing_steps": missing_steps,
            "is_complete": completion_rate == 100.0
        }
```

---

## 🔗 **관련 지침서 참조**

- 🚀 `quick-reference.instructions.md` - 핵심 체크포인트 요약
- 🎨 `fdk-development-patterns.instructions.md` - FDK 코딩 원칙
- 🐍 `backend-implementation-patterns.instructions.md` - 백엔드 코딩 원칙
- 🚨 `error-handling-debugging.instructions.md` - 에러 처리 원칙

---

_이 지침서는 AI 세션 간 일관성을 보장하는 코딩 원칙과 체크리스트를 포함합니다. 구체적인 구현 방법은 관련 지침서를 참조하세요._
