#!/bin/bash

# MCP 서버 설치 및 설정 자동화 스크립트
# GitHub Copilot 코딩 에이전트를 위한 환경 구성

set -e  # 오류 발생시 스크립트 중단

echo "🚀 GitHub Copilot MCP 환경 설정 시작..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 필수 도구 확인
check_prerequisites() {
    log_info "필수 도구 확인 중..."
    
    # Node.js 확인
    if ! command -v node &> /dev/null; then
        log_error "Node.js가 설치되지 않았습니다. Node.js 18+ 버전을 설치해주세요."
        exit 1
    fi
    
    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        log_error "Node.js 18+ 버전이 필요합니다. 현재 버전: $(node --version)"
        exit 1
    fi
    log_success "Node.js $(node --version) 확인됨"
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3이 설치되지 않았습니다."
        exit 1
    fi
    log_success "Python $(python3 --version) 확인됨"
    
    # npm 확인
    if ! command -v npm &> /dev/null; then
        log_error "npm이 설치되지 않았습니다."
        exit 1
    fi
    log_success "npm $(npm --version) 확인됨"
    
    # pip 확인
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3가 설치되지 않았습니다."
        exit 1
    fi
    log_success "pip3 확인됨"
}

# MCP 서버 설치
install_mcp_servers() {
    log_info "MCP 서버 설치 시작..."
    
    # Node.js 기반 MCP 서버들
    log_info "Node.js 기반 MCP 서버 설치..."
    
    # GitHub MCP Server
    log_info "GitHub MCP Server 설치 중..."
    if npm install -g @modelcontextprotocol/server-github; then
        log_success "GitHub MCP Server 설치 완료"
    else
        log_error "GitHub MCP Server 설치 실패"
        return 1
    fi
    
    # Filesystem MCP Server
    log_info "Filesystem MCP Server 설치 중..."
    if npm install -g @modelcontextprotocol/server-filesystem; then
        log_success "Filesystem MCP Server 설치 완료"
    else
        log_error "Filesystem MCP Server 설치 실패"
        return 1
    fi
    
    # Web Search MCP Server (선택사항)
    log_info "Web Search MCP Server 설치 중..."
    if npm install -g @modelcontextprotocol/server-web-search; then
        log_success "Web Search MCP Server 설치 완료"
    else
        log_warning "Web Search MCP Server 설치 실패 (선택사항)"
    fi
    
    # Python 기반 MCP 서버들
    log_info "Python 기반 MCP 서버 설치..."
    
    # Docker MCP Server
    log_info "Docker MCP Server 설치 중..."
    if pip3 install mcp-server-docker; then
        log_success "Docker MCP Server 설치 완료"
    else
        log_warning "Docker MCP Server 설치 실패 (선택사항)"
    fi
    
    # SQLite MCP Server (선택사항)
    log_info "SQLite MCP Server 설치 중..."
    if pip3 install mcp-server-sqlite; then
        log_success "SQLite MCP Server 설치 완료"
    else
        log_warning "SQLite MCP Server 설치 실패 (선택사항)"
    fi
}

# VS Code 설정 파일 생성
create_vscode_mcp_config() {
    log_info "VS Code MCP 설정 파일 생성..."
    
    # .vscode 디렉토리 생성
    mkdir -p .vscode
    
    # MCP 설정을 settings.json에 추가
    MCP_CONFIG='{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "${workspaceFolder}"],
      "env": {}
    },
    "docker": {
      "command": "python3",
      "args": ["-m", "mcp_server_docker"],
      "env": {}
    },
    "web-search": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-web-search"],
      "env": {
        "GOOGLE_SEARCH_API_KEY": "${env:GOOGLE_SEARCH_API_KEY}",
        "GOOGLE_SEARCH_ENGINE_ID": "${env:GOOGLE_SEARCH_ENGINE_ID}"
      }
    }
  }
}'
    
    # 기존 settings.json과 병합
    if [ -f ".vscode/settings.json" ]; then
        log_info "기존 settings.json에 MCP 설정 추가..."
        # 임시 파일로 백업
        cp .vscode/settings.json .vscode/settings.json.backup
        
        # Python을 사용하여 JSON 병합
        python3 -c "
import json
import sys

# 기존 설정 로드
try:
    with open('.vscode/settings.json', 'r') as f:
        existing = json.load(f)
except:
    existing = {}

