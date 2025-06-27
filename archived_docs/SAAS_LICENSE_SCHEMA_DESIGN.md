# 🏢 SaaS 라이선스 관리 스키마 설계

## 🎯 설계 철학

### 현재 아키텍처 고려사항
- **개발환경**: SQLite (임시) → **운영환경**: PostgreSQL + Qdrant
- **최종 목표**: 2-DB 아키텍처 (PostgreSQL + Qdrant)
- **데이터 통합**: 모든 관계형 데이터는 PostgreSQL로 통합 예정

### 2-DB 아키텍처 (권장)
1. **PostgreSQL**: 모든 관계형 데이터 (티켓, 라이선스, 사용량, 설정)
2. **Qdrant**: 벡터 검색 전용

### 설정 관리 전략
- **Freshdesk 연동**: iparams (도메인/API키)
- **시스템 설정**: PostgreSQL 내 settings 테이블
- **민감한 외부 API**: 환경변수 또는 AWS Parameter Store

### Freshdesk API 제약사항 고려
- **Role은 읽기 전용**: Freshdesk API에서 role을 동적으로 변경할 수 없음
- **기능 기반 접근**: 플랜별로 기능을 제어하되, 시트는 유연하게 관리
- **실용적 SaaS 모델**: 기본 시트 + 추가 시트 구매 방식

## 핵심 테이블 구조

### 1. **subscription_plans** (플랜 정의)
```sql
-- PostgreSQL 기준 (운영환경)
CREATE TABLE subscription_plans (
    id SERIAL PRIMARY KEY,
    plan_name VARCHAR(50) UNIQUE NOT NULL,  -- 'starter', 'professional', 'enterprise'
    display_name VARCHAR(100) NOT NULL,     -- 'Starter Plan', 'Professional Plan'
    
    -- 기본 포함 사항
    base_seats INTEGER NOT NULL,     -- 기본 포함 시트 수
    base_monthly_cost DECIMAL(10,2) NOT NULL,
    additional_seat_cost DECIMAL(10,2) NOT NULL,  -- 추가 시트당 비용
    
    -- 기능 제한
    max_seats INTEGER,               -- NULL이면 무제한
    max_tickets_per_month INTEGER,   -- NULL이면 무제한
    max_api_calls_per_day INTEGER,   -- NULL이면 무제한
    
    -- 기능 플래그 (JSON)
    features JSONB NOT NULL,  -- {"ai_summary": true, "advanced_analytics": false, "custom_fields": true}
    
    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SQLite 버전 (개발환경)
CREATE TABLE subscription_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    base_seats INTEGER NOT NULL,
    base_monthly_cost DECIMAL(10,2) NOT NULL,
    additional_seat_cost DECIMAL(10,2) NOT NULL,
    max_seats INTEGER,
    max_tickets_per_month INTEGER,
    max_api_calls_per_day INTEGER,
    features TEXT NOT NULL,  -- JSON 문자열
    is_active BOOLEAN DEFAULT true,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 2. **companies** (고객사 정보)
```sql
-- PostgreSQL 기준 (운영환경)
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    
    -- 기본 정보
    company_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,  -- freshdesk 도메인 (예: mycompany.freshdesk.com)
    contact_email VARCHAR(255) NOT NULL,
    
    -- 현재 구독 정보
    subscription_plan_id INTEGER NOT NULL,
    purchased_seats INTEGER NOT NULL,    -- 구매한 총 시트 수
    used_seats INTEGER DEFAULT 0,       -- 현재 사용 중인 시트 수
    
    -- 결제 정보
    billing_status VARCHAR(20) DEFAULT 'active',  -- 'active', 'suspended', 'cancelled', 'trial'
    subscription_start DATE NOT NULL,
    subscription_end DATE,
    next_billing_date DATE,
    monthly_cost DECIMAL(10,2) NOT NULL,
    
    -- 사용량 제한
    current_month_tickets INTEGER DEFAULT 0,
    current_day_api_calls INTEGER DEFAULT 0,
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외부 연동 (Freshdesk iparams로 관리되므로 제거 검토)
    freshdesk_domain VARCHAR(255) NOT NULL,
    -- api_credentials_encrypted TEXT,  -- 제거: iparams에서 관리
    
    FOREIGN KEY (subscription_plan_id) REFERENCES subscription_plans(id)
);

