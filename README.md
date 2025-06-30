# 자연어 기반 Freshdesk 상담사 지원 시스템

이 프로젝트는 Freshdesk Custom App을 위한 자연어 기반 상담사 지원 시스템입니다.
Vector DB 단독 아키텍처와 RESTful 스트리밍을 통한 실시간 티켓 검색, RAG(Retrieval-Augmented Generation) 기술을 활용하여 상담사의 업무 효율성을 극대화합니다.

## ✅ 완성된 핵심 기능 (2025-01-05)

### 🎯 **Vector DB 단독 아키텍처**

- **SQL 의존성 제거**: 모든 데이터를 Vector DB에만 저장, 빠른 검색
- **원본 텍스트 중심**: 티켓/KB 문서 원본을 그대로 저장, LLM 요약 제거
- **확장된 메타데이터**: 첨부파일, 커스텀필드, 대화 등 모든 원본 정보 포함

### ⚙️ **요약 프로세스 완전 제거**

- **Ingest 최적화**: LLM 요약 생성 단계 완전 제거, 빠른 데이터 수집
- **원본 텍스트 활용**: title + description_text만 임베딩, 검색 정확도 향상
- **실시간 응답**: 요약 없이 즉시 원본 텍스트 제공

### 🚀 **RESTful 검색 시스템**

- **GET 방식 검색**: `/init/{ticket_id}` RESTful 엔드포인트
- **Vector DB 검색**: 의미기반 유사 티켓/KB 문서 검색
- **풍부한 메타데이터**: 원본 정보와 확장 메타데이터 제공

### 🏗️ **모듈화된 아키텍처**

- **Vector DB 모듈화**: vectordb.py 독립 모듈, 재사용 가능한 구조
- **환경변수 제어**: ENABLE_FULL_STREAMING_MODE로 Vector DB/하이브리드 모드 선택
- **멀티테넌트**: tenant_id 기반 완전한 격리

## 프로젝트 문서

- [프로젝트 규칙 및 가이드라인](./PROJECT_RULES.md) - 개발 시 준수해야 할 규칙과 가이드라인
- [환경 구성 가이드](./SETUP.md) - 새로운 개발 환경 구성을 위한 상세 지침

## 🔄 다음 우선순위 작업

- **🎨 프론트엔드 UI 구현**: 새로운 Vector DB 필드 구조 기반 UI 구현
- **🔍 확장 메타데이터 필터링**: 첨부파일/카테고리/커스텀필드 등 정교한 검색
- **📊 원본 텍스트 표시 최적화**: 긴 원본 텍스트의 UI/UX 개선
- **⚡ End-to-End 테스트**: Vector DB 단독 모드 전체 플로우 검증

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

**환경변수 설정 (LLM 관리 시스템):**

```bash
# Code Interpreter에서 환경변수 설정

# 기본 플랫폼 설정
export FRESHDESK_DOMAIN="yourcompany.freshdesk.com"
export FRESHDESK_API_KEY="your_api_key"
export QDRANT_URL="https://your-cluster.cloud.qdrant.io"
export QDRANT_API_KEY="your_api_key"
export COMPANY_ID="your_company_id"

# LLM 사용사례별 모델 설정 (환경변수 기반 관리)
export REALTIME_LLM_PROVIDER="openai"
export REALTIME_LLM_MODEL="gpt-4-turbo"
export BATCH_LLM_PROVIDER="anthropic"
export BATCH_LLM_MODEL="claude-3-haiku-20240307"
export SUMMARY_LLM_PROVIDER="openai"
export SUMMARY_LLM_MODEL="gpt-3.5-turbo"

# API 키 설정
export ANTHROPIC_API_KEY="your_api_key"
# OPENAI_API_KEY는 자동 제공됨
```

**Python에서 직접 설정 (선택사항):**

```python
import os

# 기본 설정
os.environ['FRESHDESK_DOMAIN'] = 'yourcompany.freshdesk.com'
os.environ['FRESHDESK_API_KEY'] = 'your_api_key'
os.environ['QDRANT_URL'] = 'https://your-cluster.cloud.qdrant.io'
os.environ['QDRANT_API_KEY'] = 'your_api_key'
os.environ['COMPANY_ID'] = 'your_company_id'

# LLM 관리 설정 (즉시 적용)
os.environ['REALTIME_LLM_PROVIDER'] = 'openai'
os.environ['REALTIME_LLM_MODEL'] = 'gpt-4-turbo'
os.environ['BATCH_LLM_PROVIDER'] = 'anthropic'
os.environ['BATCH_LLM_MODEL'] = 'claude-3-haiku-20240307'

print("✅ 환경변수 기반 LLM 관리 시스템 설정 완료")
print("🚀 재시작 없이 모델 전환 가능")
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

---

## 🎉 최신 업데이트 (2025년 6월 21일)

### ✅ Backend Core 대규모 리팩토링 완료!

**프로젝트 구조가 대폭 개선되었습니다:**

#### 🏗️ 새로운 Backend 구조

```
backend/core/
├── database/     # Qdrant 벡터DB, SQLite 관리
├── data/         # Pydantic 모델, 데이터 스키마
├── search/       # 하이브리드 검색, GPU 임베딩 최적화
├── processing/   # 데이터 처리 파이프라인
├── llm/         # 통합 LLM 관리 (OpenAI, Anthropic, Gemini)
├── platforms/   # Freshdesk 등 플랫폼 어댑터
├── ingest/      # 데이터 수집 시스템
└── legacy/      # 레거시 코드 보관
```

#### 🚀 주요 개선사항

- **모듈화 완료**: 33개 분산 파일 → 8개 체계적 모듈
- **성능 향상**: GPU 임베딩 (`torch`, `sentence-transformers`) 지원
- **LLM 통합**: 모든 LLM 프로바이더 단일 인터페이스로 통합
- **확장성**: 새로운 플랫폼 추가 용이성 대폭 개선
- **안정성**: Pydantic v2 완전 호환, 타입 안정성 강화

#### 📋 자세한 내용

- **[리팩토링 완료 보고서](./backend/docs/BACKEND_REFACTORING_COMPLETION_REPORT.md)**
- **[업데이트된 아키텍처 가이드](./.github/instructions/core/system-architecture.instructions.md)**
