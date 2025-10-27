# 프로젝트 문서 인덱스

## 📚 프로젝트 개요

**프로젝트명**: RAG 기반 Freshdesk 커스텀 앱  
**유형**: AI 기반 고객 지원 어시스턴트  
**아키텍처**: FastAPI 백엔드 + Freshdesk FDK 프론트엔드  
**주요 언어**: Python (백엔드), JavaScript (프론트엔드)  
**데이터베이스**: Qdrant 벡터 데이터베이스 + PostgreSQL

### 핵심 기술 스택
- **백엔드 프레임워크**: FastAPI
- **벡터 데이터베이스**: Qdrant
- **LLM 프로바이더**: OpenAI, Anthropic Claude, Google Gemini, OpenRouter
- **임베딩**: OpenAI text-embedding-3-small, Sentence Transformers
- **프론트엔드**: Freshdesk FDK (Freshworks Development Kit)
- **컨테이너**: Docker & Docker Compose
- **클라우드**: AWS ECS, RDS

### 주요 기능
- 🔍 **벡터 검색**: 티켓과 KB 문서의 의미 기반 유사도 검색
- 🤖 **멀티 LLM 지원**: 여러 AI 프로바이더 간 지능형 라우팅
- 📊 **RAG 시스템**: 정확한 응답을 위한 검색 증강 생성
- 🌐 **멀티테넌트**: tenant_id를 통한 완전한 격리
- ⚡ **RESTful 스트리밍**: 실시간 응답 스트리밍
- 🎯 **관리자 대시보드**: 종합 관리 인터페이스
- 📈 **성능 모니터링**: 내장 메트릭 및 모니터링

## 🏗️ 프로젝트 구조

### 백엔드 아키텍처

```
backend/
├── api/                    # FastAPI 애플리케이션 레이어
│   ├── main.py            # 애플리케이션 진입점
│   ├── routes/            # API 엔드포인트
│   │   ├── init.py        # 티켓 초기화 엔드포인트
│   │   ├── query.py       # 검색 및 쿼리 엔드포인트
│   │   ├── reply.py       # 답변 생성
│   │   ├── ingest_*.py    # 데이터 수집 엔드포인트
│   │   ├── admin_*.py     # 관리자 관리 엔드포인트
│   │   ├── agents*.py     # 에이전트 관리
│   │   └── attachments.py # 파일 첨부 처리
│   └── models/            # Pydantic 모델
│
├── core/                  # 핵심 비즈니스 로직
│   ├── database/          # 데이터베이스 레이어
│   │   ├── vectordb.py    # 벡터 데이터베이스 작업
│   │   ├── postgresql_database.py # PostgreSQL 작업
│   │   └── hybrid_vectordb.py    # 하이브리드 검색 구현
│   ├── llm/              # LLM 통합
│   │   ├── providers/    # LLM 프로바이더 구현
│   │   ├── summarizer/   # 텍스트 요약 시스템
│   │   └── config/       # 모델 설정
│   ├── search/           # 검색 기능
│   │   ├── retriever.py  # 문서 검색
│   │   └── embeddings/   # 임베딩 생성
│   ├── cache/            # 캐싱 레이어
│   └── platforms/        # 플랫폼 통합
│       └── freshdesk/    # Freshdesk API 통합
│
├── config/               # 설정 파일
│   ├── defaults.py       # 기본 설정
│   └── search_weights.yaml # 검색 가중치 설정
│
└── scripts/              # 유틸리티 스크립트
    ├── init_database.py  # 데이터베이스 초기화
    └── setup_rds.py      # AWS RDS 설정
```

### 프론트엔드 아키텍처

```
frontend/
├── app/                  # 메인 애플리케이션
│   ├── index.html       # 메인 대시보드
│   ├── reply.html       # 답변 편집기 인터페이스
│   ├── admin.html       # 관리자 대시보드
│   └── scripts/         # JavaScript 모듈
│       ├── app.js       # 메인 애플리케이션 로직
│       ├── chat.js      # 채팅 인터페이스
│       ├── reply.js     # 답변 처리
│       ├── admin.js     # 관리자 기능
│       └── api.js       # API 통신
│
├── config/              # FDK 설정
│   ├── iparams.json    # 설치 매개변수
│   └── requests.json   # 백엔드 API 설정
│
└── manifest.json        # Freshdesk 앱 매니페스트
```

## 📡 API 문서

### 핵심 엔드포인트

#### 티켓 작업
- `GET /init/{ticket_id}` - 유사 티켓과 문서로 티켓 컨텍스트 초기화
- `GET /init/{ticket_id}/summary` - 티켓 요약 가져오기
- `GET /init/{ticket_id}/similar` - 유사 티켓 찾기
- `GET /init/{ticket_id}/article` - 관련 KB 문서 가져오기
- `GET /init/{ticket_id}/context` - 전체 티켓 컨텍스트 가져오기

#### 검색 및 쿼리
- `POST /query` - 일반 쿼리 엔드포인트
- `POST /hybrid-search` - 하이브리드 검색 (벡터 + 키워드)
- `POST /discovery` - 탐색을 위한 디스커버리 검색
- `POST /feedback` - 검색 피드백 제출