-- SQLite 버전 (개발환경)  
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    domain TEXT UNIQUE NOT NULL,
    contact_email TEXT NOT NULL,
    subscription_plan_id INTEGER NOT NULL,
    purchased_seats INTEGER NOT NULL,
    used_seats INTEGER DEFAULT 0,
    billing_status TEXT DEFAULT 'active',
    subscription_start TEXT NOT NULL,
    subscription_end TEXT,
    next_billing_date TEXT,
    monthly_cost DECIMAL(10,2) NOT NULL,
    current_month_tickets INTEGER DEFAULT 0,
    current_day_api_calls INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    freshdesk_domain TEXT NOT NULL,
    FOREIGN KEY (subscription_plan_id) REFERENCES subscription_plans(id)
);
```

### 3. **agents** (상담원 정보)
```sql
CREATE TABLE agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    
    -- 상담원 기본 정보
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    freshdesk_agent_id INTEGER,  -- Freshdesk 원본 ID
    freshdesk_role TEXT,         -- Freshdesk에서 가져온 role (읽기전용)
    
    -- 라이선스 정보
    license_status TEXT DEFAULT 'inactive',  -- 'active', 'inactive', 'suspended'
    seat_assigned BOOLEAN DEFAULT false,    -- 시트 할당 여부
    assigned_by INTEGER,                    -- 시트를 할당한 관리자 ID
    assigned_at TIMESTAMP,
    
    -- 개별 기능 권한 (플랜 기본값을 오버라이드 가능)
    feature_overrides JSON,  -- {"ai_summary": false} (플랜에서 허용되어도 개별 비활성화)
    
    -- 사용 통계
    last_login_at TIMESTAMP,
    last_activity_at TIMESTAMP,
    monthly_tickets_processed INTEGER DEFAULT 0,
    monthly_ai_summaries_used INTEGER DEFAULT 0,
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (assigned_by) REFERENCES agents(id),
    UNIQUE(company_id, email),
    UNIQUE(company_id, freshdesk_agent_id)
);
```

### 4. **usage_logs** (사용량 추적)
```sql
CREATE TABLE usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    company_id INTEGER NOT NULL,
    agent_id INTEGER,
    
    -- 사용량 정보
    usage_type TEXT NOT NULL,  -- 'ticket_processed', 'ai_summary', 'api_call', 'export'
    usage_count INTEGER DEFAULT 1,
    
    -- 세부 정보
    resource_id TEXT,      -- 예: ticket_id, summary_id
    metadata JSON,         -- 추가 정보 저장
    
    -- 시간 정보
    usage_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    
    INDEX(company_id, usage_date),
    INDEX(agent_id, usage_type, usage_date)
);
```

### 5. **plan_features** (플랜별 기능 정의)
```sql
CREATE TABLE plan_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    
    feature_key TEXT NOT NULL,     -- 'ai_summary', 'advanced_analytics', 'custom_fields'
    feature_value TEXT NOT NULL,   -- 'true', 'false', '100' (제한값)
    feature_type TEXT NOT NULL,    -- 'boolean', 'integer', 'string'
    
    description TEXT,
    
    FOREIGN KEY (plan_id) REFERENCES subscription_plans(id),
    UNIQUE(plan_id, feature_key)
);
```

### 6. **billing_history** (결제 이력)
```sql
CREATE TABLE billing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    company_id INTEGER NOT NULL,
    
    -- 결제 정보
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    base_amount DECIMAL(10,2) NOT NULL,
    additional_seats_count INTEGER DEFAULT 0,
    additional_seats_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    
    -- 상태
    status TEXT DEFAULT 'pending',  -- 'pending', 'paid', 'failed', 'refunded'
    payment_method TEXT,
    transaction_id TEXT,
    
    -- 플랜 정보 (스냅샷)
    plan_name TEXT NOT NULL,
    plan_features JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

## 📊 플랜 예시 데이터

