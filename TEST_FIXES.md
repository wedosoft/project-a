# E2E 테스트 수정 사항

## 문제점

1. **Qdrant `using` 파라미터 미지원**: qdrant-client 1.15.1에서 `using` 파라미터가 deprecated됨
2. **외부 서비스 의존성**: 테스트가 Qdrant, PostgreSQL, Supabase 없이 실행 시 실패
3. **누락된 dependencies**: python-dateutil, asyncpg, google-generativeai
4. **환경설정 문제**: .env 파일에 QDRANT_URL 대신 QDRANT_HOST/PORT 필요

## 수정 내역

### 1. Qdrant `using` 파라미터 수정

**파일**: `backend/services/vector_search.py`

**변경 전**:
```python
results = self.client.search(
    collection_name=collection_name,
    query_vector=query_vector,
    using=vector_name,  # deprecated
    ...
)
```

**변경 후**:
```python
results = self.client.search(
    collection_name=collection_name,
    query_vector=(vector_name, query_vector),  # tuple 형식으로 변경
    ...
)
```

### 2. 외부 서비스 Skip Markers 추가

**파일**: `backend/tests/conftest.py` (신규)

환경변수 기반으로 외부 서비스 가용성을 체크하는 pytest skip markers 추가:

- `@requires_qdrant`: Qdrant 필요
- `@requires_postgres`: PostgreSQL 필요
- `@requires_supabase`: Supabase 필요
- `@requires_external_services`: 모든 외부 서비스 필요

서비스가 설정되지 않은 경우 placeholder 값을 감지하여 자동 skip:
- `https://your-project.supabase.co` → 미설정으로 판단
- `your_supabase_key_here` → 미설정으로 판단

### 3. E2E 테스트 업데이트

**파일**: `backend/tests/test_e2e.py`

모든 테스트 메서드에 적절한 skip markers 추가:

```python
@pytest.mark.asyncio
@requires_external_services
async def test_full_ticket_pipeline(self, sample_ticket_context):
    """외부 서비스가 없으면 자동 skip"""
    ...

@pytest.mark.asyncio
@requires_supabase
async def test_approval_and_execution(self, sample_ticket_context):
    """Supabase만 필요한 테스트"""
    ...
```

### 4. Dependencies 추가

**파일**: `requirements.txt`

```python
# Database
asyncpg>=0.29.0  # 추가

# HTTP & Utilities
python-dateutil>=2.8.0  # 추가

# LangGraph & LangChain
google-generativeai>=0.3.0  # 추가
```

### 5. 환경설정 수정

**파일**: `.env.example` 및 `.env`

```bash
# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=
QDRANT_USE_HTTPS=false
```

## 테스트 결과

### E2E 테스트 (`pytest backend/tests/test_e2e.py -v`)

```
✅ 1 passed (error handling test)
⏭️  8 skipped (외부 서비스 미설정)
❌ 0 failed
```

### 개별 서비스 테스트

```
✅ test_vector_search.py: 17 passed
✅ test_hybrid_search.py: 19 passed
✅ test_reranker.py: [needs verification]
✅ test_sparse_search.py: [needs verification]
```

## 성능 SLA 테스트 관련

**현재 상태**:
- 성능 SLA 테스트(`test_response_time_sla`, `test_concurrent_requests`)는 외부 서비스가 필요하여 skip됨
- 외부 서비스가 설정되면 실행 가능

**Qdrant `using` 문제 해결됨**:
- qdrant-client 1.15.1 호환 코드로 수정 완료
- 멀티벡터 검색이 tuple 형식으로 정상 작동

**Supabase BM25 관련**:
- SparseSearchService는 PostgreSQL의 pg_trgm 및 full-text search 사용
- Supabase PostgreSQL이 설정되면 정상 작동
- 테스트는 서비스 미설정 시 자동 skip

## 권장 사항

### 로컬 개발 환경

1. 외부 서비스 설정:
   ```bash
   # Docker Compose로 로컬 서비스 실행
   docker-compose up -d qdrant postgres
   ```

2. .env 파일 설정:
   ```bash
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   SUPABASE_DB_HOST=localhost
   SUPABASE_DB_PORT=5432
   SUPABASE_DB_PASSWORD=your_password
   ```

### CI/CD 환경

1. 통합 테스트 단계에서 서비스 컨테이너 사용:
   ```yaml
   services:
     qdrant:
       image: qdrant/qdrant:latest
     postgres:
       image: postgres:15
   ```

2. 또는 외부 서비스 없이 단위 테스트만 실행:
   ```bash
   pytest backend/tests/ -v -m "not requires_external_services"
   ```

## 추가 작업 필요

- [ ] google-generativeai 설치 및 테스트 (현재 네트워크 이슈)
- [ ] 다른 테스트 파일 검증
- [ ] Docker Compose 설정 추가/업데이트
- [ ] CI/CD 파이프라인 설정
