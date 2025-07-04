#!/bin/bash

# Anthropic 프롬프트 엔지니어링 시스템 CI/CD 테스트 스크립트
# 
# 이 스크립트는 CI/CD 파이프라인에서 Anthropic 시스템의 품질을 자동으로 검증합니다.
# GitHub Actions, Jenkins, GitLab CI 등에서 사용할 수 있습니다.

set -e  # 오류 발생 시 즉시 종료

# ============================================================================
# 설정 및 초기화
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
TEST_REPORTS_DIR="$SCRIPT_DIR/test_reports"
LOG_FILE="$TEST_REPORTS_DIR/ci_test_execution.log"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 기본 설정
ENVIRONMENT=${CI_ENVIRONMENT:-"development"}
FAIL_FAST=${CI_FAIL_FAST:-"false"}
COVERAGE_THRESHOLD=${CI_COVERAGE_THRESHOLD:-"80"}
PERFORMANCE_THRESHOLD=${CI_PERFORMANCE_THRESHOLD:-"2.0"}
SLACK_WEBHOOK=${CI_SLACK_WEBHOOK:-""}

echo -e "${BLUE}🧪 Anthropic CI/CD 테스트 시작${NC}"
echo "Environment: $ENVIRONMENT"
echo "Project Root: $PROJECT_ROOT"
echo "Test Reports: $TEST_REPORTS_DIR"

# ============================================================================
# 유틸리티 함수
# ============================================================================

log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "$1"
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    log "SUCCESS" "$1"
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    log "WARNING" "$1"
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    log "ERROR" "$1"
    echo -e "${RED}❌ $1${NC}"
}

# 환경 검증
check_environment() {
    log_info "환경 검증 시작"
    
    # Python 버전 확인
    if ! command -v python3 &> /dev/null; then
        log_error "Python3가 설치되어 있지 않습니다"
        exit 1
    fi
    
    local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    log_info "Python 버전: $python_version"
    
    # 필수 환경변수 확인
    local required_vars=("ANTHROPIC_ENABLED")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_warning "누락된 환경변수: ${missing_vars[*]}"
        log_info "테스트 모드에서 Mock 데이터를 사용합니다"
        export TEST_MODE="mock"
    fi
    
    # API 키 확인 (민감 정보는 마스킹)
    if [[ -n "$ANTHROPIC_API_KEY" ]]; then
        log_info "Anthropic API 키: ****$(echo $ANTHROPIC_API_KEY | tail -c 5)"
    else
        log_warning "Anthropic API 키가 설정되지 않음 (Mock 모드 사용)"
    fi
    
    if [[ -n "$OPENAI_API_KEY" ]]; then
        log_info "OpenAI API 키: ****$(echo $OPENAI_API_KEY | tail -c 5)"
    else
        log_warning "OpenAI API 키가 설정되지 않음 (Mock 모드 사용)"
    fi
    
    log_success "환경 검증 완료"
}

# 의존성 설치
install_dependencies() {
    log_info "의존성 설치 시작"
    
    cd "$PROJECT_ROOT"
    
    # 가상환경 확인 및 생성
    if [[ ! -d "venv" ]] && [[ "$CI_CREATE_VENV" == "true" ]]; then
        log_info "가상환경 생성"
        python3 -m venv venv
    fi
    
    # 가상환경 활성화 (존재하는 경우)
    if [[ -d "venv" ]]; then
        log_info "가상환경 활성화"
        source venv/bin/activate
    fi
    
    # 필수 패키지 설치
    log_info "테스트 패키지 설치"
    pip install --quiet --upgrade pip
    pip install --quiet pytest pytest-asyncio pytest-cov pyyaml
    
    # 프로젝트 의존성 설치 (requirements.txt가 있는 경우)
    if [[ -f "requirements.txt" ]]; then
        log_info "프로젝트 의존성 설치"
        pip install --quiet -r requirements.txt
    fi
    
    log_success "의존성 설치 완료"
}

# 테스트 환경 준비
prepare_test_environment() {
    log_info "테스트 환경 준비"
    
    # 테스트 보고서 디렉토리 생성
    mkdir -p "$TEST_REPORTS_DIR"
    
    # 로그 파일 초기화
    echo "=== Anthropic CI/CD 테스트 로그 ===" > "$LOG_FILE"
    echo "시작 시간: $(date)" >> "$LOG_FILE"
    echo "환경: $ENVIRONMENT" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    
    # 테스트 설정 생성 (동적)
    create_ci_test_config
    
    log_success "테스트 환경 준비 완료"
}