### 기본 플랜 설정
```sql
INSERT INTO subscription_plans (plan_name, display_name, base_seats, base_monthly_cost, additional_seat_cost, max_seats, features) VALUES
('starter', 'Starter Plan', 3, 29.00, 8.00, 10, '{"ai_summary": true, "basic_analytics": true, "export_limit": 50}'),
('professional', 'Professional Plan', 10, 99.00, 6.00, 50, '{"ai_summary": true, "advanced_analytics": true, "custom_fields": true, "export_limit": 500}'),
('enterprise', 'Enterprise Plan', 25, 299.00, 5.00, NULL, '{"ai_summary": true, "advanced_analytics": true, "custom_fields": true, "api_access": true, "export_limit": null}');
```

## 🔧 핵심 비즈니스 로직

### 1. 시트 관리 로직
```python
class SeatManager:
    def check_seat_availability(self, company_id: int) -> bool:
        """사용 가능한 시트가 있는지 확인"""
        company = self.get_company(company_id)
        used_seats = self.count_active_agents(company_id)
        return used_seats < company.purchased_seats
    
    def assign_seat(self, company_id: int, agent_email: str, assigned_by: int) -> bool:
        """시트 할당"""
        if not self.check_seat_availability(company_id):
            raise SeatLimitExceeded("No available seats")
        
        # 상담원 활성화 및 시트 할당
        agent = self.get_or_create_agent(company_id, agent_email)
        agent.seat_assigned = True
        agent.license_status = 'active'
        agent.assigned_by = assigned_by
        agent.assigned_at = datetime.now()
        
        # 사용 시트 수 업데이트
        self.update_used_seats(company_id)
        return True
    
    def release_seat(self, company_id: int, agent_id: int) -> bool:
        """시트 해제"""
        agent = self.get_agent(agent_id)
        agent.seat_assigned = False
        agent.license_status = 'inactive'
        
        self.update_used_seats(company_id)
        return True
```

### 2. 기능 접근 제어
```python
class FeatureManager:
    def can_use_feature(self, company_id: int, agent_id: int, feature_key: str) -> bool:
        """특정 기능 사용 가능 여부 확인"""
        company = self.get_company(company_id)
        agent = self.get_agent(agent_id)
        
        # 시트가 할당되지 않은 경우
        if not agent.seat_assigned:
            return False
        
        # 플랜별 기본 기능 확인
        plan_features = self.get_plan_features(company.subscription_plan_id)
        feature_allowed = plan_features.get(feature_key, False)
        
        # 개별 오버라이드 확인
        if agent.feature_overrides and feature_key in agent.feature_overrides:
            feature_allowed = agent.feature_overrides[feature_key]
        
        return feature_allowed
    
    def check_usage_limit(self, company_id: int, usage_type: str) -> bool:
        """사용량 제한 확인"""
        company = self.get_company(company_id)
        plan = self.get_plan(company.subscription_plan_id)
        
        if usage_type == 'monthly_tickets':
            if plan.max_tickets_per_month is None:
                return True  # 무제한
            return company.current_month_tickets < plan.max_tickets_per_month
        
        elif usage_type == 'daily_api_calls':
            if plan.max_api_calls_per_day is None:
                return True  # 무제한
            return company.current_day_api_calls < plan.max_api_calls_per_day
        
        return True
```

### 3. 결제 계산 로직
```python
class BillingCalculator:
    def calculate_monthly_cost(self, company_id: int) -> Decimal:
        """월 비용 계산"""
        company = self.get_company(company_id)
        plan = self.get_plan(company.subscription_plan_id)
        
        base_cost = plan.base_monthly_cost
        
        # 추가 시트 비용 계산
        additional_seats = max(0, company.purchased_seats - plan.base_seats)
        additional_cost = additional_seats * plan.additional_seat_cost
        
        return base_cost + additional_cost
    
    def can_add_seats(self, company_id: int, additional_seats: int) -> bool:
        """시트 추가 가능 여부 확인"""
        company = self.get_company(company_id)
        plan = self.get_plan(company.subscription_plan_id)
        
        if plan.max_seats is None:
            return True  # 무제한 플랜
        
        new_total = company.purchased_seats + additional_seats
        return new_total <= plan.max_seats
```

## 🚀 관리자 인터페이스

