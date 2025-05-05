# project-a 환경 구성 가이드

이 문서는 다른 컴퓨터에서 project-a 프로젝트의 개발 환경을 동일하게 구성하는 방법을 안내합니다.

## 사전 요구사항

프로젝트를 설정하기 전에 다음 소프트웨어가 설치되어 있어야 합니다:

- Git
- Python 3.10 이상
- Docker 및 Docker Compose (도커 환경 사용 시 필요)
- Visual Studio Code (권장 IDE)

## 프로젝트 클론

```bash
# 프로젝트를 클론할 디렉토리로 이동
cd ~/GitHub  # 또는 원하는 위치

# 프로젝트 클론
git clone [프로젝트 저장소 URL] project-a
cd project-a
```

## 개발 환경 설정

### 가상환경 방식 (권장)

```bash
# 가상환경 생성
python -m venv backend/venv

# 가상환경 활성화 (macOS/Linux)
source backend/venv/bin/activate
# 또는 Windows에서는
# backend\venv\Scripts\activate

# 필요한 패키지 설치
pip install -r backend/requirements.txt
```

### Docker 방식

```bash
# 디렉토리 이동
cd backend

# 환경 변수 파일 생성 (아래 섹션 참조)

# Docker 컨테이너 실행
docker-compose up -d
```

## 환경 변수 설정

`.env` 파일은 보안상의 이유로 Git에 포함되지 않습니다. 다음 내용으로 `backend/.env` 파일을 생성해야 합니다:

```
# API 키
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Freshdesk API 설정
FRESHDESK_DOMAIN=your_freshdesk_domain
FRESHDESK_API_KEY=your_freshdesk_api_key
```

실제 키 값은 프로젝트 관리자에게 요청하세요.

## VS Code 설정

VS Code에서 프로젝트를 열고 권장 확장 프로그램을 설치합니다:
- Python 및 Pylance
- Docker
- Black Formatter
- Python Docstring Generator
- Markdown All in One

프로젝트를 VS Code에서 열려면:
```bash
code project-a.code-workspace
```

VS Code는 이미 프로젝트에 포함된 `.vscode` 설정을 사용하여 자동으로 가상환경을 인식합니다.

## 애플리케이션 실행

### 가상환경 방식

```bash
# 가상환경이 활성화된 상태에서
cd backend
python main.py

# 또는 간편하게 (macOS/Linux)
cd backend
./activate.sh
python main.py
```

### Docker 방식

```bash
cd backend
docker-compose up -d

# 로그 확인
docker logs -f project-a
```

## 데이터 수집 실행

처음 설정 후 또는 데이터를 갱신하려면 다음 명령어를 실행합니다:

```bash
# 가상환경이 활성화된 상태에서
cd backend
python ingest.py
```

## 문제 해결

### Python 관련 문제

시스템 의존성 문제가 발생하는 경우:
- macOS: `brew install python@3.10` 으로 Python 3.10 설치
- Linux: `sudo apt install python3.10-venv python3.10-dev` 등으로 필요한 패키지 설치
- Windows: Python 공식 웹사이트에서 Python 3.10 설치

### Docker 관련 문제

Docker 실행 문제가 발생하는 경우:
- Docker Desktop이 실행 중인지 확인
- `docker-compose down --volumes`로 컨테이너를 완전히 제거한 후 다시 시작

### 패키지 설치 문제

특정 패키지 설치가 실패하는 경우:
- macOS: `brew install pkg-config` 및 필요한 시스템 라이브러리 설치
- Linux: `sudo apt install build-essential python3-dev` 설치

## 개발 작업 시작

모든 개발은 [프로젝트 규칙 및 가이드라인](./PROJECT_RULES.md)을 따라야 합니다. 코드 작성 전에 반드시 이 문서를 검토하세요.

## 파일 구조 이해

```
backend/
├── main.py           # 백엔드 서버의 진입점
├── embedder.py       # 문서 임베딩 모듈
├── fetcher.py        # Freshdesk 데이터 수집 모듈
├── retriever.py      # 벡터 검색 모듈
├── ingest.py         # 데이터 수집 및 저장 스크립트
├── requirements.txt  # 필요한 패키지 목록
├── docker-compose.yml # Docker 구성 파일
└── Dockerfile        # Docker 이미지 빌드 파일
```

## 기여 방법

프로젝트에 기여하는 방법은 [CONTRIBUTING.md](./CONTRIBUTING.md)를 참조하세요.