<<<<<<< HEAD
# CLAUDE.md - 프로젝트별 지침

이 파일은 **RAG 기반 Freshdesk Custom App** 프로젝트에서 Claude Code와 작업할 때 적용되는 프로젝트별 지침을 제공합니다.

## 🎯 프로젝트 개요

이 프로젝트는 RAG (Retrieval-Augmented Generation) 기반의 Freshdesk 커스텀 앱 백엔드 서비스입니다. Freshdesk 티켓과 지식베이스 문서를 활용한 AI 기반 응답 생성을 제공합니다.

**기술 스택:**
- FastAPI 백엔드 (async/await 패턴)
- Qdrant 벡터 데이터베이스 (문서 저장 및 유사도 검색)
- 다중 LLM 제공자 (OpenAI, Anthropic, Gemini) 지능형 라우팅
- Docker 컨테이너화 (docker-compose)

## ⚡ 성능 최적화 현황

### 현재 상황
/init/{ticket_id} 호출 시 총 소요시간이 24초인 성능 이슈 확인됨. 조회하는 티켓과 유사티켓 요약 최적화가 필요한 상태입니다.

### 작업 유형: Performance Optimization
- **우선순위**: 중간
- **예상 시간**: 30분 이내 (빠른 작업)

### � 작업 지침
1. **병목 지점 분석**: 프로파일링으로 느린 부분 찾기
2. **측정 가능한 개선**: 개선 전후 성능 수치 비교
3. **점진적 최적화**: 작은 개선들을 누적

### 🎯 작업 범위
- backend/core/database/ (DB 쿼리 최적화)
- backend/core/search/ (검색 성능 개선)
- backend/core/processing/ (데이터 처리 속도)
- 메모리 사용량 최적화

### ⛔ 금지사항
- 기능 변경 또는 제거
- 새로운 의존성 추가 (꼭 필요한 경우만)
- API 인터페이스 변경

## �📁 프로젝트 구조

```
🏠 Project Root/
├─ backend/           # Python FastAPI 백엔드
│  ├─ api/           # API 엔드포인트 레이어
│  ├─ core/          # 핵심 비즈니스 로직
│  │  ├─ database/   # 데이터베이스 추상화
│  │  ├─ llm/        # LLM 관리 및 통합
│  │  ├─ ingest/     # 데이터 수집 파이프라인
│  │  └─ search/     # 검색 엔진 로직
│  └─ platforms/     # 플랫폼별 통합 (Freshdesk 등)
├─ frontend/         # FDK JavaScript 프론트엔드
│  ├─ app/          # 메인 애플리케이션
│  └─ config/       # FDK 설정
└─ docs/            # 프로젝트 문서화
```

## 🚀 개발 환경 설정

### 필수 사전 조건
- Python 3.10+
- Node.js 16+ (FDK 개발용)
- Docker & Docker Compose
- Git

### 백엔드 개발 환경
```bash
# 가상환경 설정 (최초 1회)
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 일일 개발 워크플로우
cd backend
source venv/bin/activate  # Python 명령어 실행 전 항상 활성화

# 개발 서버 실행
python -m api.main

# Docker 환경
docker-compose up -d
```

### 프론트엔드 개발 환경
```bash
# FDK 설치 (최초 1회)
npm install -g @freshworks/fdk

# 개발 서버 실행
cd frontend
fdk run

# 앱 검증
fdk validate
```

**⚠️ 중요**: Python 명령어는 반드시 `backend/` 디렉토리에서 가상환경 활성화 후 실행하세요.

## 🔧 핵심 환경변수

```bash
# 플랫폼 설정
FRESHDESK_DOMAIN=yourcompany.freshdesk.com
FRESHDESK_API_KEY=your_api_key
COMPANY_ID=your_company_id

# 벡터 데이터베이스
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_api_key

# LLM API 키
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIzaSy...

# 모델 설정 (사용 사례별)
TICKET_VIEW_MODEL_PROVIDER=gemini
TICKET_VIEW_MODEL_NAME=gemini-1.5-flash
TICKET_SIMILAR_MODEL_PROVIDER=gemini
TICKET_SIMILAR_MODEL_NAME=gemini-1.5-flash
```

## 🏗️ 아키텍처 개요

### 핵심 컴포넌트

1. **API 레이어** (`backend/api/`)
   - FastAPI 애플리케이션과 IoC 컨테이너
   - 다중 라우터: init, query, reply, ingest, health, metrics
   - CORS, 성능 모니터링, 오류 처리 미들웨어

2. **벡터 데이터베이스** (`backend/core/database/`)
   - Qdrant 어댑터 구현을 통한 추상 인터페이스
   - 완전한 데이터 격리를 통한 멀티테넌트 지원
   - 플랫폼 중립적 3-tuple ID 시스템: `(tenant_id, platform, original_id)`

3. **LLM 관리** (`backend/core/llm/`)
   - 다중 LLM 제공자의 중앙화된 관리
   - 사용 사례 기반 라우팅 (ticket_view, ticket_similar, summary)
   - TTL을 통한 응답 및 임베딩 캐싱

4. **데이터 처리** (`backend/core/ingest/`)
   - Vector 전용 및 하이브리드 (SQL+Vector) 모드 지원
   - 진행 상황 추적을 통한 배치 처리
   - OCR 지원을 통한 첨부파일 처리