#### 답변 생성
- `POST /reply` - AI 기반 답변 생성

#### 데이터 수집
- `POST /ingest` - 티켓과 KB 문서 수집
- `POST /ingest/jobs` - 수집 작업 생성
- `GET /ingest/jobs` - 수집 작업 목록
- `GET /ingest/jobs/{job_id}` - 작업 상태 확인
- `POST /ingest/jobs/{job_id}/control` - 작업 제어 (일시정지/재개/취소)

#### 관리자 관리
- `GET /admin/status` - 시스템 상태
- `POST /admin/purge` - 데이터 삭제
- `POST /admin/restore` - 데이터 복원
- `GET /admin/scheduler/status` - 스케줄러 상태
- `POST /admin/scheduler/toggle` - 스케줄러 토글
- `POST /admin/scheduler/run-now` - 스케줄러 즉시 실행

#### 에이전트 관리
- `GET /agents` - 모든 에이전트 목록
- `GET /agents/{agent_id}` - 에이전트 상세 정보
- `PUT /agents/{agent_id}/license` - 에이전트 라이선스 업데이트
- `POST /agents/bulk-license` - 대량 라이선스 업데이트
- `POST /agents/sync` - Freshdesk에서 에이전트 동기화

#### 성능 및 모니터링
- `GET /performance/dashboard` - 성능 대시보드
- `GET /performance/metrics/{metric_name}` - 특정 메트릭
- `GET /performance/cache/stats` - 캐시 통계
- `GET /performance/system/resources` - 시스템 리소스

#### 첨부파일
- `GET /attachments/{attachment_id}/download-url` - 다운로드 URL 가져오기
- `GET /attachments/{attachment_id}/metadata` - 첨부파일 메타데이터 가져오기
- `GET /attachments/bulk-urls` - 여러 첨부파일 URL 가져오기

#### 상태 확인
- `GET /health` - 헬스 체크
- `GET /metrics` - 애플리케이션 메트릭

### 인증
- `X-API-Key` 헤더를 통한 API 키 기반 인증
- `X-Tenant-Id` 헤더를 통한 테넌트 격리

## 🔧 설정

### 환경 변수

#### 핵심 설정
- `FRESHDESK_DOMAIN` - Freshdesk 서브도메인
- `FRESHDESK_API_KEY` - Freshdesk API 키
- `QDRANT_URL` - Qdrant 서버 URL
- `QDRANT_API_KEY` - Qdrant API 키
- `COMPANY_ID` - 회사 식별자

#### LLM 설정
- `REALTIME_LLM_PROVIDER` - 실시간 쿼리용 프로바이더
- `REALTIME_LLM_MODEL` - 실시간 쿼리용 모델
- `BATCH_LLM_PROVIDER` - 배치 처리용 프로바이더
- `BATCH_LLM_MODEL` - 배치 처리용 모델
- `SUMMARY_LLM_PROVIDER` - 요약용 프로바이더
- `SUMMARY_LLM_MODEL` - 요약용 모델

#### API 키
- `OPENAI_API_KEY` - OpenAI API 키
- `ANTHROPIC_API_KEY` - Anthropic API 키
- `GEMINI_API_KEY` - Google Gemini API 키
- `OPENROUTER_API_KEY` - OpenRouter API 키

#### 데이터베이스
- `DATABASE_URL` - PostgreSQL 연결 문자열
- `REDIS_URL` - Redis 연결 문자열 (선택사항)

### 설정 파일

#### `backend/config/defaults.py`
기본 애플리케이션 설정 및 상수

#### `backend/config/search_weights.yaml`
다양한 문서 유형에 대한 검색 점수 가중치

#### `frontend/config/iparams.json`
Freshdesk 앱 설치 매개변수

#### `frontend/manifest.json`
권한 및 메타데이터가 포함된 Freshdesk 앱 매니페스트

## 🚀 시작하기

### 사전 요구사항
- Python 3.10+
- Docker & Docker Compose
- Node.js 14+ (프론트엔드용)
- API 액세스가 있는 Freshdesk 계정

### 설치

1. **저장소 클론**
   ```bash
   git clone <repository-url>
   cd project-a-feature-admin
   ```

2. **백엔드 설정**
   ```bash
   # 가상환경 생성
   python -m venv backend/venv
   source backend/venv/bin/activate  # Linux/Mac
   
   # 의존성 설치
   pip install -r backend/requirements.txt
   
   # 환경 변수 설정
   cp .env.example .env
   # .env 파일을 자격 증명으로 편집
   
   # 데이터베이스 초기화
   python backend/scripts/init_database.py
   ```

3. **프론트엔드 설정**
   ```bash
   cd frontend
   npm install
   
   # 백엔드 URL 설정
   # config/requests.json을 백엔드 URL로 편집
   ```

4. **서비스 실행**
   ```bash
   # 백엔드
   cd backend
   uvicorn api.main:app --reload --port 8000
   
   # 프론트엔드 (별도 터미널)
   cd frontend
   fdk run
   ```

