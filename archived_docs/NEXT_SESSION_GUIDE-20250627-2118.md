# 다음 세션 가이드 📋

## 🎯 **현재 상황 요약**

### ✅ **완료된 작업들**

1. **ORM 환경 설정 완료**

   - `.env` 파일에 `USE_ORM=true` 설정
   - ORM 기반 데이터베이스 관리자 및 모델 정리
   - 통합 객체 (IntegratedObject) 모델 및 관계 설정

2. **ORM 기반 데이터 흐름 검증**

   - `test_summary_generation.py`: ORM을 통한 요약 생성 성공 확인
   - `diagnose_database.py`: ORM DB 상태 및 데이터 존재 확인
   - `trace_data_collection.py`: ORM 데이터 흐름 전체 추적 완료

3. **레거시 SQLite 코드 정리**
   - `core/ingest/processor.py`: 요약 생성 로직이 ORM 기반으로 전환
   - `core/migration_layer.py`: ORM 우선 사용하도록 리팩토링
   - LLMManager (not LLMRouter) 추상화로 요약 생성 통일

### ❌ **미완료 - 핵심 문제**

**API 서버의 ingest/summary 생성 엔드포인트가 아직 ORM 경로를 사용하지 않음**

- 테스트 스크립트들에서는 ORM으로 요약 생성이 성공
- 그러나 API 경로(`/ingest/sync-summaries`)에서는 "0 items processed" 결과
- `backend/api/routes/ingest_core.py`의 `sync_summaries_to_vector_db` 엔드포인트가 ORM 기반 로직을 사용하지 않음

## 🚀 **다음 세션 작업 계획**

### 1️⃣ **우선순위 1: API 엔드포인트 ORM 전환**

**📁 대상 파일:**

- `/Users/alan/GitHub/project-a/backend/api/routes/ingest_core.py` (약 1009줄)

**🔧 수정 내용:**

```python
# 현재 (라인 280-330 근처):
@router.post("/sync-summaries", response_model=IngestResponse)
async def sync_summaries_to_vector_db(...):
    # 기존 SQLite/레거시 로직 사용
    from core.ingest.processor import sync_summaries_to_vector_db as sync_func
```

**➡️ 수정 후:**

```python
@router.post("/sync-summaries", response_model=IngestResponse)
async def sync_summaries_to_vector_db(...):
    # ORM 기반 로직으로 전환
    from core.ingest.processor import generate_and_store_summaries
    # ORM 세션 및 repository 사용
```

### 2️⃣ **우선순위 2: 전체 ingest 파이프라인 ORM 통합**

**📁 대상 파일:**

- `/Users/alan/GitHub/project-a/backend/core/ingest/processor.py`

**🔧 수정 내용:**

- `ingest()` 함수가 `generate_and_store_summaries` 호출하도록 확인
- API 경로와 테스트 스크립트가 동일한 ORM 코드 경로 사용하도록 통일

### 3️⃣ **우선순위 3: 엔드투엔드 검증**

**🧪 테스트 방법:**

```bash
# 1. API 서버 시작
cd backend && source venv/bin/activate && python -m uvicorn api.main:app --reload

# 2. API 엔드포인트 호출
curl -X POST "http://localhost:8000/ingest/sync-summaries" \
     -H "X-Tenant-ID: test_company" \
     -H "X-Platform: freshdesk" \
     -H "Content-Type: application/json"

# 3. 결과 확인 - "0 items processed"가 아닌 실제 처리 결과 확인
```

## 📖 **핵심 참고 자료**

### 🔍 **현재 작동하는 ORM 코드 (참고용)**

- `/Users/alan/GitHub/project-a/backend/test_summary_generation.py` (31줄)
- `/Users/alan/GitHub/project-a/backend/core/ingest/processor.py` (generate_and_store_summaries 함수)

### 🗃️ **ORM 설정 파일들**

- `/Users/alan/GitHub/project-a/backend/.env` (USE_ORM=true)
- `/Users/alan/GitHub/project-a/backend/core/database/manager.py` (ORM 테이블 생성)
- `/Users/alan/GitHub/project-a/backend/core/database/models.py` (IntegratedObject 모델)

### 📊 **진단 및 추적 스크립트들**

- `/Users/alan/GitHub/project-a/backend/diagnose_database.py`
- `/Users/alan/GitHub/project-a/backend/trace_data_collection.py`

## ⚠️ **주의사항**

### 🔄 **제안 > 컨펌 > 진행 워크플로우 유지**

1. 코드 변경 제안 시 구체적인 수정사항 명시
2. 사용자 확인 후 실행
3. 변경 후 테스트 및 검증

### 🛡️ **안전 장치**

- 기존 테스트 스크립트들이 계속 작동하는지 확인
- ORM과 SQLite 동시 지원하는 코드는 ORM 우선으로 설정 유지
- 환경변수 `USE_ORM=true` 확인

## 📝 **예상 결과**

### ✅ **성공 시**

- API 엔드포인트 호출 시 실제 요약 생성 및 저장 확인
- "0 items processed" 대신 "X items processed successfully" 메시지
- ORM DB에 요약 데이터 저장 확인
- 테스트 스크립트와 API 경로 모두 동일한 ORM 경로 사용

### 📈 **최종 목표**

- 레거시 SQLite 코드 완전 제거 (ORM만 사용)
- 모든 데이터 처리 파이프라인이 ORM 기반으로 통일
- API와 배치 작업 모두 동일한 ORM 추상화 사용

---

## 🎯 **즉시 실행 가능한 첫 번째 작업**

```bash
# API 서버 상태 확인 및 현재 문제 재현
cd /Users/alan/GitHub/project-a/backend
source venv/bin/activate
python -m uvicorn api.main:app --reload &

# 문제 재현 (백그라운드에서 실행)
sleep 3
curl -X POST "http://localhost:8000/ingest/sync-summaries" \
     -H "X-Tenant-ID: test_company" \
     -H "X-Platform: freshdesk" \
     -H "Content-Type: application/json" \
     -v
```

**예상 결과:** "0 items processed" 메시지 확인 → ORM 경로로 수정 필요 확인
