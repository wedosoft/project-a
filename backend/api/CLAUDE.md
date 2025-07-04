# Backend API Layer - CLAUDE.md

## 🎯 컨텍스트 & 목적

이 디렉토리는 **Backend API Layer**로 FastAPI 애플리케이션 레이어, 라우팅, 미들웨어, 의존성 주입 컨테이너를 담당합니다. Copilot Canvas의 모든 HTTP 엔드포인트와 요청/응답 관리를 처리합니다.

**주요 영역:**
- FastAPI 라우트 핸들러 및 미들웨어
- IoC 컨테이너 및 의존성 주입 패턴
- 요청 검증 및 응답 포맷팅
- CORS, 인증, 보안 미들웨어
- 헬스체크 및 모니터링 엔드포인트

## 🏗️ API 구조

```
api/
├── main.py              # FastAPI 애플리케이션 진입점
├── container.py         # IoC 컨테이너 설정
├── routers/            # API 라우터들
│   ├── init.py         # 티켓 초기화 및 분석
│   ├── query.py        # 에이전트 쿼리 처리
│   ├── reply.py        # 응답 제안 생성
│   ├── ingest.py       # 데이터 수집 엔드포인트
│   ├── health.py       # 헬스체크
│   └── metrics.py      # 성능 모니터링
├── middleware/         # 커스텀 미들웨어
├── models/            # Pydantic 모델들
└── utils/             # API 유틸리티
```

## 🚀 주요 엔드포인트

### 1. 티켓 분석 (`/init/{ticket_id}`)
```bash
GET /init/12345
Headers:
  X-Freshdesk-Domain: company.freshdesk.com
  X-Freshdesk-API-Key: your_api_key
```

### 2. 쿼리 처리 (`/query`)
```bash
POST /query
{
  "query": "로그인 문제 해결 방법",
  "context": {...},
  "tenant_id": "company_id"
}
```

### 3. 응답 생성 (`/reply`)
```bash
POST /reply
{
  "conversation": [...],
  "context": {...},
  "language": "ko"
}
```

## 🔧 핵심 기능

### 의존성 주입 컨테이너
```python
from api.container import Container

@inject
async def process_ticket(
    ticket_id: int,
    vector_db: VectorDB = Depends(Container.vector_db),
    llm_manager: LLMManager = Depends(Container.llm_manager)
):
    # 비즈니스 로직 구현
    pass
```

### 미들웨어 체인
```
CORS → 인증 검증 → 요청 로깅 → 성능 측정 → 라우트 핸들러 → 응답 포맷팅 → 에러 처리
```

### 스트리밍 응답
```python
@router.post("/stream-analysis")
async def stream_analysis(request: AnalysisRequest):
    async def generate():
        async for chunk in analyze_ticket_stream(request.ticket_id):
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")
```

## 🚀 개발 명령어

```bash
# 개발 서버 시작
cd backend
source venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 엔드포인트 테스트
curl http://localhost:8000/health
curl -X GET "http://localhost:8000/init/12345" \
     -H "X-Freshdesk-Domain: company.freshdesk.com" \
     -H "X-Freshdesk-API-Key: your_api_key"
```

## ⚠️ 중요 사항

### 보안
- API 키 검증 필수
- 입력 데이터 검증 (Pydantic 모델)
- CORS 정책 설정
- 민감 정보 로그 마스킹

### 성능
- 비동기 처리 (async/await)
- 응답 캐싱
- 요청 타임아웃 설정
- 리소스 풀링

### 모니터링
- Prometheus 메트릭 수집
- 구조화된 로깅 (structlog)
- 헬스체크 엔드포인트
- 에러 추적 및 알림

---

*상세한 라우터별 구현은 각 `routers/*.py` 파일을 참조하세요.*
