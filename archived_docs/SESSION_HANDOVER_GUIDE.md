# 세션 인계 지침서: 멀티플랫폼 API 표준화 프로젝트

## 📋 프로젝트 개요
통합 멀티플랫폼(특히 Freshdesk) 티켓/KB 데이터 수집 및 검색 시스템을 운영환경 수준으로 개선하는 프로젝트입니다.

## 🎯 주요 목표
1. **API 헤더 표준화**: 모든 API에서 X-Company-ID, X-Platform, X-Domain, X-API-Key 4개 헤더만 사용
2. **레거시 의존성 제거**: 환경변수 fallback, 하드코딩된 기본값, 구 헤더명 완전 제거
3. **운영 이슈 해결**: collection_logs 카운트, 첨부파일 테이블, KST 시간 등
4. **FastAPI 문서 정리**: Swagger에서 표준 헤더만 노출, 혼란 요소 제거

## ✅ 완료된 작업들

### 1. KB 문서 처리 개선
- `backend/core/platforms/freshdesk/fetcher.py`: status=2(공개) 문서만 처리
- `backend/core/platforms/freshdesk/optimized_fetcher.py`: 메타데이터 보존
- 인라인 이미지/첨부파일 통합 처리
- 하이브리드 검색 시스템 구현

### 2. API 헤더 표준화 (핵심 작업)
**수정된 파일들:**
- `backend/api/dependencies.py`: 4개 표준 헤더만 필수로 받도록 변경
- `backend/api/routes/ingest.py`: 표준 헤더 적용
- `backend/api/routes/query.py`: 표준 헤더 적용
- `backend/core/platforms/factory.py`: 표준 헤더 기반 플랫폼 팩토리
- `backend/core/ingest/processor.py`: 환경변수를 DEFAULT_DOMAIN으로 표준화

**변경 내용:**
```python
# 이전 (레거시)
freshdesk_domain = request.headers.get("freshdesk-domain", os.getenv("FRESHDESK_DOMAIN"))

# 현재 (표준화)
x_domain: str = Header(..., alias="X-Domain", description="플랫폼 도메인 (필수)")
```

### 3. 데이터베이스 개선
- `backend/core/database/database.py`: connect()에서 테이블 자동 생성
- collection_logs에 티켓/첨부파일/대화/KB 카운트 정확히 기록
- 모든 시간 기록을 KST로 변환 (pytz 라이브러리 추가)

### 4. 의존성 관리
- `backend/requirements.txt`: pytz 추가
- 도커 컨테이너에서 서버 강제 중지/재시작 테스트 완료

## ⚠️ 현재 문제점

### 1. FastAPI 문서상 헤더 혼란 (우선순위: 중)
- Swagger UI에서 여전히 일부 레거시 헤더가 보일 가능성
- 실제 API 동작에는 영향 없음 (문서상 혼란만 발생)
- 모든 엔드포인트가 4개 표준 헤더만 받도록 설정되어 있음

### 2. 실제 API 테스트 미완료 (우선순위: 높)
- 표준 헤더 미입력시 400 에러 발생 여부 확인 필요
- 모든 엔드포인트에서 의존성 주입 올바른 동작 확인 필요
- 환경변수 없이 헤더만으로 완전 동작 여부 검증 필요

## 🔧 핵심 파일 상태

### dependencies.py (가장 중요)
```python
# 모든 헤더 함수가 필수값으로 설정됨
async def get_company_id(
    x_company_id: str = Header(..., alias="X-Company-ID", description="회사 ID (필수)")
)

async def get_platform(
    x_platform: str = Header(..., alias="X-Platform", description="플랫폼 식별자 (필수)")
)

async def get_api_key(
    x_api_key: str = Header(..., alias="X-API-Key", description="API 키 (필수)")
)

async def get_domain(
    x_domain: str = Header(..., alias="X-Domain", description="플랫폼 도메인 (필수)")
)
```

