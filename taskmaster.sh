#!/bin/bash
# 통합 Task Master 스크립트 (taskmaster.sh)
# Task Master 관련 모든 기능을 제공하는 통합 스크립트입니다.

# 스크립트 경로 설정
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
ENV_FILE="$BACKEND_DIR/.env"
CONFIG_FILE="$PROJECT_ROOT/.taskmasterconfig"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"

# 색상 정의
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m" # No Color

# 사용법 표시 함수
show_usage() {
    echo -e "${BOLD}Wedosoft Task Master 도구 v1.0${NC}"
    echo
    echo -e "사용법: $0 [명령어] [옵션]"
    echo
    echo -e "${BOLD}기본 명령어:${NC}"
    echo -e "  ${YELLOW}run${NC} [명령어]    - Task Master 명령을 실행합니다 (list, next 등)"
    echo -e "  ${YELLOW}check${NC}          - 환경 설정 및 API 키 상태를 확인합니다"
    echo -e "  ${YELLOW}fix${NC}            - API 키 문제를 자동으로 해결합니다"
    echo -e "  ${YELLOW}load-env${NC}       - .env 파일을 환경 변수로 로드합니다"
    echo -e "  ${YELLOW}help${NC}           - 도움말을 표시합니다"
    echo
    echo -e "${BOLD}사용 예시:${NC}"
    echo -e "  $0 run list     # 태스크 목록 보기"
    echo -e "  $0 run next     # 다음 작업 보기"
    echo -e "  $0 check        # 환경 설정 진단하기"
    echo -e "  $0 fix          # 설정 문제 자동 해결"
    echo
    exit 1
}

