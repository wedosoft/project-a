#!/bin/bash

# ANSI Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=====================================================${NC}"
echo -e "${CYAN}🤖 Project-A LangChain 에이전트 환경 설정 시작 🤖${NC}"
echo -e "${CYAN}=====================================================${NC}"

# Python 버전 체크 (3.9 이상 권장)
echo -e "\n${YELLOW}1. Python 버전 확인 중...${NC}"
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9 이상이 필요합니다. 현재 버전: " + sys.version'
if [ $? -ne 0 ]; then
    echo "Python 버전 요구사항을 만족하지 못했습니다. 설치를 중단합니다."
    exit 1
fi
echo -e "${GREEN}Python 버전 확인 완료.${NC}"

# 가상환경 설정
echo -e "\n${YELLOW}2. Python 가상환경 설정 중...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}가상환경(.venv) 생성 완료.${NC}"
else
    echo -e "${GREEN}기존 가상환경(.venv)을 사용합니다.${NC}"
fi

# 가상환경 활성화 및 의존성 설치
source .venv/bin/activate
echo -e "\n${YELLOW}3. 백엔드 의존성 라이브러리 설치 중... (requirements.txt)${NC}"
pip install -r backend/requirements.txt
echo -e "${GREEN}의존성 설치 완료.${NC}"

# .env 파일 설정
echo -e "\n${YELLOW}4. .env 파일 설정 중...${NC}"
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}backend/.env 파일이 없습니다. 기본 설정으로 생성합니다.${NC}"
    # config.py를 참고하여 필수 환경변수 설정
    cat > backend/.env << EOL
FRESHDESK_API_KEY=your_freshdesk_api_key
# FRESHDESK_DOMAIN: 도메인 이름만 입력 (예: "your-company") 또는 전체 도메인 (예: "your-company.freshdesk.com")
# 시스템에서 자동으로 company_id를 추출하여 X-Company-ID 헤더에 사용합니다
FRESHDESK_DOMAIN=your_freshdesk_domain

# =================================================================
# Qdrant Cloud 벡터 데이터베이스 설정
# =================================================================
QDRANT_URL=https://your-qdrant-url
QDRANT_API_KEY=your_qdrant_api_key

# =================================================================
# LLM API 키 설정 (Multi-LLM Router용)
# =================================================================
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key

# =================================================================
# 애플리케이션 설정
# =================================================================
COMPANY_ID=your_company_id
PROCESS_ATTACHMENTS=true
EMBEDDING_MODEL=text-embedding-3-small
LOG_LEVEL=INFO
MAX_TOKENS=4096
EOL
    echo -e "${GREEN}backend/.env 파일 생성 완료. 파일을 열어 API 키 등 필수 정보를 입력해주세요.${NC}"
else
    echo -e "${GREEN}backend/.env 파일이 이미 존재합니다.${NC}"
fi

echo -e "\n${GREEN}✅ 에이전트 환경 설정이 완료되었습니다!${NC}"
echo -e "다음 단계를 진행하세요:"
echo -e "1. ${YELLOW}backend/.env${NC} 파일을 열어 ${YELLOW}API 키와 도메인 정보${NC}를 입력하세요."
echo -e "2. 다음 명령어로 가상환경을 활성화하세요: ${CYAN}source .venv/bin/activate${NC}"
echo -e "3. 다음 명령어로 백엔드 서버를 실행하세요: ${CYAN}uvicorn backend.api.main:app --reload${NC}"
