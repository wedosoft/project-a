# 백엔드 테스트 가이드

프론트엔드 없이 백엔드 API만으로 실제 데이터 테스트하는 방법

---

## 🚀 빠른 시작

### 1단계: 환경 확인

```bash
# .env 파일 확인
cat .env

# 필수 환경변수 체크:
# - FRESHDESK_DOMAIN
# - FRESHDESK_API_KEY
# - OPENAI_API_KEY (또는 GOOGLE_API_KEY)
# - QDRANT_URL
# - SUPABASE_URL, SUPABASE_KEY
```

### 2단계: 서비스 시작

```bash
# Qdrant 시작 (로컬)
docker run -d -p 6333:6333 qdrant/qdrant

# FastAPI 백엔드 시작
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3단계: 데이터 시딩 (실제 Freshdesk 데이터)

```bash
# 티켓 50개 + KB 아티클 20개 가져오기
python backend/scripts/seed_data.py --tickets 50 --kb 20

# 티켓만 가져오기 (KB 건너뛰기)
python backend/scripts/seed_data.py --tickets 100 --skip-kb
```

### 4단계: API 테스트

```bash
# 기본 테스트 (헬스체크 + AI 제안 생성)
python backend/scripts/test_api.py

# 특정 티켓으로 테스트
python backend/scripts/test_api.py --ticket-id 12345

# 전체 파이프라인 테스트
python backend/scripts/test_api.py --full-pipeline
```

---

## 📋 테스트 시나리오

### 시나리오 1: 실제 티켓으로 AI 제안 받기

```bash
# 1. 데이터 시딩
python backend/scripts/seed_data.py --tickets 50

# 2. API 테스트
python backend/scripts/test_api.py

# 예상 출력:
# ✅ API 상태: 200
# ✅ 제안 생성 성공 (응답 시간: 3.24초)
#
# 🔍 유사사례: 5개
#   1. [티켓#123] 로그인 오류 - 비밀번호 재설정...
#      점수: 0.892
#   ...
#
# 📚 KB 제안: 2개
#   1. 비밀번호 재설정 절차...
#
# 🏷️ 필드 업데이트 제안:
#   • category: 로그인/인증
#   • priority: 3
#
# 💬 응답 초안:
#   안녕하세요, 비밀번호 재설정 관련 문의 주셔서 감사합니다...
```

### 시나리오 2: E2E 통합 테스트

```bash
# pytest로 전체 파이프라인 테스트
cd backend
pytest tests/test_e2e.py -v -s

# 특정 테스트만 실행
pytest tests/test_e2e.py::TestE2ETicketFlow::test_full_ticket_pipeline -v
```

### 시나리오 3: 성능 벤치마크

```bash
# 응답 시간 측정
pytest tests/test_e2e.py::TestE2EPerformance -v

# 동시 요청 처리 테스트
pytest tests/test_e2e.py::TestE2EPerformance::test_concurrent_requests -v
```

---

## 🔍 curl로 직접 API 호출

### 헬스체크

```bash
curl http://localhost:8000/api/health
```

### AI 제안 생성

```bash
curl -X POST http://localhost:8000/api/assist/test-001/suggest \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{
    "ticket_id": "test-001",
    "subject": "로그인이 안 돼요",
    "description": "비밀번호를 입력했는데 틀렸다고 나옵니다.",
    "customer_email": "test@example.com",
    "priority": 2,
    "status": 2,
    "category": "로그인/인증"
  }'
```

### 승인 처리

```bash
curl -X POST http://localhost:8000/api/assist/test-001/approve \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{
    "action": "approved",
    "feedback": "AI 제안이 정확했습니다.",
    "agent_id": "agent-001"
  }'
```

### Freshdesk 동기화

```bash
curl -X POST http://localhost:8000/api/sync/tickets \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{
    "limit": 10
  }'
```

---

## 🧪 데이터 검증

### Supabase 데이터 확인

```bash
# psql로 직접 쿼리
psql $SUPABASE_DB_CONNECTION_STRING

# SQL 쿼리
SELECT COUNT(*) FROM issue_blocks WHERE tenant_id = 'default';
SELECT COUNT(*) FROM kb_blocks WHERE tenant_id = 'default';
SELECT * FROM approval_logs ORDER BY created_at DESC LIMIT 10;
```

### Qdrant 데이터 확인

```bash
# Qdrant API로 컬렉션 확인
curl http://localhost:6333/collections/issue_embeddings

# 벡터 카운트
curl http://localhost:6333/collections/issue_embeddings | jq '.result.vectors_count'
```

---

## 📊 성능 지표

### 목표 SLA

| 작업 | 목표 시간 | 측정 방법 |
|------|----------|----------|
| 임베딩 생성 | < 500ms | `seed_data.py` 로그 |
| Qdrant 검색 | < 200ms | API 응답 시간 |
| BM25 검색 | < 100ms | API 응답 시간 |
| 재랭킹 | < 1000ms | API 응답 시간 |
| 전체 파이프라인 | < 5초 | E2E 테스트 |

### 벤치마크 실행

```bash
# pytest-benchmark 설치
pip install pytest-benchmark

# 벤치마크 실행
pytest tests/test_e2e.py::TestE2EPerformance --benchmark-only
```

---

## 🐛 트러블슈팅

### 문제 1: Freshdesk API 연결 실패

**증상**: `seed_data.py` 실행 시 "티켓을 가져올 수 없습니다"

**해결**:
```bash
# .env 확인
echo $FRESHDESK_DOMAIN
echo $FRESHDESK_API_KEY

# API 키 테스트
curl -u your_api_key:X https://your_domain.freshdesk.com/api/v2/tickets
```

### 문제 2: Qdrant 연결 실패

**증상**: "Qdrant 저장 실패"

**해결**:
```bash
# Qdrant 실행 확인
docker ps | grep qdrant

# Qdrant 시작
docker run -d -p 6333:6333 qdrant/qdrant

# 연결 테스트
curl http://localhost:6333/collections
```

### 문제 3: LLM API 오류

**증상**: "LLM 호출 실패" 또는 비용 초과

**해결**:
```bash
# API 키 확인
echo $OPENAI_API_KEY

# 더 저렴한 모델 사용 (config.py 수정)
# GPT-4o-mini 또는 Gemini 1.5 Flash
```

### 문제 4: 임베딩 모델 다운로드 느림

**증상**: 첫 실행 시 모델 다운로드에 시간 소요

**해결**:
```bash
# 사전 다운로드
python -c "from sentence_transformers import SentenceTransformer; \
           SentenceTransformer('BAAI/bge-m3')"
```

---

## 📈 다음 단계

1. **프론트엔드 연동** (선택):
   - Freshdesk FDK 앱 업데이트 (명령어 15-16)
   - 백엔드 API 연동

2. **성능 최적화**:
   - 캐싱 추가 (Redis)
   - 배치 처리 최적화

3. **프로덕션 배포**:
   - Docker Compose로 전체 스택 배포
   - 모니터링 설정 (Prometheus, Grafana)

---

## 📚 추가 리소스

- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Qdrant 문서](https://qdrant.tech/documentation/)
- [Freshdesk API](https://developers.freshdesk.com/api/)
- [LangGraph 가이드](https://python.langchain.com/docs/langgraph)
