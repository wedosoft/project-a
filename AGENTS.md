# 🤖 Project-A LangChain Agent 가이드 (AGENT.md)

이 문서는 `project-a-langchain` 프로젝트를 위한 Codex 기반 AI 에이전트의 작동 방식, 규약, 핵심 명령어를 정의합니다. 에이전트는 이 가이드를 참고하여 코드베이스를 이해하고, 개발 작업을 자동화하며, 프로젝트 표준을 준수합니다.

---

## 🎯 1. 에이전트의 역할과 목적

**Project-A LangChain Agent**는 단순한 코드 자동완성 도구를 넘어, 프로젝트의 맥락을 이해하고 복잡한 개발 작업을 수행하는 **소프트웨어 엔지니어링 동료**입니다. 주요 역할은 다음과 같습니다.

* **기능 개발:** FastAPI 엔드포인트 추가, 데이터 처리 로직 구현 등 새로운 기능을 개발합니다.
* **버그 수정:** 기존 코드의 논리적 오류를 분석하고 수정 제안(Pull Request)을 생성합니다.
* **테스트 자동화:** `pytest`를 사용하여 기존 기능의 테스트 코드를 작성하고 실행합니다.
* **Qdrant DB 관리:** `backend/core/vectordb.py`를 참고하여 벡터DB 스키마 변경, 데이터 마이그레이션 스크립트 작성을 지원합니다.
* **Freshdesk 연동:** `backend/freshdesk/fetcher.py`의 로직을 기반으로 데이터 수집 및 처리 관련 작업을 자동화합니다.

---

## 🏛️ 2. 아키텍처 및 핵심 파일 가이드

에이전트는 아래 파일들을 중심으로 프로젝트의 구조와 핵심 로직을 파악해야 합니다.

* **`backend/api/main.py`**: FastAPI 애플리케이션의 메인 진입점. API 라우팅 구조를 파악하는 데 사용됩니다.
* **`backend/core/config.py`**: Pydantic을 이용한 환경변수 및 설정 관리. API 키나 DB 주소 등 핵심 설정은 이곳을 통해 주입됩니다.
* **`backend/core/vectordb.py`**: Qdrant 벡터 데이터베이스와의 모든 상호작용을 담당하는 핵심 모듈입니다.
* **`backend/core/retriever.py`**: LangChain Retriever를 구현하여 Qdrant DB로부터 정보를 검색하는 로직이 담겨있습니다.
* **`docker-compose.yml`**: 프로젝트의 서비스(백엔드, Qdrant DB 등) 구성과 네트워크를 정의합니다.
* **`.pre-commit-config.yaml`**: 코드 포맷팅(black, ruff) 및 린트 규칙이 정의되어 있습니다. 모든 코드 변경은 이 규칙을 따라야 합니다.

---

## ⚙️ 3. 핵심 명령어 및 실행 규약

에이전트가 작업을 수행할 때 사용하는 기본 명령어입니다. 모든 명령어는 프로젝트 루트 디렉터리에서 실행하는 것을 원칙으로 합니다.

| 목적 | 명령어 | 설명 |
| :--- | :--- | :--- |
| **환경 설정** | `source backend/venv/bin/activate` | 가상환경을 활성화합니다. |
| **의존성 설치** | `pip install -r backend/requirements.txt` | 백엔드 개발에 필요한 라이브러리를 설치합니다. |
| **백엔드 실행**| `uvicorn backend.api.main:app --reload` | FastAPI 개발 서버를 실행합니다. |
| **전체 테스트** | `pytest backend/tests/` | 프로젝트의 모든 테스트를 실행합니다. |
| **특정 파일 테스트** | `pytest backend/tests/test_search.py` | 지정된 파일의 테스트만 실행합니다. |
| **코드 포맷팅** | `pre-commit run --all-files` | `.pre-commit-config.yaml`에 정의된 툴로 전체 코드를 포맷팅합니다. |

---

## ✅ 4. 작업 절차 및 준수사항

1.  **요구사항 분석**: 주어진 태스크(예: "Task-001.txt")의 내용을 명확히 이해합니다.
2.  **파일 탐색 및 이해**: `AGENT.md`의 '아키텍처 가이드'를 기반으로 관련 파일을 파악하고 수정 계획을 세웁니다.
3.  **코드 수정 및 작성**: **점진적으로** 코드를 수정합니다. 한 번에 너무 많은 변경을 만들지 않습니다.
4.  **테스트**: 코드 수정 후, 반드시 관련 테스트를 실행하여 기존 기능이 깨지지 않았는지(`Non-regression`) 확인합니다.
5.  **PR 제안**: 모든 테스트가 통과하면, 변경 사항에 대한 명확한 설명과 함께 Pull Request를 제안합니다.

> ⚠️ **중요**: 에이전트는 `OPENAI_API_KEY`와 같은 민감 정보를 코드에 직접 하드코딩해서는 안 됩니다. 항상 `backend/core/config.py`의 설정 모델을 통해 환경변수에서 값을 참조해야 합니다.
