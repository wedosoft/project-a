# 🏢 멀티테넌트 SaaS 아키텍처 가이드

## 📋 개요

우리의 멀티테넌트 SaaS 플랫폼은 **데이터베이스 기반 설정 관리**를 통해 각 테넌트(고객사)별로 완전히 격리된 환경을 제공합니다. 환경변수는 시스템 레벨에서만 사용하고, 테넌트별 설정은 모두 데이터베이스에서 관리합니다.

## 🏗️ 아키텍처 원칙

### ❌ 기존 문제점 (환경변수 기반)
```bash
# 환경변수로 테넌트별 설정 관리 (부적절)
WEDOSOFT_FRESHDESK_DOMAIN=wedosoft.freshdesk.com
WEDOSOFT_FRESHDESK_API_KEY=fd_key_123
ACME_FRESHDESK_DOMAIN=acme.freshdesk.com
ACME_FRESHDESK_API_KEY=fd_key_456
# ... 1000개 테넌트면 2000개 환경변수 필요!
```

**문제점:**
- 확장성 부족 (테넌트 수만큼 환경변수 증가)
- 보안 위험 (모든 API 키가 환경에 노출)
- 관리 복잡성 (테넌트 추가/제거 시마다 환경변수 수정)
- 동적 설정 변경 불가

### ✅ 개선된 방식 (데이터베이스 기반)

```python
# 시스템 레벨 환경변수 (최소한)
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
TENANT_ISOLATION=schema
MAX_TENANTS=10000

# 테넌트별 설정은 데이터베이스에서 관리
config_manager.set_platform_config(company_id=1, platform="freshdesk", {
    "domain": "wedosoft.freshdesk.com",
    "api_key": "encrypted_key_123",
    "rate_limit": 200
})
```

**장점:**
- 무제한 확장성
- 동적 설정 변경
- 암호화된 민감 정보
- 테넌트별 완전 격리
- 중앙집중식 관리

## 🗄️ 데이터베이스 스키마

### 1. 시스템 설정 테이블

```sql
-- 전체 시스템 공통 설정
CREATE TABLE system_settings (
    id INTEGER PRIMARY KEY,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT,
    is_encrypted BOOLEAN DEFAULT 0,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 예시 데이터
INSERT INTO system_settings VALUES 
('qdrant_collection_name', 'saas_tickets', 0, 'Default Qdrant collection'),
('default_llm_model', 'gpt-4o-mini', 0, 'Default LLM model'),
('tenant_config_encryption_key', 'base64_encoded_key', 0, 'Master encryption key');
```

### 2. 테넌트별 설정 테이블

```sql
-- 테넌트(회사)별 개별 설정
CREATE TABLE company_settings (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    is_encrypted BOOLEAN DEFAULT 0,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, setting_key)
);

-- 예시 데이터 (암호화됨)
INSERT INTO company_settings VALUES 
(1, 1, 'platform_config_freshdesk', 'encrypted_json_config', 1, 'Freshdesk 연동 설정'),
(2, 1, 'company_name', 'WedoSoft', 0, '회사명'),
(3, 1, 'timezone', 'Asia/Seoul', 0, '타임존'),
(4, 2, 'platform_config_freshdesk', 'encrypted_json_config_2', 1, 'ACME Freshdesk 설정');
```

### 3. 회사 정보 테이블

```sql
-- 테넌트(고객사) 기본 정보
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    domain TEXT UNIQUE NOT NULL,
    contact_email TEXT NOT NULL,
    subscription_plan_id INTEGER NOT NULL,
    purchased_seats INTEGER NOT NULL,
    freshdesk_domain TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 코드 사용법

### 1. 테넌트 설정 관리

```python
from core.database.tenant_config import TenantConfigManager
from core.database.database import get_database

# 설정 관리자 생성
db = get_database("system", "master")  # 시스템 DB 사용
config_manager = TenantConfigManager(db)

# 테넌트 설정 저장
config_manager.set_tenant_setting(
    company_id=1,
    key="company_name", 
    value="WedoSoft"
)

# 플랫폼별 설정 저장 (암호화됨)
config_manager.set_platform_config(
    company_id=1,
    platform="freshdesk",
    config={
        "domain": "wedosoft.freshdesk.com",
        "api_key": "fd_api_key_secure_123",
        "rate_limit": 200,
        "collect_attachments": True
    }
)

# 설정 조회
freshdesk_config = config_manager.get_freshdesk_config(company_id=1)
print(freshdesk_config)  # 자동으로 복호화됨
```

### 2. API에서 테넌트 컨텍스트 사용

```python
from core.database.tenant_context import (
    tenant_context, 
    get_current_tenant,
    get_current_freshdesk_config
)

# 방법 1: 컨텍스트 매니저 사용
async def collect_data(company_id: int):
    with tenant_context(company_id, "freshdesk"):
        config = get_current_freshdesk_config()
        # config는 해당 테넌트의 설정
        return config