# 환경변수 로드 함수
load_env() {
    echo -e "${BLUE}📋 환경변수 로드 중...${NC}"
    
    # .env 파일이 존재하는지 확인
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}오류: .env 파일을 찾을 수 없습니다. ($ENV_FILE)${NC}"
        exit 1
    fi

    # Python 스크립트를 통해 환경 변수 내보내기
    cd "$BACKEND_DIR" || { echo -e "${RED}오류: 백엔드 디렉토리로 이동할 수 없습니다.${NC}"; exit 1; }

    # 임시 파일에 환경 변수 명령어 저장
    TEMP_ENV_FILE="/tmp/taskmaster_env_$(date +%s).sh"

    # Python 모듈 실행하여 환경 변수 내보내기 명령어 생성
    python -c "from core.config import export_settings_for_taskmaster; export_settings_for_taskmaster()" > "$TEMP_ENV_FILE" 2>/dev/null

    if [ $? -ne 0 ]; then
        # Python 모듈 방식이 실패하면 직접 .env 파일에서 로드
        echo -e "${YELLOW}Python 모듈 로드 실패, .env 파일에서 직접 로드합니다...${NC}"
        echo "# Task Master 환경변수" > "$TEMP_ENV_FILE"
        grep -v "^#" "$ENV_FILE" | grep -v "^$" | sed 's/^/export /' >> "$TEMP_ENV_FILE"
    fi

    # 환경변수 로드
    source "$TEMP_ENV_FILE"
    
    # 주요 환경변수를 직접 내보내기 (현재 쉘 세션에 적용)
    export ANTHROPIC_API_KEY=$(grep "^ANTHROPIC_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
    export OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
    export GOOGLE_API_KEY=$(grep "^GOOGLE_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
    export PERPLEXITY_API_KEY=$(grep "^PERPLEXITY_API_KEY=" "$ENV_FILE" | cut -d= -f2-)

    # 임시 파일 삭제
    rm -f "$TEMP_ENV_FILE"

    echo -e "${GREEN}✅ 환경변수 로드 완료${NC}"
}

# 진단 기능
check_environment() {
    echo -e "${BOLD}${BLUE}===================================================${NC}"
    echo -e "${BOLD}${BLUE}     Task Master 환경변수 진단 도구${NC}"
    echo -e "${BOLD}${BLUE}===================================================${NC}"
    echo

    # 시스템 정보 확인
    echo -e "${BOLD}시스템 정보:${NC}"
    echo -e "  OS: $(uname -s)"
    echo -e "  Shell: $SHELL"
    echo -e "  Task Master 버전: $(task-master --version 2>/dev/null || echo '확인 불가')"
    echo

    # .env 파일 확인
    echo -e "${BOLD}.env 파일 상태:${NC}"
    if [ -f "$ENV_FILE" ]; then
        FILE_SIZE=$(wc -c < "$ENV_FILE")
        LINES=$(wc -l < "$ENV_FILE")
        echo -e "  ${GREEN}✓ .env 파일 존재 ($ENV_FILE)${NC}"
        echo -e "    - 파일 크기: $FILE_SIZE 바이트"
        echo -e "    - 줄 수: $LINES 줄"
        
        # API 키 확인
        echo
        echo -e "${BOLD}API 키 확인:${NC}"
        grep -q "ANTHROPIC_API_KEY" "$ENV_FILE" && echo -e "  ${GREEN}✓ ANTHROPIC_API_KEY 확인됨${NC}" || echo -e "  ${RED}✗ ANTHROPIC_API_KEY 없음${NC}"
        grep -q "OPENAI_API_KEY" "$ENV_FILE" && echo -e "  ${GREEN}✓ OPENAI_API_KEY 확인됨${NC}" || echo -e "  ${RED}✗ OPENAI_API_KEY 없음${NC}"
        grep -q "GOOGLE_API_KEY" "$ENV_FILE" && echo -e "  ${GREEN}✓ GOOGLE_API_KEY 확인됨${NC}" || echo -e "  ${RED}✗ GOOGLE_API_KEY 없음${NC}"
        grep -q "PERPLEXITY_API_KEY" "$ENV_FILE" && echo -e "  ${GREEN}✓ PERPLEXITY_API_KEY 확인됨${NC}" || echo -e "  ${RED}✗ PERPLEXITY_API_KEY 없음${NC}"
    else
        echo -e "  ${RED}✗ .env 파일이 존재하지 않습니다.${NC}"
    fi

    # Task Master 설정 파일 확인
    echo
    echo -e "${BOLD}.taskmasterconfig 파일 상태:${NC}"
    if [ -f "$CONFIG_FILE" ]; then
        echo -e "  ${GREEN}✓ .taskmasterconfig 파일 존재${NC}"
        
        # envFiles 설정 확인
        if grep -q "envFiles" "$CONFIG_FILE"; then
            echo -e "  ${GREEN}✓ envFiles 설정 확인됨${NC}"
        else
            echo -e "  ${RED}✗ envFiles 설정 없음${NC}"
            echo -e "    ${YELLOW}권장: .taskmasterconfig 파일에 다음 설정 추가:${NC}"
            echo -e "    \"envFiles\": [\"backend/.env\"]"
        fi
    else
        echo -e "  ${RED}✗ .taskmasterconfig 파일이 존재하지 않습니다.${NC}"
    fi

    # 현재 환경변수 확인
    echo
    echo -e "${BOLD}현재 환경변수 상태:${NC}"
    ENV_ANTHROPIC=$(env | grep ANTHROPIC_API_KEY || echo "")
    ENV_OPENAI=$(env | grep OPENAI_API_KEY || echo "")
    ENV_GEMINI=$(env | grep GEMINI_API_KEY || echo "")
    ENV_GOOGLE=$(env | grep GOOGLE_API_KEY || echo "")
    ENV_PERPLEXITY=$(env | grep PERPLEXITY_API_KEY || echo "")

    [ -n "$ENV_ANTHROPIC" ] && echo -e "  ${GREEN}✓ ANTHROPIC_API_KEY 환경변수 존재${NC}" || echo -e "  ${RED}✗ ANTHROPIC_API_KEY 환경변수 없음${NC}"
    [ -n "$ENV_OPENAI" ] && echo -e "  ${GREEN}✓ OPENAI_API_KEY 환경변수 존재${NC}" || echo -e "  ${RED}✗ OPENAI_API_KEY 환경변수 없음${NC}"
    
    # GOOGLE_API_KEY와 GEMINI_API_KEY 모두 확인 (호환성 유지)
    if [ -n "$ENV_GOOGLE" ]; then
        echo -e "  ${GREEN}✓ GOOGLE_API_KEY 환경변수 존재${NC}"
    elif [ -n "$ENV_GEMINI" ]; then
        echo -e "  ${YELLOW}! GEMINI_API_KEY 환경변수는 존재하지만 GOOGLE_API_KEY로 통일해야 합니다${NC}"
        echo -e "    ${YELLOW}  향후 GOOGLE_API_KEY만 사용 예정입니다.${NC}"
    else
        echo -e "  ${RED}✗ GOOGLE_API_KEY 환경변수 없음${NC}"
    fi
    
    [ -n "$ENV_PERPLEXITY" ] && echo -e "  ${GREEN}✓ PERPLEXITY_API_KEY 환경변수 존재${NC}" || echo -e "  ${RED}✗ PERPLEXITY_API_KEY 환경변수 없음${NC}"

    # MCP 설정 확인
    echo
    echo -e "${BOLD}MCP 설정 상태:${NC}"
    MCP_JSON="$PROJECT_ROOT/.vscode/mcp.json"
    VSCODE_SETTINGS="$PROJECT_ROOT/.vscode/settings.json"

    # .vscode/mcp.json 확인
    if [ -f "$MCP_JSON" ]; then
        echo -e "  ${GREEN}✓ .vscode/mcp.json 파일 존재${NC}"
        if grep -q "env:GOOGLE_API_KEY" "$MCP_JSON" || grep -q "\${env:GOOGLE_API_KEY}" "$MCP_JSON"; then
            echo -e "  ${GREEN}✓ .vscode/mcp.json 파일이 환경변수 참조 형식으로 설정됨${NC}"
        else
            echo -e "  ${RED}✗ .vscode/mcp.json 파일에서 하드코딩된 API 키 사용 중${NC}"
            echo -e "    ${YELLOW}권장: '$0 fix' 명령으로 설정 수정${NC}"
        fi
    else
        echo -e "  ${RED}✗ .vscode/mcp.json 파일이 존재하지 않습니다${NC}"
        echo -e "    ${YELLOW}권장: '$0 fix' 명령으로 파일 생성${NC}"
    fi

    # .vscode/settings.json 확인
    if [ -f "$VSCODE_SETTINGS" ]; then
        echo -e "  ${GREEN}✓ .vscode/settings.json 파일 존재${NC}"
        if grep -q "chat.mcp.keysFile" "$VSCODE_SETTINGS"; then
            echo -e "  ${GREEN}✓ MCP 키 파일 설정 확인됨${NC}"
        else
            echo -e "  ${RED}✗ MCP 키 파일 설정 없음${NC}"
            echo -e "    ${YELLOW}권장: '$0 fix' 명령으로 설정 추가${NC}"
        fi
        
        if grep -q "terminal.integrated.env.osx" "$VSCODE_SETTINGS"; then
            echo -e "  ${GREEN}✓ 터미널 환경변수 설정 확인됨${NC}"
        else
            echo -e "  ${RED}✗ 터미널 환경변수 설정 없음${NC}"
            echo -e "    ${YELLOW}권장: '$0 fix' 명령으로 설정 추가${NC}"
        fi
    else
        echo -e "  ${RED}✗ .vscode/settings.json 파일이 존재하지 않습니다${NC}"
        echo -e "    ${YELLOW}권장: '$0 fix' 명령으로 파일 생성${NC}"
    fi
    # 요약 및 제안
    echo
    echo -e "${BOLD}${BLUE}진단 요약:${NC}"
    ISSUES=0

    if [ ! -f "$ENV_FILE" ]; then
        echo -e "  ${RED}✗ .env 파일이 없습니다.${NC}"
        ISSUES=$((ISSUES+1))
    fi

    if [ -f "$CONFIG_FILE" ] && ! grep -q "envFiles" "$CONFIG_FILE"; then
        echo -e "  ${RED}✗ .taskmasterconfig에 envFiles 설정이 없습니다.${NC}"
        ISSUES=$((ISSUES+1))
    fi

    if [ -z "$ENV_ANTHROPIC" ] || [ -z "$ENV_OPENAI" ] || [ -z "$ENV_GEMINI" ] || [ -z "$ENV_PERPLEXITY" ]; then
        echo -e "  ${RED}✗ 일부 필수 API 키 환경변수가 설정되지 않았습니다.${NC}"
        ISSUES=$((ISSUES+1))
    fi

    if [ $ISSUES -eq 0 ]; then
        echo -e "  ${GREEN}✓ 모든 설정이 정상적으로 구성되어 있습니다!${NC}"
    else
        echo
        echo -e "${BOLD}${YELLOW}권장 조치:${NC}"
        echo -e "  1. 환경변수를 로드하려면 '$0 load-env' 명령을 실행하세요."
        echo -e "  2. 문제를 자동으로 해결하려면 '$0 fix' 명령을 실행하세요."
    fi

    echo
    echo -e "${BOLD}${BLUE}===================================================${NC}"
}

# 문제 자동 해결 함수
fix_issues() {
    echo -e "${BOLD}${BLUE}Task Master 설정 문제 자동 해결 도구${NC}"
    echo

    # .taskmasterconfig 파일 확인 및 수정
    if [ -f "$CONFIG_FILE" ]; then
        if ! grep -q "envFiles" "$CONFIG_FILE"; then
            echo -e "${YELLOW}envFiles 설정을 .taskmasterconfig 파일에 추가합니다...${NC}"
            
            # 임시 파일에 저장
            TEMP_CONFIG="/tmp/taskmasterconfig_$(date +%s).json"
            cat "$CONFIG_FILE" > "$TEMP_CONFIG"
            
            # envFiles 설정 추가
            sed -i '' 's/"global": {/"global": {\n    "envFiles": ["backend\/.env"],/g' "$TEMP_CONFIG"
            
            # 원본 파일 백업 및 새 설정 적용
            cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
            cat "$TEMP_CONFIG" > "$CONFIG_FILE"
            rm -f "$TEMP_CONFIG"
            
            echo -e "${GREEN}✓ .taskmasterconfig 파일이 업데이트되었습니다.${NC}"
        else
            echo -e "${GREEN}✓ .taskmasterconfig 파일이 이미 올바르게 구성되어 있습니다.${NC}"
        fi
    else
        echo -e "${RED}✗ .taskmasterconfig 파일이 존재하지 않습니다.${NC}"
    fi
    
    # 환경 변수 로드
    echo -e "${YELLOW}환경 변수를 로드합니다...${NC}"
    load_env
    
    echo
    echo -e "${GREEN}✅ 모든 문제 해결 작업이 완료되었습니다.${NC}"
    echo -e "${BLUE}이제 '$0 run list'와 같은 명령을 사용하여 Task Master를 실행할 수 있습니다.${NC}"
}

# Task Master 명령 실행 함수
run_taskmaster() {
    echo -e "${BOLD}${BLUE}Task Master 명령 실행${NC}"
    
    # 환경 변수 로드
    load_env
    
    if [ $# -eq 0 ]; then
        echo -e "${YELLOW}사용법: $0 run [task-master 명령어]${NC}"
        echo -e "예시: $0 run list"
        echo -e "예시: $0 run next"
        exit 1
    fi
    
    echo -e "${BLUE}🚀 Task Master 명령 실행: $@${NC}"
    echo
    
    # Task Master 실행
    task-master "$@"
}

# 메인 로직
case "$1" in
    "run")
        shift
        run_taskmaster "$@"
        ;;
    "check")
        check_environment
        ;;
    "fix")
        fix_issues
        sync_mcp_settings
        ;;
    "load-env")
        load_env
        echo -e "${GREEN}✓ 환경 변수가 로드되었습니다.${NC}"
        ;;
    "help"|"--help"|"-h")
        show_usage
        ;;
    *)
        show_usage
        ;;