### 회사별 시트 관리 대시보드
```python
class CompanyDashboard:
    def get_seat_overview(self, company_id: int) -> dict:
        """시트 사용 현황"""
        company = self.get_company(company_id)
        active_agents = self.get_active_agents(company_id)
        
        return {
            'purchased_seats': company.purchased_seats,
            'used_seats': len(active_agents),
            'available_seats': company.purchased_seats - len(active_agents),
            'monthly_cost': self.calculate_monthly_cost(company_id),
            'active_agents': active_agents
        }
    
    def get_feature_usage(self, company_id: int, month: str) -> dict:
        """월별 기능 사용량"""
        return {
            'ai_summaries': self.count_usage(company_id, 'ai_summary', month),
            'tickets_processed': self.count_usage(company_id, 'ticket_processed', month),
            'api_calls': self.count_usage(company_id, 'api_call', month),
        }
```

## 🔍 주요 쿼리 예시

### 시트 사용률 조회
```sql
SELECT 
    c.company_name,
    c.purchased_seats,
    COUNT(CASE WHEN a.seat_assigned = true THEN 1 END) as used_seats,
    (c.purchased_seats - COUNT(CASE WHEN a.seat_assigned = true THEN 1 END)) as available_seats,
    ROUND(
        (COUNT(CASE WHEN a.seat_assigned = true THEN 1 END) * 100.0 / c.purchased_seats), 2
    ) as utilization_rate
FROM companies c
LEFT JOIN agents a ON c.id = a.company_id AND a.is_active = true
GROUP BY c.id, c.company_name, c.purchased_seats;
```

### 월별 기능 사용량 집계
```sql
SELECT 
    c.company_name,
    ul.usage_type,
    DATE_FORMAT(ul.usage_date, '%Y-%m') as month,
    SUM(ul.usage_count) as total_usage
FROM usage_logs ul
JOIN companies c ON ul.company_id = c.id
WHERE ul.usage_date >= DATE_SUB(CURRENT_DATE, INTERVAL 6 MONTH)
GROUP BY c.id, ul.usage_type, month
ORDER BY c.company_name, month DESC;
```

### 플랜별 수익 분석
```sql
SELECT 
    sp.plan_name,
    COUNT(c.id) as companies_count,
    SUM(c.purchased_seats) as total_seats,
    SUM(c.monthly_cost) as monthly_revenue,
    AVG(c.purchased_seats) as avg_seats_per_company
FROM subscription_plans sp
JOIN companies c ON sp.id = c.subscription_plan_id
WHERE c.billing_status = 'active'
GROUP BY sp.id, sp.plan_name
ORDER BY monthly_revenue DESC;
```

## 🎯 마이그레이션 전략

### 1단계: 테이블 생성
```sql
-- 위의 모든 테이블 생성 스크립트 실행
```

### 2단계: 기본 데이터 입력
```sql
-- 플랜 데이터 입력
-- 기존 고객사 마이그레이션 (기본 3시트 할당)
```

### 3단계: 기존 시스템 통합
- 현재 companies 테이블 데이터 마이그레이션
- Freshdesk API 연동으로 상담원 정보 동기화
- 기존 사용량 데이터 usage_logs로 마이그레이션

## 🗄️ 통합 PostgreSQL 아키텍처

### 📊 단순한 2-DB 전략 (권장)

#### 1. **PostgreSQL (All-in-One 관계형 데이터)**
- **기존 티켓 데이터**: tickets, conversations, attachments, integrated_objects
- **SaaS 라이선스**: subscription_plans, companies, agents, usage_logs
- **시스템 설정**: 벡터DB 설정, 외부 API 키 등
- **위치**: AWS RDS PostgreSQL
- **이유**: 단일 DB로 관리 복잡도 최소화, 트랜잭션 일관성

#### 2. **Qdrant (벡터 검색 전용)**
- **역할**: AI 임베딩 및 의미적 검색
- **위치**: Qdrant Cloud
- **데이터**: 티켓 임베딩, 지식베이스 벡터

### 🔐 설정 관리 통합 방안

#### PostgreSQL 내 system_settings 테이블
```sql
-- 시스템 전체 설정 관리
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,  -- 'qdrant_url', 'qdrant_api_key', 'openai_api_key'
    setting_value TEXT,  -- 암호화된 값
    is_encrypted BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 회사별 개별 설정 (필요시)
CREATE TABLE company_settings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    is_encrypted BOOLEAN DEFAULT false,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, setting_key)
);
```

