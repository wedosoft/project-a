# 멀티테넌트 SaaS 플랫폼 데이터 격리 가이드

## 📋 개요

우리 SaaS 플랫폼은 **완전한 데이터 격리**를 통해 고객별/플랫폼별 데이터를 안전하게 분리 관리합니다.

## 🏗️ 아키텍처

### 1. SQLite 방식 (개발/소규모)
```
고객별 독립 데이터베이스 파일
├── acme_corp_freshdesk_data.db
├── beta_company_freshdesk_data.db  
└── ...
```

**장점:**
- ✅ 완전한 물리적 격리
- ✅ 빠른 개발/테스트
- ✅ 백업/복원 용이

**단점:**
- ❌ 대용량 데이터 처리 제한
- ❌ 동시 접속 제한

### 2. PostgreSQL 스키마 방식 (프로덕션)
```
단일 PostgreSQL 데이터베이스
├── public (메타데이터)
│   ├── tenants
│   ├── platforms
│   └── tenant_platforms
├── tenant_acme_corp (고객 데이터)
│   ├── integrated_objects
│   └── progress_logs
├── tenant_beta_company (고객 데이터)
│   ├── integrated_objects
│   └── progress_logs
└── ...
```

**장점:**
- ✅ 확장성 뛰어남
- ✅ 고성능 쿼리
- ✅ 중앙 집중 관리
- ✅ 전문 검색 지원

**단점:**
- ❌ 복잡한 설정
- ❌ PostgreSQL 의존성

## 🔧 설정 방법

### 1. 환경변수 설정

```bash
# .env 파일 생성
cp .env.multitenant.example .env

# 필수 설정
DATABASE_TYPE=postgresql  # 또는 sqlite
POSTGRES_HOST=localhost
POSTGRES_DB=saas_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
```

### 2. PostgreSQL 데이터베이스 준비

```sql
-- PostgreSQL에서 실행
CREATE DATABASE saas_platform;
CREATE USER saas_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE saas_platform TO saas_user;
```

### 3. Python 의존성 설치

```bash
# PostgreSQL 드라이버 (PostgreSQL 사용시)
pip install psycopg2-binary

# 또는 컴파일 버전
pip install psycopg2
```

## 💻 사용 방법

### 1. 기본 사용법

```python
from core.database.database import get_tenant_database

# 테넌트별 데이터베이스 연결
db = get_tenant_database('acme_corp', 'freshdesk')

# 데이터 삽입
ticket_data = {
    'original_id': 'TICKET-001',
    'object_type': 'ticket',
    'original_data': {...},
    'integrated_content': 'Ticket content',
    'summary': 'Ticket summary',
    'metadata': {...}
}
db.insert_integrated_object(ticket_data)

# 데이터 조회
tickets = db.get_integrated_objects_by_type('acme_corp', 'freshdesk', 'ticket')
```

### 2. 환경별 자동 선택

```python
# 환경변수에 따라 자동으로 SQLite 또는 PostgreSQL 선택
from core.database.database import DatabaseFactory

db = DatabaseFactory.create_database('acme_corp', 'freshdesk')
```

### 3. 테넌트 관리

```python
from core.database.database import TenantDataManager

# 테넌트 통계
stats = TenantDataManager.get_tenant_statistics('acme_corp', 'freshdesk')

# 테넌트 데이터 마이그레이션
TenantDataManager.migrate_tenant_data('old_tenant', 'new_tenant', 'freshdesk')
```

## 🧪 격리 검증

### 테스트 실행

```bash
# 격리 테스트 실행
python backend/test_multitenant_isolation.py
```

### 예상 결과