# CI용 테스트 설정 생성
create_ci_test_config() {
    local config_file="$SCRIPT_DIR/ci_test_config.yaml"
    
    log_info "CI 테스트 설정 생성: $config_file"
    
    cat > "$config_file" << EOF
# CI/CD 자동 생성 테스트 설정
version: "1.0.0"
environment: "$ENVIRONMENT"

test_suites:
  unit_tests:
    enabled: true
    timeout: 180
    fail_fast: $FAIL_FAST
  
  anthropic_tests:
    enabled: true
    timeout: 240
    fail_fast: $FAIL_FAST
  
  integration_tests:
    enabled: true
    timeout: 300
    fail_fast: $FAIL_FAST

coverage:
  enabled: true
  min_coverage: $COVERAGE_THRESHOLD
  target_coverage: 90

reporting:
  formats: ["json", "console"]
  output_dir: "$TEST_REPORTS_DIR"
  include_performance: true
  include_coverage: true

performance:
  benchmark_enabled: true
  response_time_threshold: $PERFORMANCE_THRESHOLD
  memory_threshold_mb: 512

ci_cd:
  fail_fast: $FAIL_FAST
  continue_on_error: false
  notifications:
    slack:
      enabled: $([ -n "$SLACK_WEBHOOK" ] && echo "true" || echo "false")
      webhook_url: "$SLACK_WEBHOOK"

logging:
  level: "INFO"
  file_output: true
  console_output: true
EOF
    
    log_success "CI 테스트 설정 생성 완료"
}

# ============================================================================
# 테스트 실행 함수들
# ============================================================================

# 빠른 체크 실행 (Pull Request용)
run_quick_check() {
    log_info "빠른 체크 실행 (PR 검증용)"
    
    cd "$SCRIPT_DIR"
    
    local start_time=$(date +%s)
    local config_file="ci_test_config.yaml"
    
    if python3 run_tests.py --quick --config "$config_file" 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log_success "빠른 체크 완료 (실행 시간: ${duration}초)"
        return 0
    else
        log_error "빠른 체크 실패"
        return 1
    fi
}

# 전체 테스트 실행 (메인 브랜치용)
run_full_tests() {
    log_info "전체 테스트 실행 (메인 브랜치 검증용)"
    
    cd "$SCRIPT_DIR"
    
    local start_time=$(date +%s)
    local config_file="ci_test_config.yaml"
    
    if python3 run_tests.py --config "$config_file" --coverage --performance 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log_success "전체 테스트 완료 (실행 시간: ${duration}초)"
        return 0
    else
        log_error "전체 테스트 실패"
        return 1
    fi
}

# 통합 테스트만 실행
run_integration_only() {
    log_info "통합 테스트 실행"
    
    cd "$SCRIPT_DIR"
    
    local start_time=$(date +%s)
    
    if python3 integration_test.py 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log_success "통합 테스트 완료 (실행 시간: ${duration}초)"
        return 0
    else
        log_error "통합 테스트 실패"
        return 1
    fi
}

# ============================================================================
# 결과 분석 및 보고
# ============================================================================

# 테스트 결과 분석
analyze_test_results() {
    log_info "테스트 결과 분석"
    
    local latest_json_report
    latest_json_report=$(find "$TEST_REPORTS_DIR" -name "test_report_*.json" -type f -exec ls -t {} + | head -1)
    
    if [[ -z "$latest_json_report" ]]; then
        log_warning "JSON 보고서를 찾을 수 없습니다"
        return 1
    fi
    
    log_info "보고서 분석: $latest_json_report"
    
    # jq가 있으면 상세 분석, 없으면 기본 분석
    if command -v jq &> /dev/null; then
        analyze_with_jq "$latest_json_report"
    else
        analyze_without_jq "$latest_json_report"
    fi
}