#### 설정 사용 예시
```python
class SettingsManager:
    def get_qdrant_config(self) -> dict:
        """Qdrant 연결 설정 조회"""
        return {
            'url': self.get_setting('qdrant_url'),
            'api_key': self.get_setting('qdrant_api_key', encrypted=True),
            'collection_name': self.get_setting('qdrant_collection', default='tickets')
        }
    
    def get_llm_config(self) -> dict:
        """LLM 서비스 설정 조회"""
        return {
            'openai_api_key': self.get_setting('openai_api_key', encrypted=True),
            'model': self.get_setting('default_llm_model', default='gpt-4o-mini')
        }
```

### 🏗️ 최종 아키텍처 (운영환경)

```
📱 Freshdesk App (Frontend)
   ↕️ API  
🖥️ Backend (EC2)
   ├── 🗄️ PostgreSQL (RDS)
   │   ├── 티켓 데이터 (기존)
   │   ├── SaaS 라이선스
   │   └── 시스템 설정
   └── 🎯 Qdrant Cloud (벡터 검색)
```

### 🔄 마이그레이션 경로

#### 개발 → 운영 전환
```python
# 개발환경: SQLite
DATABASE_URL = "sqlite:///./data/company_freshdesk_data.db"

# 운영환경: PostgreSQL (모든 데이터 통합)
DATABASE_URL = "postgresql://user:pass@rds.amazonaws.com/saas_platform"
```

#### 데이터 이전 스크립트
```python
async def migrate_to_postgresql():
    """SQLite → PostgreSQL 통합 마이그레이션"""
    
    # 1. 기존 티켓 데이터 이전
    sqlite_companies = get_all_sqlite_companies()
    for company_id in sqlite_companies:
        tickets = get_sqlite_tickets(company_id)
        conversations = get_sqlite_conversations(company_id)
        # PostgreSQL로 이전
        
    # 2. 라이선스 데이터 초기화
    create_default_plans()
    setup_initial_companies()
    
    # 3. 시스템 설정 등록
    setup_qdrant_config()
    setup_llm_config()
```

### 💡 이점

#### ✅ **관리 복잡도 최소화**
- 단일 관계형 DB로 백업/복구 간소화
- 트랜잭션 일관성 보장
- 조인 쿼리로 복합 분석 가능

#### ✅ **설정 관리 통합**
- 모든 설정을 DB에서 관리
- 런타임 설정 변경 가능
- 회사별 개별 설정 지원

#### ✅ **확장성 유지**
- PostgreSQL 스케일링 가능
- Qdrant는 독립적으로 확장
- 필요시 샤딩/파티셔닝 적용

### 🔑 벡터DB 설정 저장 방안

#### 옵션 1: PostgreSQL system_settings (권장)
```sql
INSERT INTO system_settings (setting_key, setting_value, is_encrypted) VALUES
('qdrant_url', 'https://xyz.qdrant.tech', false),
('qdrant_api_key', 'encrypted_api_key_here', true),
('qdrant_collection_name', 'saas_tickets', false);
```

#### 옵션 2: 환경변수 (민감 정보만)
```bash
# .env.production
DATABASE_URL=postgresql://...
QDRANT_URL=https://xyz.qdrant.tech
QDRANT_API_KEY=your_encrypted_key
```

**권장**: **PostgreSQL 설정 + 환경변수 민감정보** 하이브리드 방식

## 📋 TODO 리스트

### 백엔드 구현
- [ ] SQLAlchemy 모델 정의
- [ ] SeatManager, FeatureManager, BillingCalculator 클래스 구현
- [ ] REST API 엔드포인트 추가
- [ ] Freshdesk API 동기화 스케줄러

### 프론트엔드 구현
- [ ] 시트 관리 대시보드 UI
- [ ] 사용량 분석 차트
- [ ] 결제 및 플랜 업그레이드 인터페이스