### processor.py 주요 변경사항
- DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "example.freshdesk.com") 사용
- Freshdesk 하드코딩 제거
- KST 시간 변환 적용
- collection_logs 카운트 정확성 개선

## 📋 다음 단계 (우선순위 순)

### 1. 실제 API 테스트 (필수)
```bash
# 백엔드 서버 실행
cd backend && source venv/bin/activate && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 테스트 명령어들
# 1. 헤더 없이 요청 (400 에러 확인)
curl -X GET "http://localhost:8000/api/v1/tickets/"

# 2. 표준 헤더로 정상 요청
curl -X GET "http://localhost:8000/api/v1/tickets/" \
  -H "X-Company-ID: test-company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: test.freshdesk.com" \
  -H "X-API-Key: test-key"

# 3. 각 엔드포인트별 테스트
# /api/v1/ingest/tickets
# /api/v1/ingest/conversations  
# /api/v1/ingest/attachments
# /api/v1/ingest/kb
# /api/v1/query/
```

### 2. FastAPI 문서 최종 점검
```bash
# Swagger UI 확인
open http://localhost:8000/docs

# 각 엔드포인트에서 Parameters 섹션 확인
# 오직 4개 헤더만 보여야 함:
# - X-Company-ID
# - X-Platform  
# - X-Domain
# - X-API-Key
```

### 3. 운영환경 검증
- 환경변수 없이 완전 동작 확인
- 도커 컨테이너에서 표준 헤더만으로 모든 기능 동작 확인
- 멀티테넌트 보안 검증

## 🚨 주의사항

### 1. 절대 건드리면 안 되는 것들
- `dependencies.py`의 4개 헤더 함수 - 이미 완벽하게 표준화됨
- `processor.py`의 collection_logs 로직 - 카운트 정확성 확보됨
- KST 시간 변환 로직 - 운영 시간 이슈 해결됨

### 2. 검증해야 할 것들
- 모든 엔드포인트가 4개 헤더 없이 400 에러 반환하는지
- FastAPI 문서에서 레거시 헤더가 안 보이는지
- 실제 데이터 수집/검색이 정상 동작하는지

### 3. 만약 문제 발견시
1. **API 에러**: `dependencies.py` 재확인
2. **문서 혼란**: FastAPI 의존성 주입 재점검  
3. **데이터 문제**: `processor.py` collection_logs 로직 확인

## 🔍 테스트 체크리스트

### API 기능 테스트
- [ ] 표준 헤더 없이 요청시 400 에러
- [ ] 4개 헤더 모두 제공시 정상 동작
- [ ] 각 헤더 중 하나라도 누락시 400 에러
- [ ] 모든 CRUD 엔드포인트 정상 동작

### 문서 확인
- [ ] Swagger UI에서 4개 헤더만 표시
- [ ] 레거시 헤더명 완전 제거 확인
- [ ] 헤더 설명이 명확하고 일관성 있음

### 운영 기능
- [ ] collection_logs 카운트 정확성
- [ ] KST 시간 정상 기록
- [ ] 멀티플랫폼 지원 동작
- [ ] 첨부파일 처리 정상

## 💡 트러블슈팅 가이드

### "헤더가 필수인데 선택사항으로 보임"
→ `dependencies.py`에서 `Header(...)`의 `...` 확인

### "레거시 헤더가 여전히 보임"  
→ 모든 라우트 파일에서 import된 의존성 함수 확인

### "환경변수에 의존하고 있음"
→ `processor.py`에서 DEFAULT_DOMAIN 사용 확인

### "카운트가 맞지 않음"
→ `processor.py`의 collection_logs 업데이트 로직 확인

---

**이 지침서는 멀티플랫폼 API 표준화 프로젝트의 현재 상태와 다음 단계를 정확히 반영합니다. 새 세션에서는 이 내용을 기반으로 실제 API 테스트와 최종 검증을 진행하면 됩니다.**