# jq를 사용한 상세 분석
analyze_with_jq() {
    local report_file=$1
    
    log_info "상세 결과 분석 (jq 사용)"
    
    # 전체 성공률
    local overall_success=$(jq -r '.final_result.success // false' "$report_file")
    local success_rate=$(jq -r '.final_result.summary.success_rate // 0' "$report_file")
    local duration=$(jq -r '.test_session.duration // 0' "$report_file")
    
    echo "📊 테스트 결과 요약:"
    echo "  - 전체 성공: $overall_success"
    echo "  - 성공률: $(printf "%.1f%%" $(echo "$success_rate * 100" | bc -l 2>/dev/null || echo "0"))"
    echo "  - 실행 시간: ${duration}초"
    
    # 커버리지 정보
    local coverage=$(jq -r '.coverage.overall_coverage // 0' "$report_file")
    echo "  - 코드 커버리지: ${coverage}%"
    
    # 성능 정보
    local avg_response_time=$(jq -r '.performance.average_response_time // 0' "$report_file")
    echo "  - 평균 응답 시간: ${avg_response_time}초"
    
    # 실패한 테스트 목록
    local failed_tests=$(jq -r '.error_logs[]?.test // empty' "$report_file")
    if [[ -n "$failed_tests" ]]; then
        echo "❌ 실패한 테스트:"
        echo "$failed_tests" | while read -r test; do
            echo "  - $test"
        done
    fi
}

# jq 없이 기본 분석
analyze_without_jq() {
    local report_file=$1
    
    log_info "기본 결과 분석 (jq 미사용)"
    
    # 기본적인 grep 기반 분석
    if grep -q '"success": true' "$report_file"; then
        log_success "전체 테스트 성공"
    else
        log_error "전체 테스트 실패"
    fi
    
    # 파일 크기 기반 대략적 분석
    local file_size=$(stat -c%s "$report_file" 2>/dev/null || stat -f%z "$report_file" 2>/dev/null || echo "0")
    echo "보고서 크기: ${file_size} bytes"
}

# 슬랙 알림 전송
send_slack_notification() {
    local status=$1
    local message=$2
    
    if [[ -z "$SLACK_WEBHOOK" ]]; then
        log_info "슬랙 웹훅이 설정되지 않음 - 알림 전송 건너뜀"
        return 0
    fi
    
    log_info "슬랙 알림 전송"
    
    local color
    local emoji
    if [[ "$status" == "success" ]]; then
        color="good"
        emoji="✅"
    else
        color="danger"
        emoji="❌"
    fi
    
    local payload=$(cat << EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$emoji Anthropic 테스트 결과",
            "text": "$message",
            "fields": [
                {
                    "title": "환경",
                    "value": "$ENVIRONMENT",
                    "short": true
                },
                {
                    "title": "브랜치",
                    "value": "${CI_COMMIT_REF_NAME:-unknown}",
                    "short": true
                },
                {
                    "title": "커밋",
                    "value": "${CI_COMMIT_SHA:-unknown}",
                    "short": true
                },
                {
                    "title": "시간",
                    "value": "$(date)",
                    "short": false
                }
            ]
        }
    ]
}
EOF
)
    
    if curl -X POST -H 'Content-type: application/json' \
            --data "$payload" \
            "$SLACK_WEBHOOK" &>/dev/null; then
        log_success "슬랙 알림 전송 완료"
    else
        log_warning "슬랙 알림 전송 실패"
    fi
}

# 아티팩트 수집
collect_artifacts() {
    log_info "테스트 아티팩트 수집"
    
    local artifacts_dir="$TEST_REPORTS_DIR/artifacts"
    mkdir -p "$artifacts_dir"
    
    # 로그 파일 복사
    if [[ -f "$LOG_FILE" ]]; then
        cp "$LOG_FILE" "$artifacts_dir/"
        log_info "로그 파일 수집: $LOG_FILE"
    fi
    
    # JSON 보고서 수집
    find "$TEST_REPORTS_DIR" -name "*.json" -type f -exec cp {} "$artifacts_dir/" \;
    
    # HTML 보고서 수집
    find "$TEST_REPORTS_DIR" -name "*.html" -type f -exec cp {} "$artifacts_dir/" \;
    
    # 압축 아카이브 생성 (CI 환경에서 유용)
    if command -v tar &> /dev/null; then
        local archive_name="anthropic_test_artifacts_$(date +%Y%m%d_%H%M%S).tar.gz"
        tar -czf "$TEST_REPORTS_DIR/$archive_name" -C "$artifacts_dir" .
        log_success "아티팩트 아카이브 생성: $archive_name"
    fi
    
    log_success "아티팩트 수집 완료"
}