### 인프라
- [ ] 결제 시스템 연동 (Stripe/PayPal)
- [ ] 사용량 모니터링 알림
- [ ] 백업 및 복구 전략
    feature_type TEXT NOT NULL,  -- 'ai_summary', 'ticket_export', 'api_call'
    usage_count INTEGER DEFAULT 1,
    billing_month TEXT NOT NULL,  -- '2024-01'
    
    -- 비용 계산
    unit_cost DECIMAL(10,4),
    total_cost DECIMAL(10,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    INDEX(company_id, billing_month),
    INDEX(agent_id, feature_type, billing_month)
);
```

### 5. **license_audit_log** (라이선스 변경 로그)
```sql
CREATE TABLE license_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    company_id INTEGER NOT NULL,
    agent_id INTEGER,
    admin_id INTEGER NOT NULL,  -- 변경한 관리자
    
    -- 변경 내용
    action_type TEXT NOT NULL,  -- 'assign', 'revoke', 'change_role', 'suspend'
    old_status TEXT,
    new_status TEXT,
    old_license_type TEXT,
    new_license_type TEXT,
    
    -- 이유 및 메모
    reason TEXT,
    admin_notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (admin_id) REFERENCES agents(id)
);
```

## 🔧 라이선스 관리 로직

### 1. **라이선스 할당 체크**
```python
async def assign_license(company_id: int, agent_email: str, license_type: str, admin_id: int):
    company = await get_company(company_id)
    
    # 1. 라이선스 한도 체크
    if company.current_agents >= company.max_agents:
        raise LicenseExceededException("Maximum agent limit reached")
    
    # 2. 에이전트 존재 여부 확인
    agent = await get_or_create_agent(company_id, agent_email)
    
    # 3. 라이선스 할당
    agent.license_status = 'active'
    agent.license_type = license_type
    agent.assigned_by = admin_id
    agent.assigned_at = datetime.utcnow()
    
    # 4. 회사 카운터 업데이트
    company.current_agents += 1
    
    # 5. 감사 로그 기록
    await log_license_action(company_id, agent.id, admin_id, 'assign', 
                            old_status='inactive', new_status='active')
    
    await save_changes()
```

### 2. **사용량 추적**
```python
async def track_ai_summary_usage(company_id: int, agent_id: int):
    # 1. 월별 사용량 확인
    current_month = datetime.now().strftime('%Y-%m')
    usage = await get_monthly_usage(company_id, 'ai_summary', current_month)
    
    # 2. 한도 체크
    company = await get_company(company_id)
    plan = await get_license_plan(company.subscription_plan)
    
    if usage.usage_count >= plan.max_ai_summaries_per_month:
        raise UsageLimitExceededException("AI summary limit exceeded")
    
    # 3. 사용량 기록
    await record_usage(company_id, agent_id, 'ai_summary', 
                      unit_cost=0.10, billing_month=current_month)
```

## 🎯 관리자 대시보드 기능

### 라이선스 관리 화면
```
┌─────────────────────────────────────────┐
│ 🏢 Company Dashboard - Acme Corp        │
├─────────────────────────────────────────┤
│ 📊 Current Plan: Professional (20 seats)│
│ 👥 Active Agents: 15/20                 │
│ 💰 Monthly Cost: $150                   │
├─────────────────────────────────────────┤
│ Agents:                                 │
│ ✅ john@acme.com (Senior Agent)         │
│ ✅ jane@acme.com (Junior Agent)         │
│ ❌ bob@acme.com (Inactive)              │
│ [+ Add Agent] [Manage Roles]           │
├─────────────────────────────────────────┤
│ 📈 This Month Usage:                    │
│ AI Summaries: 450/1000                 │
│ API Calls: 12,500/50,000               │
└─────────────────────────────────────────┘
```

## 💡 구현 우선순위

### Phase 1: 기본 라이선스 관리
1. 회사별 에이전트 한도 관리
2. 간단한 역할 기반 권한 (Admin, Agent)
3. 기본 사용량 추적

### Phase 2: 고급 기능
1. 세분화된 역할 관리
2. 상세 사용량 분석
3. 자동 빌링 연동

### Phase 3: 엔터프라이즈 기능
1. 커스텀 역할 생성
2. 부서별 라이선스 관리
3. SSO 연동

이런 구조로 하면 어떠신가요? 특별히 궁금한 부분이나 수정하고 싶은 부분이 있으시면 말씀해 주세요! 🤔