# MCP 설정 추가
mcp_config = $MCP_CONFIG
existing.update(mcp_config)

# 저장
with open('.vscode/settings.json', 'w') as f:
    json.dump(existing, f, indent=2)

print('MCP 설정이 settings.json에 추가되었습니다.')
"
    else
        log_info "새로운 settings.json 생성..."
        echo "$MCP_CONFIG" > .vscode/settings.json
    fi
    
    log_success "VS Code MCP 설정 완료"
}

# 환경변수 확인 및 가이드
check_environment_variables() {
    log_info "환경변수 확인..."
    
    ENV_MISSING=false
    
    # GitHub Token 확인
    if [ -z "$GITHUB_TOKEN" ]; then
        log_warning "GITHUB_TOKEN이 설정되지 않았습니다."
        ENV_MISSING=true
    else
        log_success "GITHUB_TOKEN 설정됨"
    fi
    
    # Google Search API 확인 (선택사항)
    if [ -z "$GOOGLE_SEARCH_API_KEY" ]; then
        log_warning "GOOGLE_SEARCH_API_KEY가 설정되지 않았습니다 (선택사항)."
    else
        log_success "GOOGLE_SEARCH_API_KEY 설정됨"
    fi
    
    if [ "$ENV_MISSING" = true ]; then
        log_warning "필수 환경변수가 누락되었습니다."
        log_info "환경변수 설정 방법:"
        echo "1. GitHub Personal Access Token 생성:"
        echo "   https://github.com/settings/tokens"
        echo "2. .env 파일에 추가:"
        echo "   GITHUB_TOKEN=ghp_your_token_here"
        echo "3. 현재 세션에 적용:"
        echo "   source .env"
        echo ""
        log_info "자세한 설정 방법은 .github/MCP_INSTALLATION_GUIDE.md를 참고하세요."
    fi
}

# MCP 서버 테스트
test_mcp_servers() {
    log_info "MCP 서버 연결 테스트..."
    
    # GitHub MCP Server 테스트
    log_info "GitHub MCP Server 테스트..."
    if timeout 10s npx @modelcontextprotocol/server-github --help > /dev/null 2>&1; then
        log_success "GitHub MCP Server 작동 확인"
    else
        log_warning "GitHub MCP Server 테스트 실패"
    fi
    
    # Filesystem MCP Server 테스트
    log_info "Filesystem MCP Server 테스트..."
    if timeout 10s npx @modelcontextprotocol/server-filesystem --help > /dev/null 2>&1; then
        log_success "Filesystem MCP Server 작동 확인"
    else
        log_warning "Filesystem MCP Server 테스트 실패"
    fi
    
    # Docker MCP Server 테스트
    log_info "Docker MCP Server 테스트..."
    if python3 -c "import mcp_server_docker; print('Docker MCP Server: OK')" > /dev/null 2>&1; then
        log_success "Docker MCP Server 작동 확인"
    else
        log_warning "Docker MCP Server 테스트 실패"
    fi
}

# 메인 실행 함수
main() {
    echo "🤖 GitHub Copilot MCP 환경 설정"
    echo "================================"
    echo ""
    
    # 전체 과정 실행
    check_prerequisites
    echo ""
    
    install_mcp_servers
    echo ""
    
    create_vscode_mcp_config
    echo ""
    
    check_environment_variables
    echo ""
    
    test_mcp_servers
    echo ""
    
    # 완료 메시지
    log_success "🎉 MCP 환경 설정이 완료되었습니다!"
    echo ""
    log_info "다음 단계:"
    echo "1. VS Code 재시작: Command Palette → 'Developer: Reload Window'"
    echo "2. GitHub Copilot 확장 설치 (미설치시)"
    echo "3. 환경변수 설정: .env 파일 또는 시스템 환경변수"
    echo "4. Copilot Chat에서 '@copilot' 명령어로 테스트"
    echo ""
    log_info "문제 발생시 참고 문서:"
    echo "- .github/MCP_INSTALLATION_GUIDE.md"
    echo "- .github/COPILOT_MCP_GUIDE.md"
    echo ""
    
    # 추가 권장사항
    log_info "권장사항:"
    echo "- GitHub Personal Access Token 생성 및 설정"
    echo "- Docker Desktop 실행 (Docker MCP 서버 사용시)"
    echo "- 프로젝트별 환경변수 설정 (.env 파일)"
}

# 스크립트 실행
main "$@"