# ============================================================================
# 메인 실행 로직
# ============================================================================

# 도움말 출력
show_help() {
    cat << EOF
Anthropic CI/CD 테스트 스크립트

사용법:
  $0 [옵션] [명령]

명령:
  quick       빠른 체크 실행 (PR용)
  full        전체 테스트 실행 (기본값)
  integration 통합 테스트만 실행
  help        이 도움말 출력

옵션:
  --environment ENV    환경 설정 (development/staging/production)
  --fail-fast         첫 번째 실패 시 즉시 중단
  --coverage NUM      커버리지 임계값 설정 (기본값: 80)
  --performance NUM   성능 임계값 설정 (기본값: 2.0)
  --slack-webhook URL 슬랙 웹훅 URL 설정
  --no-artifacts     아티팩트 수집 건너뜀

환경변수:
  ANTHROPIC_ENABLED      Anthropic 기능 활성화 (true/false)
  ANTHROPIC_API_KEY      Anthropic API 키
  OPENAI_API_KEY         OpenAI API 키
  CI_ENVIRONMENT         CI 환경 (development/staging/production)
  CI_FAIL_FAST          실패 시 즉시 중단 (true/false)
  CI_COVERAGE_THRESHOLD  커버리지 임계값 (0-100)
  CI_SLACK_WEBHOOK      슬랙 웹훅 URL

예시:
  # 빠른 체크 실행
  $0 quick
  
  # 전체 테스트 실행 (커버리지 90% 이상)
  $0 full --coverage 90
  
  # 실패 시 즉시 중단하며 통합 테스트 실행
  $0 integration --fail-fast
EOF
}

# 명령행 인수 파싱
parse_arguments() {
    COMMAND="full"  # 기본 명령
    COLLECT_ARTIFACTS="true"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            quick|full|integration)
                COMMAND="$1"
                shift
                ;;
            help|--help|-h)
                show_help
                exit 0
                ;;
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --fail-fast)
                FAIL_FAST="true"
                shift
                ;;
            --coverage)
                COVERAGE_THRESHOLD="$2"
                shift 2
                ;;
            --performance)
                PERFORMANCE_THRESHOLD="$2"
                shift 2
                ;;
            --slack-webhook)
                SLACK_WEBHOOK="$2"
                shift 2
                ;;
            --no-artifacts)
                COLLECT_ARTIFACTS="false"
                shift
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 메인 실행 함수
main() {
    local start_time=$(date +%s)
    local exit_code=0
    
    # 인수 파싱
    parse_arguments "$@"
    
    # 초기화
    check_environment
    install_dependencies
    prepare_test_environment
    
    # 테스트 실행
    case "$COMMAND" in
        quick)
            if ! run_quick_check; then
                exit_code=1
            fi
            ;;
        full)
            if ! run_full_tests; then
                exit_code=1
            fi
            ;;
        integration)
            if ! run_integration_only; then
                exit_code=1
            fi
            ;;
    esac
    
    # 결과 분석
    analyze_test_results
    
    # 아티팩트 수집
    if [[ "$COLLECT_ARTIFACTS" == "true" ]]; then
        collect_artifacts
    fi
    
    # 알림 전송
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    if [[ $exit_code -eq 0 ]]; then
        local success_message="Anthropic 테스트 성공! (실행 시간: ${total_duration}초)"
        log_success "$success_message"
        send_slack_notification "success" "$success_message"
    else
        local failure_message="Anthropic 테스트 실패! (실행 시간: ${total_duration}초)"
        log_error "$failure_message"
        send_slack_notification "failure" "$failure_message"
    fi
    
    # 최종 로그
    echo "종료 시간: $(date)" >> "$LOG_FILE"
    echo "총 실행 시간: ${total_duration}초" >> "$LOG_FILE"
    echo "종료 코드: $exit_code" >> "$LOG_FILE"
    
    log_info "테스트 로그: $LOG_FILE"
    log_info "테스트 보고서: $TEST_REPORTS_DIR"
    
    exit $exit_code
}

# 스크립트가 직접 실행될 때만 main 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi