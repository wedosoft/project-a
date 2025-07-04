# 백엔드 개발 가이드

## 🎯 프로젝트 컨텍스트
- **프로젝트**: RAG 기반 Freshdesk Custom App 백엔드
- **기술 스택**: FastAPI + Qdrant + 멀티 LLM 아키텍처
- **핵심 목표**: 성능 최적화 및 멀티테넌트 지원

## 🏗️ 아키텍처 패턴

### IoC Container 패턴
```python
# 의존성 주입으로 테스트 가능한 구조
class ServiceManager:
    def __init__(self, db_adapter, llm_manager, cache_manager):
        self.db = db_adapter
        self.llm = llm_manager  
        self.cache = cache_manager
```

### 비동기 처리 우선
```python
# 모든 I/O 작업은 비동기
async def process_ticket_data(ticket_id: str) -> dict:
    async with get_db_session() as session:
        ticket_data = await session.fetch_ticket(ticket_id)
        similar_tickets = await search_similar_tickets(ticket_data)
        return await format_response(ticket_data, similar_tickets)
```

### 멀티테넌트 데이터 격리
```python
# tenant_id 기반 완전 격리
async def get_tenant_documents(tenant_id: str, query: str):
    filter_conditions = {
        "must": [{"match": {"tenant_id": tenant_id}}]
    }
    return await vector_db.search(query, filter=filter_conditions)
```

## 🔧 개발 지침

### 코딩 스타일
- **Python 3.10+** async/await 패턴 필수
- **타입 힌팅** 모든 함수에 적용
- **Pydantic 모델** 데이터 검증 및 직렬화
- **구조화된 로깅** 디버깅 및 모니터링

### 에러 처리 패턴
```python
try:
    result = await risky_operation()
except SpecificException as e:
    logger.error(f"특정 오류 발생", extra={"error": str(e), "context": context})
    raise HTTPException(status_code=400, detail="처리 중 오류 발생")
except Exception as e:
    logger.error(f"예상치 못한 오류", extra={"error": str(e)})
    raise HTTPException(status_code=500, detail="내부 서버 오류")
```

## 📊 성능 최적화 가이드

### DB 쿼리 최적화
- **N+1 쿼리 방지**: select_related, prefetch_related 활용
- **배치 처리**: bulk_insert_mappings 사용
- **인덱스 전략**: 복합 인덱스 고려

### 벡터 검색 최적화  
- **Qdrant 연결 풀링**: 연결 재사용
- **임베딩 배치 생성**: 여러 문서 동시 처리
- **점수 기반 필터링**: top_k 값 최적화

### 메모리 관리
- **스트리밍 처리**: 대용량 데이터 청크 단위 처리
- **캐싱 전략**: TTL 기반 지능형 캐싱
- **가비지 컬렉션**: 명시적 메모리 해제

## 🚀 현재 최적화 목표
- **/init/{ticket_id}** 응답 시간: 24초 → 5초
- **메모리 사용량** 20% 감소
- **동시 요청 처리** 성능 향상

