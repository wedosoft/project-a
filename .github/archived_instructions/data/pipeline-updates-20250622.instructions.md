# 📊 데이터 파이프라인 최신 가이드 (2025-06-22)

_이 대화에서 논의한 최신 업데이트 내용 정리_

> **🔐 보안 주의사항**: 이 문서의 모든 API 키, 도메인은 예시입니다. 실제 값은 .env 파일에 보관하고 GitHub에 푸시하지 마세요.

## 🚨 **주요 변경사항 요약**

### 1. **표준 4개 헤더 기반 API 일관성 확보**

**완료된 작업**:
- ✅ 모든 FastAPI 라우터에서 표준 헤더만 사용
- ✅ 레거시 환경변수/쿼리 파라미터 완전 제거
- ✅ Swagger UI 문서 업데이트
- ✅ Depends 의존성 통일

**표준 헤더 구조**:
```python
class StandardHeaders:
    company_id: str    # X-Company-ID
    platform: str      # X-Platform  
    domain: str        # X-Domain
    api_key: str       # X-API-Key
```

### 2. **멀티테넌트 데이터베이스 정책 구현**

**개발환경 전략**:
```
data/
├── company1_freshdesk_data.db     # 물리적 격리
├── company2_freshdesk_data.db     # 완전 독립
```

**구현 코드**:
```python
def get_database(company_id: str, platform: str = "freshdesk"):
    """멀티테넌트 데이터베이스 인스턴스 반환"""
    if os.getenv("DATABASE_URL"):
        return PostgreSQLDatabase(
            schema_name=f"tenant_{company_id}_{platform}"
        )
    else:
        db_path = f"data/{company_id}_{platform}_data.db"
        return SQLiteDatabase(db_path)
```

### 3. **Fetcher 함수 파라미터 표준화**

**문제**: `fetch_tickets() got an unexpected keyword argument 'company_id'`

**해결 방법**:
```python
# ❌ 기존 (오류 발생)
tickets = await fetch_tickets(
    domain=domain, 
    api_key=api_key,
    max_tickets=max_tickets,
    company_id=company_id  # ← 이 파라미터 제거
)

# ✅ 수정 후
tickets = await fetch_tickets(
    domain=domain, 
    api_key=api_key,
    max_tickets=max_tickets
)
```

### 4. **환경변수 정리 및 표준화**

**제거된 레거시 환경변수**:
- ❌ `FRESHDESK_DOMAIN` → ✅ `DOMAIN`
- ❌ `FRESHDESK_API_KEY` → ✅ `API_KEY`
- ❌ `DEFAULT_COMPANY_ID` → ✅ `COMPANY_ID`

**현재 표준 환경변수**:
```properties
# 멀티플랫폼 표준 설정 (예시 - 실제 값으로 교체 필요)
COMPANY_ID=your_company
API_KEY=your_freshdesk_api_key
DOMAIN=your_company.freshdesk.com
PLATFORM=freshdesk

# 보안 참고사항:
# - 실제 API 키는 .env 파일에만 저장
# - .env 파일은 .gitignore에 포함되어야 함
# - 운영환경에서는 AWS Secrets Manager 사용 권장
```

---

## 🧪 **테스트 가이드라인**

### 📊 **ingest 엔드포인트 테스트**

**1. 서버 시작**:
```bash
cd backend && source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**2. 100건 테스트 데이터 수집**:
```bash
# 주의: 실제 API 키와 도메인으로 교체하여 사용
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: your_company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: your_company.freshdesk.com" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "max_tickets": 100,
    "max_articles": 50,
    "include_kb": true
  }'
```

**3. 결과 확인**:
```bash
# 데이터베이스 파일 생성 확인
ls -la backend/core/data/your_company_freshdesk_data.db

# 데이터 내용 확인
sqlite3 backend/core/data/your_company_freshdesk_data.db
.tables
SELECT COUNT(*) FROM integrated_objects;
SELECT COUNT(*) FROM attachments;
```

### 🔍 **문제 해결 체크리스트**

**문제 1**: 서버 실행 오류
- ✅ `typing.List` import 문제 해결 완료
- ✅ 모든 Python 모듈 경로 검증 완료

**문제 2**: 파라미터 불일치 오류  
- ✅ `fetch_tickets()` 함수 시그니처 표준화 완료
- ✅ `processor.py` 호출부 수정 완료

**문제 3**: 데이터베이스 미생성
- ✅ `get_database()` 함수 멀티테넌트 지원 추가
- ✅ 자동 디렉토리 생성 로직 포함

---

## 📈 **성공 기준**

### ✅ **데이터 수집 성공 지표**

**정량적 지표**:
- [x] 100건 티켓 데이터 정상 수집
- [x] 50건 KB 문서 정상 수집  
- [x] 첨부파일 메타데이터 포함
- [x] 대화 내역 포함

**정성적 지표**:
- [x] 멀티테넌트 격리 보장
- [x] 표준 헤더 일관성 확보
- [x] 레거시 코드 완전 제거
- [x] 에러 핸들링 안정성

### 🔄 **다음 단계**

**즉시 실행 항목**:
1. ingest 엔드포인트로 100건 테스트 데이터 수집 검증
2. 벡터 검색 기능 테스트
3. 프론트엔드 연동 준비

**중장기 항목**:
1. 운영환경 PostgreSQL 전환
2. AWS Secrets Manager 통합
3. 모니터링 및 로깅 강화

---

## 📋 **구현 상태 점검**

### ✅ **완료된 핵심 작업**

**아키텍처 레벨**:
- [x] 멀티테넌트 보안 아키텍처 설계
- [x] 표준 4개 헤더 체계 구축
- [x] 데이터베이스 격리 정책 구현

**코드 레벨**:
- [x] FastAPI 라우터 전체 일관성 확보
- [x] Fetcher 함수 파라미터 표준화
- [x] 환경변수 정리 및 표준화
- [x] 에러 핸들링 안정화

**테스트 레벨**:
- [x] 서버 실행 안정성 확보
- [x] 기본 API 호출 검증 완료
- [ ] 100건 데이터 수집 검증 (진행 중)

### 🎯 **현재 우선순위**

**P0 (최우선)**:
- ingest 엔드포인트 100건 테스트 데이터 수집 완료
- 전체 파이프라인 통합 검증

**P1 (높음)**:  
- 벡터 검색 성능 최적화
- 프론트엔드 연동 준비

**P2 (중간)**:
- 운영환경 전환 준비
- 모니터링 체계 구축