### Docker 배포

```bash
# Docker Compose로 빌드 및 실행
docker-compose up -d

# 로그 보기
docker-compose logs -f

# 서비스 중지
docker-compose down
```

## 📊 데이터 플로우

### 수집 파이프라인
1. **데이터 수집**: Freshdesk에서 티켓/문서 가져오기
2. **처리**: 데이터 정제 및 정규화
3. **임베딩**: 벡터 임베딩 생성
4. **저장**: Qdrant와 PostgreSQL에 저장
5. **인덱싱**: 검색 인덱스 생성

### 쿼리 파이프라인
1. **요청**: 사용자 쿼리 수신
2. **임베딩**: 쿼리를 벡터로 변환
3. **검색**: 벡터 DB에서 하이브리드 검색
4. **검색**: 관련 문서 가져오기
5. **생성**: LLM이 응답 생성
6. **스트리밍**: 클라이언트로 응답 스트리밍

### 답변 생성 플로우
1. **컨텍스트 구축**: 티켓 컨텍스트 수집
2. **프롬프트 구성**: 구조화된 프롬프트 구축
3. **LLM 처리**: 선택된 모델로 답변 생성
4. **품질 검증**: 응답 품질 검증
5. **응답 전달**: 포맷된 응답 반환

## 🔐 보안

### 인증 및 권한 부여
- 백엔드 액세스를 위한 API 키 인증
- 테넌트 기반 데이터 격리
- 관리자 기능을 위한 역할 기반 접근 제어 (RBAC)

### 데이터 보호
- 암호화된 데이터 전송 (HTTPS)
- 안전한 자격 증명 저장
- 입력 검증 및 살균
- 속도 제한 및 DDoS 보호

### 규정 준수
- GDPR 준수 데이터 처리
- 민감한 작업에 대한 감사 로깅
- 데이터 보존 정책

## 📈 성능 최적화

### 캐싱 전략
- 빈번한 쿼리를 위한 Redis 기반 캐싱
- 첨부파일 URL 캐싱
- LLM 응답 캐싱
- 검색 결과 캐싱

### 데이터베이스 최적화
- 벡터 인덱스 최적화
- 쿼리 결과 페이지네이션
- 연결 풀링
- 대규모 데이터셋을 위한 배치 처리

### LLM 최적화
- 모델별 토큰 제한
- 스트리밍 응답
- 병렬 처리
- 쿼리 복잡도에 따른 스마트 라우팅

## 🧪 테스트

### 백엔드 테스트
```bash
cd backend
pytest tests/
```

### 프론트엔드 테스트
```bash
cd frontend
npm test
```

### 통합 테스트
```bash
# 전체 통합 테스트 스위트 실행
./scripts/run_integration_tests.sh
```

## 📝 개발 가이드라인

### 코드 스타일
- Python: PEP 8 준수
- JavaScript: ESLint 설정
- Python 함수에 타입 힌트
- JavaScript에 JSDoc 주석

### Git 워크플로우
- `main`에서 기능 브랜치 생성
- 모든 변경사항에 대한 풀 리퀘스트
- 코드 리뷰 필수
- 시맨틱 커밋 메시지

### 문서화
- 코드 변경과 함께 문서 업데이트
- OpenAPI 형식의 API 문서
- 복잡한 로직에 대한 인라인 코드 주석
- 각 주요 컴포넌트에 대한 README 파일

## 🚨 문제 해결

### 일반적인 문제

#### 벡터 데이터베이스 연결
- Qdrant 서버 상태 확인
- API 키와 URL 확인
- 네트워크 연결 확인

#### LLM API 오류
- API 키가 유효한지 확인
- 속도 제한 확인
- 토큰 사용량 모니터링

#### 프론트엔드 로딩 문제
- 브라우저 캐시 지우기
- 백엔드 URL 설정 확인
- CORS 설정 확인

### 로깅
- 백엔드 로그: `backend/backend.log`
- 프론트엔드 로그: 브라우저 콘솔
- Docker 로그: `docker-compose logs`

## 📚 추가 리소스

### 내부 문서
- [프로젝트 규칙](./PROJECT_RULES.md)
- [환경 설정](./SETUP.md)
- [백엔드 리팩토링 보고서](./backend/docs/BACKEND_REFACTORING_COMPLETION_REPORT.md)
- [Docker 가이드](./backend/docs/DOCKER_GUIDE.md)
- [ECS 배포 가이드](./backend/docs/ECS_DEPLOYMENT_GUIDE.md)

### 외부 리소스
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Qdrant 문서](https://qdrant.tech/documentation/)
- [Freshdesk API 참조](https://developers.freshdesk.com/api/)
- [OpenAI API 문서](https://platform.openai.com/docs/)
- [Anthropic Claude 문서](https://docs.anthropic.com/)

## 📞 지원

문제나 질문이 있는 경우:
1. 문제 해결 섹션 확인
2. 기존 문서 검토
3. GitHub 이슈 확인
4. 개발팀에 문의

## 📄 라이선스

[라이선스 정보]

---

*최종 업데이트: 2025년 1월*