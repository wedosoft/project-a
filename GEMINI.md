# Gemini 가이드: project-a

이 문서는 Gemini가 "project-a"를 이해하고 효과적으로 상호작용하기 위한 핵심 정보를 제공합니다.

## 1. 프로젝트 개요

- **목적**: 자연어 기반 Freshdesk 상담사 지원 시스템.
- **핵심 기술**: RAG (Retrieval-Augmented Generation), Vector DB (Qdrant), RESTful API.
- **주요 기능**:
    - Vector DB 단독 아키텍처로 SQL 의존성 제거.
    - 데이터 수집(Ingest) 시 LLM 요약 단계를 제거하여 속도 향상.
    - RESTful API (`/init/{ticket_id}`)를 통한 실시간 유사 티켓/KB 검색.
    - 멀티테넌트 지원 (`tenant_id` 기반 데이터 격리).

## 2. 핵심 기술 스택

- **백엔드**:
    - **프레임워크**: FastAPI
    - **데이터베이스**: Qdrant (Vector DB), SQLite, PostgreSQL (선택적)
    - **AI/LLM**:
        - **프로바이더**: OpenAI, Anthropic, Google Gemini
        - **라이브러리**: LangChain, `sentence-transformers` (GPU 임베딩용), `torch`
    - **데이터 모델**: Pydantic v2
    - **비동기**: `anyio`, `httpx`
- **프론트엔드**:
    - JavaScript/TypeScript 기반 프로젝트 (세부 사항은 `frontend/package.json` 참조).
- **도구 및 환경**:
    - **컨테이너**: Docker, Docker Compose
    - **테스트**: `pytest`
    - **코드 품질**: `pre-commit` (`black`, `flake8`, `isort`)

## 3. 프로젝트 구조

```
/
├── backend/
│   ├── api/            # FastAPI 애플리케이션
│   ├── core/           # 핵심 비즈니스 로직 (리팩토링된 모듈)
│   │   ├── database/   # Qdrant, SQLite 관리
│   │   ├── search/     # 하이브리드 검색
│   │   ├── llm/        # 통합 LLM 관리
│   │   └── ...
│   ├── tests/          # Pytest 테스트
│   └── requirements.txt # Python 의존성
├── frontend/           # 프론트엔드 애플리케이션
├── docs/               # 프로젝트 문서
├── scripts/            # 보조 스크립트
├── .pre-commit-config.yaml # 코드 스타일 및 품질 설정
└── pytest.ini          # Pytest 설정
```

## 4. 개발 워크플로우

### 가. 환경 설정

- **3가지 옵션 지원**:
    1.  **Docker**: `cd backend && docker-compose up -d`
    2.  **Python 가상환경**: `cd backend && source venv/bin/activate && pip install -r requirements.txt`
    3.  **Code Interpreter**: `./setup_codex_env.sh`
- **환경 변수**: `FRESHDESK_DOMAIN`, `FRESHDESK_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY` 등 LLM 및 플랫폼 관련 키 설정이 필수. `README.md` 참조.

### 나. 서버 실행

- **프로덕션 모드 (권장)**: 데이터 자동 재수집 문제를 피하기 위해 `--reload` 없이 실행.
  ```bash
  cd backend && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
  ```
- **개발 모드**: 파일 변경 시 자동 리로드. 데이터 수집 중에는 사용에 주의.
  ```bash
  cd backend && uvicorn api.main:app --reload
  ```

### 다. 테스팅 및 품질 관리

- **테스트 실행**:
  ```bash
  pytest
  ```
  - 테스트 파일 위치: `backend/tests/`
  - E2E 테스트: `python backend/test_e2e_real_data.py`

- **코드 스타일 검사 및 수정**:
  ```bash
  pre-commit run --all-files
  ```
  - **주요 규칙**: 라인 길이 100자 제한 (`black`, `flake8`).

## 5. 주요 아키텍처 및 규칙

- **순차 실행 패턴**: 복잡성을 줄이기 위해 기존의 병렬 처리에서 순차 실행으로 변경됨. API 호출 -> 벡터 검색 순으로 진행.
- **필터링**: 코드 레벨 필터링을 제거하고, Qdrant 쿼리 레벨에서 필터링을 수행.
- **Task Master**: `taskmaster.sh` 스크립트를 통해 태스크 관리, 환경 진단 및 수정을 자동화.
- **프로젝트 규칙**: 커밋 전 `PROJECT_RULES.md` 확인 필요.