```
🧪 멀티테넌트 데이터 격리 테스트 시작
==================================================

1️⃣ 테넌트별 데이터 삽입 테스트
   ✅ acme_corp (freshdesk): 티켓 삽입 성공 (ID: 1)
   ✅ beta_company (freshdesk): 티켓 삽입 성공 (ID: 1)

2️⃣ 데이터 격리 검증
   acme_corp (freshdesk): 1개 객체, ✅ 격리됨
   beta_company (freshdesk): 1개 객체, ✅ 격리됨

3️⃣ 크로스 테넌트 액세스 방지 테스트
   ✅ 크로스 테넌트 데이터 액세스 차단됨

4️⃣ 테넌트 설정 검증
   acme_corp: schema 방식, 격리: True
   beta_company: schema 방식, 격리: True
   gamma_ltd: schema 방식, 격리: True
```

## 🔒 보안 고려사항

### 1. 테넌트 ID 검증
```python
# 안전한 테넌트 ID만 허용
VALID_TENANT_PATTERN = r'^[a-z0-9_]+$'
```

### 2. SQL 인젝션 방지
```python
# 모든 쿼리에서 파라미터화된 쿼리 사용
cursor.execute("SELECT * FROM table WHERE tenant_id = %s", (tenant_id,))
```

### 3. 스키마 권한 관리 (PostgreSQL)
```sql
-- 테넌트별 사용자 권한 제한
GRANT USAGE ON SCHEMA tenant_acme_corp TO acme_user;
REVOKE ALL ON SCHEMA tenant_beta_company FROM acme_user;
```

## 📊 모니터링

### 1. 격리 상태 모니터링
```python
from core.database.database import validate_multitenant_setup

# 정기적으로 실행
validation = validate_multitenant_setup()
if not validation['is_production_ready']:
    alert_admin(validation['recommendations'])
```

### 2. 테넌트 리소스 사용량
```python
# 테넌트별 사용량 추적
stats = TenantDataManager.get_tenant_statistics('acme_corp')
if stats['storage_info']['file_size_mb'] > 1000:  # 1GB 초과
    notify_tenant_limit_exceeded('acme_corp')
```

## 🚀 마이그레이션 가이드

### SQLite → PostgreSQL 마이그레이션

```python
# 1. PostgreSQL 환경 설정
export DATABASE_TYPE=postgresql

# 2. 기존 SQLite 데이터 내보내기
python scripts/export_sqlite_data.py --tenant=acme_corp

# 3. PostgreSQL로 데이터 가져오기
python scripts/import_to_postgresql.py --tenant=acme_corp --data=export.json

# 4. 격리 검증
python test_multitenant_isolation.py
```

## 📈 성능 최적화

### 1. 인덱스 최적화
```sql
-- PostgreSQL의 경우 JSON 인덱스 활용
CREATE INDEX idx_metadata_gin ON integrated_objects USING GIN (metadata);
```

### 2. 연결 풀링
```python
# 환경변수로 연결 풀 크기 조정
CONNECTION_POOL_SIZE=20
```

### 3. 쿼리 최적화
```python
# 테넌트별 쿼리 최적화
db.get_integrated_objects_by_type(
    company_id, platform, object_type,
    limit=100,  # 페이징 사용
    offset=0
)
```

## ❗ 주의사항

1. **테넌트 ID 일관성**: 모든 API에서 동일한 company_id 사용
2. **플랫폼 분리**: 같은 테넌트라도 플랫폼별로 데이터 분리
3. **백업 전략**: 테넌트별 독립적인 백업 계획 수립
4. **성능 모니터링**: 테넌트별 리소스 사용량 추적
5. **스키마 변경**: 모든 테넌트 스키마에 일관되게 적용

---

## 🆘 문제 해결

### 일반적인 문제

1. **PostgreSQL 연결 실패**
   ```bash
   # PostgreSQL 서비스 상태 확인
   systemctl status postgresql
   ```

2. **테넌트 스키마 누락**
   ```python
   # 스키마 재생성
   db = get_tenant_database('company_id', force_creation=True)
   ```

3. **크로스 테넌트 데이터 접근**
   ```python
   # 격리 검증 실행
   python test_multitenant_isolation.py
   ```

### 로그 확인
```bash
# 테넌트 관련 로그 확인
tail -f logs/multitenant.log | grep "company_id"
```
