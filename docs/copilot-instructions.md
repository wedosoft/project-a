# GitHub Copilot Instructions for Freshdesk Custom App Backend

## 프로젝트 개요

이 프로젝트는 Freshdesk Custom App (Prompt Canvas)을 위한 RAG 기반 백엔드 서비스입니다.

## 기술 스택

- **백엔드**: Python 3.10, FastAPI (async/await)
- **벡터 DB**: Qdrant Cloud
- **임베딩**: OpenAI Embeddings
- **LLM**: Anthropic Claude, OpenAI GPT, Google Gemini (LLM Router 패턴)
- **외부 API**: Freshdesk API (티켓, 지식베이스)
- **컨테이너**: Docker, docker-compose
- **프론트엔드**: BlockNote 에디터, Freshdesk FDK

## 코딩 규칙 및 가이드라인

### 1. 아키텍처 원칙

- 모듈식 설계와 단일 책임 원칙 준수
- MVP 원칙에 따른 간단하고 실용적인 구현
- 비동기 처리 (async/await) 적극 활용
- 환경변수를 통한 설정 관리

### 2. 파일 구조 규칙

```
backend/
├── api/           # FastAPI 엔드포인트
├── core/          # 핵심 비즈니스 로직
├── freshdesk/     # Freshdesk API 연동
├── data/          # 데이터 처리 및 저장
└── docs/          # 문서
```

### 3. 코딩 스타일

- **타입 힌트**: 모든 함수에 타입 힌트 필수
- **문서화**: 독스트링과 인라인 주석 필수
- **에러 처리**: try-catch 블록과 적절한 로깅
- **로깅**: 구조화된 로깅 (JSON 형태 권장)
- **한글 주석 필수**: 모든 코드의 주석과 설명은 반드시 한글로 작성
- **충실한 주석**: 코드의 의도, 비즈니스 로직, 복잡한 알고리즘에 대한 상세한 한글 설명 추가

### 4. 핵심 컴포넌트

#### LLM Router (core/llm_router.py)

- 다중 LLM 제공자 지원 (Anthropic, OpenAI, Gemini)
- 자동 폴백 및 로드 밸런싱
- 성능 메트릭 수집

#### Qdrant Vector DB (core/vectordb.py)

- company_id 기반 데이터 분리
- 효율적인 벡터 검색 및 필터링
- 메타데이터 관리

#### Freshdesk 연동 (freshdesk/)

- 대용량 데이터 수집 최적화
- Rate limit 및 에러 복구
- 티켓과 지식베이스 동시 처리

### 5. API 설계 원칙

- RESTful API 설계
- 적절한 HTTP 상태 코드 사용
- 요청/응답 모델 정의 (Pydantic)
- CORS 및 보안 헤더 설정

### 6. 성능 최적화

- 비동기 I/O 적극 활용
- 벡터 검색 결과 캐싱
- 배치 처리 및 청크 단위 작업
- 메모리 사용량 모니터링

### 7. 에러 처리 및 로깅

- 구조화된 에러 응답
- 상세한 로깅 (요청 ID, 성능 메트릭)
- Freshdesk API 에러 복구 로직
- 벡터 DB 연결 실패 처리

### 8. 환경 설정

필수 환경변수:

```bash
# Freshdesk
FRESHDESK_DOMAIN=your-domain.freshdesk.com
FRESHDESK_API_KEY=your-api-key

# Qdrant Cloud
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-api-key

# LLM APIs
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
GOOGLE_API_KEY=your-key

# Settings
COMPANY_ID=your-company-id
PROCESS_ATTACHMENTS=true
EMBEDDING_MODEL=text-embedding-3-small
```

### 9. 특별 고려사항

#### Freshdesk 대용량 데이터 처리

- 500만건+ 티켓 처리 최적화
- 청크 단위 수집 및 저장
- 진행률 모니터링 및 중단/재개 지원

#### 멀티테넌트 지원

- company_id 기반 데이터 분리
- 고객사별 설정 관리
- 보안 및 격리 보장

#### BlockNote 에디터 연동

- 블록 기반 응답 생성
- 리치 텍스트 포맷 지원
- 실시간 편집 기능

### 10. 테스트 및 디버깅

- 단위 테스트 작성 권장
- API 엔드포인트 테스트
- Freshdesk API 모킹
- 성능 벤치마크

## 주요 작업 패턴

### 새로운 API 엔드포인트 추가

1. Pydantic 모델 정의 (request/response)
2. 비즈니스 로직을 core/ 모듈에 구현
3. FastAPI 라우터에 엔드포인트 추가
4. 에러 처리 및 로깅 추가
5. 문서화 업데이트

### Freshdesk 데이터 처리

1. fetcher.py에서 API 호출 로직 구현
2. 데이터 전처리 및 검증
3. 벡터 임베딩 생성
4. Qdrant에 저장 (company_id 포함)
5. 로깅 및 모니터링

### LLM 통합

1. llm_router.py에 새 제공자 추가
2. 프롬프트 템플릿 정의
3. 응답 검증 및 후처리
4. 에러 처리 및 폴백 로직

## 디버깅 팁

- Docker 로그: `docker logs -f project-a`
- Qdrant 상태: 대시보드 또는 API 직접 조회
- Freshdesk API: Rate limit 및 권한 확인
- 성능 이슈: 프로파일링 및 메트릭 수집

## 한글 주석 및 문서화 가이드라인

### 필수 주석 항목

1. **함수/클래스 독스트링**: 모든 함수와 클래스에 한글 독스트링 필수

   ```python
   def process_ticket_data(ticket_id: str) -> Dict[str, Any]:
       """
       티켓 데이터를 처리하고 벡터 임베딩을 생성합니다.

       Args:
           ticket_id: 처리할 티켓의 고유 ID

       Returns:
           처리된 티켓 데이터와 메타데이터를 포함한 딕셔너리

       Raises:
           ValueError: 유효하지 않은 티켓 ID인 경우
       """
   ```

2. **비즈니스 로직 설명**: 복잡한 비즈니스 로직에는 상세한 한글 설명 추가

   ```python
   # Freshdesk API에서 대용량 데이터를 청크 단위로 가져오는 로직
   # Rate limit을 고려하여 요청 간격을 조절합니다
   for chunk in paginate_tickets(start_date, end_date):
       # 각 청크는 최대 100개 티켓을 포함
       processed_chunk = await process_ticket_chunk(chunk)
   ```

3. **알고리즘 및 최적화 설명**: 성능 최적화나 특별한 알고리즘 사용 시 이유 설명

   ```python
   # Vector DB 검색 성능 향상을 위해 임베딩을 배치 단위로 처리
   # 메모리 사용량을 제한하기 위해 청크 크기를 1000개로 설정
   EMBEDDING_BATCH_SIZE = 1000
   ```

4. **설정 및 환경변수 설명**: 환경변수나 설정값의 용도와 기본값 설명
   ```python
   # Qdrant 클라우드 연결을 위한 설정
   # QDRANT_URL: Qdrant 클러스터 URL (필수)
   # QDRANT_API_KEY: API 키 (필수)
   QDRANT_URL = os.getenv("QDRANT_URL")
   ```

### 코드 수정 시 주의사항

- 기존 코드 수정 시 변경 이유와 영향을 주석으로 명시
- 임시 해결책이나 TODO 항목은 명확히 표시
- 외부 API 연동 시 에러 처리 로직과 재시도 정책 설명
- 성능에 민감한 부분은 벤치마크 결과나 측정 기준 명시

이 가이드라인을 따라 안정적이고 확장 가능한 코드를 작성해 주세요.