### 핵심 설계 패턴
- **멀티테넌시**: tenant_id를 통한 완전한 데이터 격리
- **비동기 처리**: 성능 향상을 위한 모든 I/O 작업의 비동기화
- **의존성 주입**: 테스트 가능성을 위한 IoC 컨테이너 패턴
- **어댑터 패턴**: 플랫폼 독립적 통합 (Freshdesk, 향후 플랫폼)

## 🔍 일반적인 개발 작업

### 테스트 실행
```bash
# 백엔드 테스트
cd backend
source venv/bin/activate
pytest tests/

# 특정 테스트
python tests/test_vectordb.py
python tests/test_llm_simple.py

# 프론트엔드 테스트
cd frontend
npm test
```

### 데이터 수집
```bash
# Freshdesk 데이터 수집
cd backend/platforms/freshdesk
python run_collection.py

# 수집 진행 상황 모니터링
bash scripts/monitor_collection.sh
```

### 디버깅 도구
```bash
# LLM 관리자 테스트
python -c "from core.llm.manager import LLMManager; manager = LLMManager(); print('Available providers:', manager.get_available_providers())"

# 벡터 검색 테스트
python -c "from core.database.vectordb import get_vector_db; db = get_vector_db(); print('Vector DB 연결 성공')"

# 요약 품질 테스트
python tests/test_summary_quality.py
```

## 🚨 주요 컨벤션

### 다국어 지원
- 내부 문서/주석: 한국어 작성 필수
- 사용자 대상 오류 메시지: 한국어
- API 응답: 요청에 따라 한국어/영어
- 변수/함수명: 영어 (국제 표준)

### 성능 고려사항
- LLM 토큰 사용량 모니터링
- 요청 타임아웃 및 재시도 구현
- 적절한 top_k 값으로 벡터 검색 최적화
- Prometheus 메트릭을 통한 모니터링

### 문서 타입
- `ticket`: 대화가 포함된 지원 티켓
- `kb`: 지식베이스 문서
- `faq`: 별도 점수 체계를 가진 FAQ 문서

## 🎯 Claude Code 7-Rule 워크플로우
1. **계획**: 성능 병목 지점을 체계적으로 분석하고 우선순위 결정
2. **체크리스트**: 측정-최적화-검증 사이클을 반복
3. **검토**: 각 최적화마다 성능 개선 수치를 측정하고 검토
4. **보안**: 최적화가 보안성이나 데이터 무결성에 영향 없는지 확인
5. **학습**: 성능 최적화 기법과 측정 방법을 문서화
6. **피드백**: 최적화 후 전체 시스템 성능을 모니터링
7. **반복**: 성능 개선 노하우를 다른 영역에 적용

## ✅ 성능 최적화 완료 체크리스트
- [ ] 현재 성능 측정 완료
- [ ] 병목 지점 파악
- [ ] 최적화 코드 구현
- [ ] 성능 개선 확인 (수치로)
- [ ] 기존 기능 정상 동작 확인

---

## 📚 컴포넌트별 상세 지침

이 프로젝트의 각 컴포넌트에 대한 상세한 지침은 다음 파일들을 참조하세요:

- **Backend API Core**: `backend/CLAUDE.md`
- **API Layer**: `backend/api/CLAUDE.md`
- **LLM Management**: `backend/core/llm/CLAUDE.md`
- **Database & Vector DB**: `backend/core/database/CLAUDE.md`
- **Vector Search Engine**: `backend/core/search/CLAUDE.md`
- **Data Pipeline**: `backend/core/ingest/CLAUDE.md`
- **Frontend FDK**: `frontend/CLAUDE.md`

**전역 개발 원칙은 `/Users/alan/.claude/CLAUDE.md`에서 관리됩니다.**

---

## 🧪 프론트엔드 스트리밍 실험 현황

### 실험 목표
Frontend `/init/ticket-id` 호출을 통해서 백엔드 데이터를 스트리밍으로 정확히 받아오는지 테스트합니다. 상담원 페이지에서 보여지는 모달창은 `index.html`을 사용하며 먼저 사이드바에서 페이지 로딩시 데이터를 미리 호출하고 사용자가 호출 시 로딩이 진행 혹은 완료 되어야 합니다.

### 작업 유형: Experiment
- **우선순위**: 낮음
- **예상 시간**: 30분 이내 (빠른 작업)

### 📋 작업 지침
1. **안전한 실험**: 기존 시스템에 영향 주지 않기
2. **별도 파일**: 새 파일로 실험, 기존 파일 최소 수정
3. **문서화**: 실험 과정과 결과 기록

### 🎯 작업 범위
- 새로운 접근법 테스트
- 라이브러리/도구 평가
- 프로토타입 개발
- A/B 테스트 구현

### ⛔ 금지사항
- 프로덕션 코드 직접 수정
- 기존 API 변경
- 데이터베이스 스키마 변경

### ✅ 실험 완료 체크리스트
- [ ] 실험 계획 수립
- [ ] 별도 환경에서 테스트
- [ ] 결과 측정 및 분석
- [ ] 문서화 완료
- [ ] 기존 시스템 영향 없음 확인