# 방법 2: 데코레이터 사용
@with_tenant_context()
async def process_request(company_id: int, platform: str):
    # 자동으로 테넌트 컨텍스트 설정됨
    tenant = get_current_tenant()
    config = tenant.get_freshdesk_config()
    return config

# 방법 3: 미들웨어로 자동 설정
# FastAPI 미들웨어가 헤더에서 테넌트 정보를 추출하여 자동 설정
# X-Company-ID: 1
# X-Platform: freshdesk
```

### 3. HTTP 요청에서 테넌트 지정

```bash
# 헤더로 테넌트 지정
curl -X GET "http://localhost:8001/api/v1/data/tickets" \
     -H "X-Company-ID: 1" \
     -H "X-Platform: freshdesk"

# 쿼리 파라미터로 지정
curl "http://localhost:8001/api/v1/data/tickets?company_id=1&platform=freshdesk"

# 서브도메인으로 지정 (설정 시)
curl "http://wedosoft.yourdomain.com/api/v1/data/tickets"
```

## 🔒 보안 및 격리

### 1. 데이터 격리

**SQLite (개발/소규모):**
- 파일 기반 분리: `{company_id}_{platform}_data.db`
- 물리적 격리 보장

**PostgreSQL (프로덕션):**
- 스키마 기반 분리: `tenant_{company_id}`
- 같은 DB 인스턴스, 다른 스키마

### 2. 설정 암호화

```python
# 민감한 설정은 자동으로 암호화
config_manager.set_platform_config(
    company_id=1,
    platform="freshdesk", 
    config={"api_key": "sensitive_data"}  # 자동 암호화됨
)

# 조회 시 자동 복호화
config = config_manager.get_platform_config(1, "freshdesk")
print(config["api_key"])  # 복호화된 값
```

### 3. 크로스 테넌트 접근 방지

```python
# 각 테넌트는 자신의 데이터만 접근 가능
with tenant_context(company_id=1):
    tickets = get_tickets()  # 테넌트 1의 티켓만 반환

with tenant_context(company_id=2):
    tickets = get_tickets()  # 테넌트 2의 티켓만 반환 (완전 분리)
```

## 🚀 확장성

### 1. 새 테넌트 추가

```python
# 새 테넌트 설정 (코드로 자동화)
setup_new_tenant(
    company_id=999,
    company_name="New Customer",
    platform="freshdesk",
    platform_config={
        "domain": "newcustomer.freshdesk.com",
        "api_key": "new_api_key"
    }
)
# 환경변수 수정 없이 즉시 사용 가능!
```

### 2. 새 플랫폼 지원

```python
config_manager.set_platform_config(
    company_id=1,
    config={
        "api_key": "zd_api_key_123"
    }
)
```

### 3. 동적 설정 변경

```python
# 런타임에 설정 변경 (재시작 불필요)
config_manager.set_tenant_setting(
    company_id=1,
    key="rate_limit",
    value=500  # 200 -> 500으로 증가
)
# 즉시 적용됨
```

## 🛠️ 개발 도구

### 1. 설정 관리 CLI

```bash
# 테넌트 설정 확인
python -m core.database.tenant_config list --company-id=1

# 설정 변경
python -m core.database.tenant_config set --company-id=1 --key="rate_limit" --value=300

# 새 테넌트 생성
python -m core.database.tenant_config create --company-name="Test Corp" --platform="freshdesk"
```

### 2. 데모 스크립트

```bash
# 멀티테넌트 설정 데모 실행
python demo_tenant_config.py

# API 서버 실행 (테넌트 지원)
python example_multitenant_api.py
```

## 📊 모니터링

### 1. 테넌트별 사용량 추적

```python
# 사용량 로그 기록
config_manager.log_usage({
    'company_id': 1,
    'usage_type': 'api_call',
    'usage_count': 1,
    'resource_id': 'collect_tickets'
})

# 사용량 조회
usage = config_manager.get_usage_summary(company_id=1, days=30)
```

### 2. 설정 변경 감사

```sql
-- 설정 변경 이력 추적
SELECT company_id, setting_key, updated_at 
FROM company_settings 
WHERE updated_at > date('now', '-7 days')
ORDER BY updated_at DESC;
```

## 🎯 마이그레이션 가이드

### 기존 환경변수 → 데이터베이스 설정

```python
# 1. 기존 환경변수 읽기
import os
wedosoft_domain = os.getenv('WEDOSOFT_FRESHDESK_DOMAIN')
wedosoft_api_key = os.getenv('WEDOSOFT_FRESHDESK_API_KEY')

# 2. 데이터베이스로 이전
config_manager.set_platform_config(
    company_id=1,  # WedoSoft
    platform="freshdesk",
    config={
        "domain": wedosoft_domain,
        "api_key": wedosoft_api_key
    }
)

# 3. 환경변수 제거
# .env 파일에서 테넌트별 환경변수 삭제
```

이 아키텍처를 통해 **무제한 확장 가능한 멀티테넌트 SaaS 플랫폼**을 구축할 수 있습니다! 🚀
