# Freshdesk Custom App 백엔드 서비스

이 프로젝트는 Freshdesk Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 기반으로 AI 기반 응답 생성 기능을 제공합니다.

## 프로젝트 문서

- [프로젝트 규칙 및 가이드라인](./PROJECT_RULES.md) - 개발 시 준수해야 할 규칙과 가이드라인
- [환경 구성 가이드](./SETUP.md) - 새로운 개발 환경 구성을 위한 상세 지침

## 시작하기

### 요구사항

- Python 3.10+
- Docker 및 Docker Compose

### 개발 환경 설정

#### 가상환경 사용 (권장)

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
- ChromaDB 벡터 데이터베이스
- Freshdesk API 연동
- 임베딩 및 검색 모듈
