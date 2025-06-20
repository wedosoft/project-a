# 자연어 기반 Freshdesk 상담사 지원 시스템

이 프로젝트는 Freshdesk Custom App을 위한 자연어 기반 상담사 지원 시스템입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스 데이터를 기반으로 상담사의 자연어 요청을 처리하고 맥락에 맞는 AI 응답을 생성하는 기능을 제공합니다.

## 프로젝트 문서

- [프로젝트 규칙 및 가이드라인](./PROJECT_RULES.md) - 개발 시 준수해야 할 규칙과 가이드라인
- [환경 구성 가이드](./SETUP.md) - 새로운 개발 환경 구성을 위한 상세 지침

## 시작하기

### 요구사항

- Python 3.10+
- Docker 및 Docker Compose

### 개발 환경 설정

#### ChatGPT Code Interpreter 환경 (권장)

Code Interpreter 환경에서는 가상환경 없이 바로 사용할 수 있습니다.

```bash
# Code Interpreter 환경용 설정 스크립트 실행
./setup_codex_env.sh

# 자동 검증 항목:
# ✅ 환경변수 설정 상태 (7개)
# ✅ 라이브러리 설치 상태 (13개) 
# ✅ 백엔드 모듈 임포트 (7개)
# ✅ 클라이언트 연결 테스트
```

**환경변수 설정:**
```bash
# Code Interpreter에서 환경변수 설정
export FRESHDESK_DOMAIN="yourcompany.freshdesk.com"
export FRESHDESK_API_KEY="your_api_key"
export QDRANT_URL="https://your-cluster.cloud.qdrant.io"
export QDRANT_API_KEY="your_api_key"
export ANTHROPIC_API_KEY="your_api_key"
export COMPANY_ID="your_company_id"
# OPENAI_API_KEY는 자동 제공됨
```

**Python에서 직접 설정 (선택사항):**
```python
import os
os.environ['FRESHDESK_DOMAIN'] = 'yourcompany.freshdesk.com'
os.environ['FRESHDESK_API_KEY'] = 'your_api_key'
os.environ['QDRANT_URL'] = 'https://your-cluster.cloud.qdrant.io'
os.environ['QDRANT_API_KEY'] = 'your_api_key'
os.environ['ANTHROPIC_API_KEY'] = 'your_api_key'
os.environ['COMPANY_ID'] = 'your_company_id'
print("✅ 환경변수 설정 완료")
```

📚 **상세 가이드**: [Code Interpreter 설정 가이드](./CODEX_SETUP.md)

#### 가상환경 사용 (로컬 개발)

```bash
# 가상환경 생성 (최초 1회만 실행)
python -m venv backend/venv

# 가상환경 활성화 (Mac/Linux)
source backend/venv/bin/activate
# 또는 간편하게
cd backend && ./activate.sh

# 필요한 패키지 설치
pip install -r backend/requirements.txt

# 서버 실행
cd backend && python main.py

# 가상환경 비활성화
deactivate
```

#### Docker 환경 사용

```bash
# 도커 컨테이너 실행
cd backend && docker-compose up -d

# 로그 확인
docker logs -f project-a

# 컨테이너 중지
docker-compose down
```

## 주요 구성 요소

- FastAPI 웹 서버
- Qdrant 벡터 데이터베이스
- Freshdesk API 연동
- 다중 LLM 라우터 (Anthropic Claude, OpenAI, Google Gemini)
- 임베딩 및 검색 모듈

## Task Master 사용하기

프로젝트에는 태스크 관리를 위한 Task Master가 통합되어 있습니다. 모든 Task Master 관련 기능은 단일 통합 스크립트(`taskmaster.sh`)를 통해 사용할 수 있습니다.

### 통합 스크립트 사용법

```bash
# 도움말 보기
./taskmaster.sh help

# Task Master 명령 실행 (예: 태스크 목록 확인)
./taskmaster.sh run list

# 다음 태스크 가져오기
./taskmaster.sh run next

# 환경 설정 진단하기
./taskmaster.sh check

# 설정 문제 자동 해결하기
./taskmaster.sh fix

# 환경 변수 로드하기
./taskmaster.sh load-env
```

### 문제 해결

Task Master가 API 키를 인식하지 못하는 경우:

1. `./taskmaster.sh check` 명령으로 현재 상태를 진단하세요.
2. `./taskmaster.sh fix` 명령으로 자동 문제 해결을 시도하세요.
3. 환경 변수가 제대로 로드되었는지 확인하려면 `./taskmaster.sh load-env` 명령을 실행하세요.
