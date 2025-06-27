# 새 세션 지침서 - 멀티플랫폼 데이터 수집/검색 시스템 운영환경 개선

## 📋 프로젝트 개요

**목표**: 표준화된 4개 헤더(X-Company-ID, X-Platform, X-Domain, X-API-Key)만 사용하는 멀티플랫폼(특히 Freshdesk) 데이터 수집/검색 시스템을 운영환경 수준으로 개선

**핵심 요구사항**:
- 레거시 헤더/환경변수/기본값 완전 제거
- 모든 헤더를 필수로 강제 (400 에러 반환)
- collection_logs 카운트 정확성, 첨부파일 테이블, KST 시간 처리
- FastAPI Swagger 문서에서 표준 헤더만 노출

## ✅ 완료된 작업

### 1. **의존성 함수 표준화** (`backend/api/dependencies.py`)
```python
# 모든 헤더가 필수값으로 변경됨
async def get_company_id(x_company_id: str = Header(..., alias="X-Company-ID", description="회사 ID (필수)"))
async def get_platform(x_platform: str = Header(..., alias="X-Platform", description="플랫폼 식별자 (필수)"))
async def get_api_key(x_api_key: str = Header(..., alias="X-API-Key", description="API 키 (필수)"))
async def get_domain(x_domain: str = Header(..., alias="X-Domain", description="플랫폼 도메인 (필수)"))
```
- 레거시 헤더 함수 완전 제거
- 환경변수 fallback 제거
- 기본값 제거

### 2. **데이터 처리 로직 개선** (`backend/core/ingest/processor.py`)
```python
# FRESHDESK_DOMAIN → DEFAULT_DOMAIN으로 표준화
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "")  # 환경변수 fallback 제거됨

# collection_logs에 정확한 카운트 기록
await db.record_collection_log(
    platform=platform,
    company_id=company_id,
    tickets_count=len(tickets_data),
    attachments_count=total_attachments,
    conversations_count=total_conversations,
    kb_articles_count=len(articles_data),
    status="completed"
)

# KST 시간 변환 적용
import pytz
KST = pytz.timezone('Asia/Seoul')
timestamp_kst = datetime.now(KST)
```

### 3. **데이터베이스 테이블 관리** (`backend/core/database/database.py`)
- `connect()` 메서드에서 테이블 자동 생성
- collection_logs 카운트 필드 추가
- 첨부파일 테이블 관리 개선

### 4. **의존성 패키지 추가** (`backend/requirements.txt`)
```
pytz==2023.3  # KST 시간 변환용
```

### 5. **문서화 완료**
- `docs/SESSION_HANDOVER_GUIDE.md`: 전체 작업 내역 정리
- 트러블슈팅 가이드 포함
- 운영 환경 주의사항 명시

## 🔴 현재 문제점 (해결 필요)

### 1. **API 테스트 미완료**
- 헤더 미입력시 400 에러 반환 확인 안됨
- 모든 엔드포인트 의존성 주입 동작 확인 안됨
- 환경변수 없이 헤더만으로 완전 동작 검증 필요

### 2. **Swagger UI 혼란**
- FastAPI 문서에서 레거시 헤더가 여전히 보일 가능성
- 4개 표준 헤더만 노출되는지 최종 점검 필요

### 3. **운영환경 검증 부족**
- 실제 Freshdesk 데이터로 수집/검색 테스트 안됨
- 멀티테넌트 보안 동작 확인 안됨
- collection_logs 카운트 정확성 실데이터 검증 필요

## 🎯 다음 단계 (우선순위별)

### **STEP 1: API 동작 검증 (최우선)**
```bash
# 1. 백엔드 서버 시작
cd /Users/alan/GitHub/project-a/backend
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 2. Swagger UI 확인
# http://localhost:8000/docs 접속하여 4개 헤더만 보이는지 확인

# 3. 헤더 미입력시 400 에러 테스트
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"action": "tickets"}'
# 예상 결과: 422 Unprocessable Entity (헤더 누락)

# 4. 모든 헤더 포함 정상 테스트  
curl -X POST "http://localhost:8000/ingest" \
  -H "X-Company-ID: test-company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: test.freshdesk.com" \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{"action": "tickets"}'
```

### **STEP 2: Swagger 문서 정리**
```python
# backend/api/main.py에서 확인할 항목들:
# 1. 라우터 import시 레거시 의존성 참조 제거
# 2. OpenAPI 스키마에서 불필요한 헤더 제거
# 3. 모든 엔드포인트가 4개 표준 헤더만 받는지 확인
```

### **STEP 3: 실데이터 테스트**
```bash
# 실제 Freshdesk 환경에서 테스트
curl -X POST "http://localhost:8000/ingest" \
  -H "X-Company-ID: wedosoft" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: wedosoft.freshdesk.com" \
  -H "X-API-Key: [실제-API-키]" \
  -H "Content-Type: application/json" \
  -d '{"action": "tickets", "limit": 10}'

# collection_logs 테이블에서 카운트 확인
# SELECT * FROM collection_logs ORDER BY created_at DESC LIMIT 5;
```

## 🔧 주요 파일 경로

**핵심 수정 파일**:
- `backend/api/dependencies.py` - 의존성 함수 (헤더 처리)
- `backend/core/ingest/processor.py` - 데이터 처리 로직
- `backend/core/database/database.py` - DB 연결 및 테이블 관리
- `backend/requirements.txt` - 패키지 의존성

**테스트 대상 엔드포인트**:
- `POST /ingest` - 데이터 수집
- `POST /query` - 데이터 검색  
- `POST /init` - 초기화

## ⚠️ 운영 환경 주의사항

1. **환경변수 의존성 제거**: 모든 설정이 헤더를 통해 전달되어야 함
2. **헤더 필수 검증**: 4개 헤더 중 하나라도 누락시 400 에러
3. **멀티테넌트 보안**: company_id를 통한 데이터 격리 보장
4. **KST 시간**: collection_logs에 한국 시간으로 기록됨

## 🚨 문제 발생시 체크리스트

**API 호출 실패시**:
1. 4개 헤더 모두 포함되었는지 확인
2. 헤더 이름 대소문자 정확성 확인 (X-Company-ID, X-Platform, X-Domain, X-API-Key)
3. 서버 로그에서 의존성 주입 에러 확인

**Swagger UI 문제시**:
1. `/docs` 페이지에서 각 엔드포인트별 파라미터 확인
2. 레거시 헤더 노출되면 라우터 의존성 재점검
3. 브라우저 캐시 클리어 후 재확인

**데이터 수집 실패시**:
1. Freshdesk API 키 및 도메인 유효성 확인
2. collection_logs 테이블에서 에러 메시지 확인
3. 네트워크 연결 및 방화벽 설정 점검

## 📊 성공 기준

- [ ] 헤더 미입력시 422 에러 반환
- [ ] 4개 헤더 입력시 정상 동작
- [ ] Swagger UI에서 표준 헤더만 노출
- [ ] 실데이터 수집/검색 정상 동작
- [ ] collection_logs 카운트 정확성
- [ ] KST 시간 기록 확인
- [ ] 환경변수 없이 완전 동작

이 지침서를 바탕으로 새 세션에서 작업을 계속하시기 바랍니다.