esac

# MCP 설정 동기화 함수
sync_mcp_settings() {
    echo -e "\n${BOLD}MCP 설정 동기화:${NC}"
    
    # .vscode 폴더가 없으면 생성
    if [ ! -d "$PROJECT_ROOT/.vscode" ]; then
        mkdir -p "$PROJECT_ROOT/.vscode"
    fi
    
    # .env 파일이 있는지 확인
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}✗ .env 파일이 존재하지 않습니다. 먼저 .env 파일을 생성하세요.${NC}"
        return 1
    fi
    
    # .env 파일에서 API 키 읽기
    source "$ENV_FILE"
    
    # MCP 설정 파일 생성/업데이트
    echo -e "${BLUE}MCP JSON 설정 파일 업데이트 중...${NC}"
    
    cat > "$PROJECT_ROOT/.vscode/mcp.json" << EOF
{
    "anthropic": {
        "apiKey": "\${env:ANTHROPIC_API_KEY}"
    },
    "openai": {
        "apiKey": "\${env:OPENAI_API_KEY}"
    },
    "google": {
        "apiKey": "\${env:GOOGLE_API_KEY}"
    },
    "perplexity": {
        "apiKey": "\${env:PERPLEXITY_API_KEY}"
    }
}
EOF
    echo -e "${GREEN}✓ MCP JSON 설정이 업데이트되었습니다.${NC}"
    
    # .vscode/settings.json 파일 확인 및 업데이트
    VSCODE_SETTINGS="$PROJECT_ROOT/.vscode/settings.json"
    if [ ! -f "$VSCODE_SETTINGS" ]; then
        echo -e "${YELLOW}⚠️ .vscode/settings.json 파일이 존재하지 않습니다. 새로 생성합니다.${NC}"
        # 기본 설정 파일 생성
        cat > "$VSCODE_SETTINGS" << EOF
{
    "chat.mcp.enabled": true,
    "chat.mcp.keysFile": "\${workspaceFolder}/.vscode/mcp.json",
    "terminal.integrated.env.osx": {
        "PYTHONPATH": "\${workspaceFolder}/backend",
        "ANTHROPIC_API_KEY": "\${env:ANTHROPIC_API_KEY}",
        "OPENAI_API_KEY": "\${env:OPENAI_API_KEY}",
        "GOOGLE_API_KEY": "\${env:GOOGLE_API_KEY}",
        "PERPLEXITY_API_KEY": "\${env:PERPLEXITY_API_KEY}"
    }
}
EOF
    else
        # settings.json이 존재하면 MCP 키 설정만 추가/업데이트
        if grep -q "chat.mcp.keysFile" "$VSCODE_SETTINGS"; then
            echo -e "${GREEN}✓ .vscode/settings.json 파일에 MCP 키 설정이 이미 있습니다.${NC}"
        else
            echo -e "${YELLOW}⚠️ .vscode/settings.json 파일에 MCP 키 설정을 추가합니다.${NC}"
            # 임시 파일에 업데이트된 설정 저장
            TEMP_SETTINGS=$(mktemp)
            sed -i '' 's/{/{\n    "chat.mcp.enabled": true,\n    "chat.mcp.keysFile": "${workspaceFolder}\\/.vscode\\/mcp.json",/g' "$VSCODE_SETTINGS"
        fi
        
        # 터미널 환경 변수 설정 확인 및 추가
        if grep -q "terminal.integrated.env.osx" "$VSCODE_SETTINGS"; then
            echo -e "${GREEN}✓ .vscode/settings.json 파일에 터미널 환경 변수 설정이 이미 있습니다.${NC}"
        else
            echo -e "${YELLOW}⚠️ .vscode/settings.json 파일에 터미널 환경 변수 설정을 추가합니다.${NC}"
            # 임시 파일에 업데이트된 설정 저장
            TEMP_SETTINGS=$(mktemp)
            sed -i '' 's/{/{\\n    "terminal.integrated.env.osx": {\\n        "PYTHONPATH": "${workspaceFolder}\\/backend",\\n        "ANTHROPIC_API_KEY": "${env:ANTHROPIC_API_KEY}",\\n        "OPENAI_API_KEY": "${env:OPENAI_API_KEY}",\\n        "GOOGLE_API_KEY": "${env:GOOGLE_API_KEY}",\\n        "PERPLEXITY_API_KEY": "${env:PERPLEXITY_API_KEY}"\\n    },/g' "$VSCODE_SETTINGS"
        fi
    fi
    
    echo -e "${GREEN}✓ VS Code 설정이 업데이트되었습니다.${NC}"
    echo -e "${BLUE}ℹ️  이제 .env 파일만 관리하면 MCP와 Task Master가 자동으로 API 키를 참조합니다.${NC}"
}
