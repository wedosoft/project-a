-- =====================================================
-- 🏢 SaaS 라이선스 관리 통합 스키마
-- =====================================================
-- PostgreSQL 기준 (운영환경)
-- SQLite 호환 주석 포함

-- =====================================================
-- 📊 플랜 및 라이선스 관리
-- =====================================================

-- 1. 구독 플랜 정의
CREATE TABLE subscription_plans (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    plan_name VARCHAR(50) UNIQUE NOT NULL,          -- 'starter', 'professional', 'enterprise'
    display_name VARCHAR(100) NOT NULL,             -- 'Starter Plan', 'Professional Plan'
    
    -- 기본 포함 사항
    base_seats INTEGER NOT NULL,                    -- 기본 포함 시트 수
    base_monthly_cost DECIMAL(10,2) NOT NULL,       -- 기본 월 비용
    additional_seat_cost DECIMAL(10,2) NOT NULL,    -- 추가 시트당 비용
    
    -- 제한사항
    max_seats INTEGER,                              -- NULL이면 무제한
    max_tickets_per_month INTEGER,                  -- NULL이면 무제한  
    max_api_calls_per_day INTEGER,                  -- NULL이면 무제한
    
    -- 기능 플래그
    features JSONB NOT NULL,                        -- SQLite: TEXT (JSON 문자열)
    -- {"ai_summary": true, "advanced_analytics": false, "custom_fields": true}
    
    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 고객사 정보
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    -- 기본 정보
    company_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,            -- freshdesk 도메인 (mycompany.freshdesk.com)
    contact_email VARCHAR(255) NOT NULL,
    
    -- 구독 정보
    subscription_plan_id INTEGER NOT NULL,
    purchased_seats INTEGER NOT NULL,               -- 구매한 총 시트 수
    used_seats INTEGER DEFAULT 0,                   -- 현재 사용 중인 시트 수
    
    -- 결제 정보
    billing_status VARCHAR(20) DEFAULT 'active',    -- 'active', 'suspended', 'cancelled', 'trial'
    subscription_start DATE NOT NULL,               -- SQLite: TEXT
    subscription_end DATE,                          -- SQLite: TEXT
    next_billing_date DATE,                         -- SQLite: TEXT
    monthly_cost DECIMAL(10,2) NOT NULL,
    
    -- 사용량 제한 (월별/일별 카운터)
    current_month_tickets INTEGER DEFAULT 0,
    current_day_api_calls INTEGER DEFAULT 0,
    last_reset_month VARCHAR(7),                    -- '2024-01' 형식
    last_reset_day DATE,                            -- SQLite: TEXT
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 외부 연동
    freshdesk_domain VARCHAR(255) NOT NULL,
    
    FOREIGN KEY (subscription_plan_id) REFERENCES subscription_plans(id)
);

-- 3. 상담원 정보
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    company_id INTEGER NOT NULL,
    
    -- 상담원 기본 정보
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    freshdesk_agent_id INTEGER,                     -- Freshdesk 원본 ID
    freshdesk_role VARCHAR(50),                     -- Freshdesk에서 가져온 role (읽기전용)
    
    -- 라이선스 정보
    license_status VARCHAR(20) DEFAULT 'inactive',  -- 'active', 'inactive', 'suspended'
    seat_assigned BOOLEAN DEFAULT false,            -- 시트 할당 여부
    assigned_by INTEGER,                            -- 시트를 할당한 관리자 ID
    assigned_at TIMESTAMP,                          -- SQLite: TEXT
    
    -- 개별 기능 권한 (플랜 기본값 오버라이드)
    feature_overrides JSONB,                        -- SQLite: TEXT (JSON 문자열)
    -- {"ai_summary": false} (플랜에서 허용되어도 개별 비활성화 가능)
    
    -- 사용 통계
    last_login_at TIMESTAMP,                        -- SQLite: TEXT
    last_activity_at TIMESTAMP,                     -- SQLite: TEXT
    monthly_tickets_processed INTEGER DEFAULT 0,
    monthly_ai_summaries_used INTEGER DEFAULT 0,
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (assigned_by) REFERENCES agents(id),
    UNIQUE(company_id, email),
    UNIQUE(company_id, freshdesk_agent_id)
);

-- 4. 사용량 추적 로그
CREATE TABLE usage_logs (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    company_id INTEGER NOT NULL,
    agent_id INTEGER,                               -- NULL 가능 (시스템 사용량)
    
    -- 사용량 정보
    usage_type VARCHAR(50) NOT NULL,                -- 'ticket_processed', 'ai_summary', 'api_call', 'export'
    usage_count INTEGER DEFAULT 1,
    
    -- 세부 정보
    resource_id VARCHAR(255),                       -- 예: ticket_id, summary_id
    metadata JSONB,                                 -- SQLite: TEXT (JSON 문자열)
    
    -- 시간 정보
    usage_date DATE NOT NULL,                       -- SQLite: TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 5. 플랜별 기능 정의 (정규화)
CREATE TABLE plan_features (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    plan_id INTEGER NOT NULL,
    
    feature_key VARCHAR(100) NOT NULL,              -- 'ai_summary', 'advanced_analytics', 'custom_fields'
    feature_value TEXT NOT NULL,                    -- 'true', 'false', '100' (제한값)
    feature_type VARCHAR(20) NOT NULL,              -- 'boolean', 'integer', 'string'
    
    description TEXT,
    
    FOREIGN KEY (plan_id) REFERENCES subscription_plans(id),
    UNIQUE(plan_id, feature_key)
);

-- 6. 결제 이력
CREATE TABLE billing_history (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    company_id INTEGER NOT NULL,
    
    -- 결제 정보
    billing_period_start DATE NOT NULL,             -- SQLite: TEXT
    billing_period_end DATE NOT NULL,               -- SQLite: TEXT
    base_amount DECIMAL(10,2) NOT NULL,
    additional_seats_count INTEGER DEFAULT 0,
    additional_seats_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    
    -- 상태
    status VARCHAR(20) DEFAULT 'pending',           -- 'pending', 'paid', 'failed', 'refunded'
    payment_method VARCHAR(50),
    transaction_id VARCHAR(255),
    
    -- 플랜 정보 (스냅샷)
    plan_name VARCHAR(50) NOT NULL,
    plan_features JSONB,                            -- SQLite: TEXT (JSON 문자열)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- =====================================================
-- 🗄️ 기존 티켓 데이터 (통합)
-- =====================================================

-- 7. 티켓 (기존 구조 유지)
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    original_id VARCHAR(255) NOT NULL,              -- Freshdesk 원본 ID
    company_id VARCHAR(100) NOT NULL,               -- 멀티테넌트 식별자
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk',
    
    -- 티켓 정보
    subject TEXT,
    description TEXT,
    description_text TEXT,                          -- HTML 제거된 순수 텍스트
    status VARCHAR(50),
    priority VARCHAR(20),
    type VARCHAR(50),
    source VARCHAR(50),
    
    -- 담당자 정보
    requester_id INTEGER,
    responder_id INTEGER,
    group_id INTEGER,
    
    -- 시간 정보
    created_at TIMESTAMP,                           -- SQLite: TEXT
    updated_at TIMESTAMP,                           -- SQLite: TEXT
    due_by TIMESTAMP,                               -- SQLite: TEXT
    fr_due_by TIMESTAMP,                            -- SQLite: TEXT
    
    -- 상태 정보
    is_escalated BOOLEAN DEFAULT false,
    spam BOOLEAN DEFAULT false,
    
    -- 메타데이터
    tags TEXT,                                      -- JSON 문자열
    custom_fields TEXT,                             -- JSON 문자열
    raw_data TEXT,                                  -- 전체 원본 데이터 JSON
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    UNIQUE(company_id, platform, original_id)
);

-- 8. 대화 (기존 구조 유지)
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    original_id VARCHAR(255) NOT NULL,
    ticket_original_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk',
    
    -- 대화 정보
    user_id INTEGER,
    body TEXT,
    body_text TEXT,                                 -- HTML 제거된 순수 텍스트
    incoming BOOLEAN,
    private BOOLEAN,
    source VARCHAR(50),
    
    -- 시간 정보
    created_at TIMESTAMP,                           -- SQLite: TEXT
    updated_at TIMESTAMP,                           -- SQLite: TEXT
    
    -- 메타데이터
    attachments TEXT,                               -- JSON 문자열
    raw_data TEXT,                                  -- 전체 원본 데이터 JSON
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    UNIQUE(company_id, platform, original_id),
    FOREIGN KEY(company_id, platform, ticket_original_id) REFERENCES tickets(company_id, platform, original_id)
);

-- 9. 첨부파일
CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    original_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk',
    
    -- 첨부파일 정보
    name VARCHAR(500),
    content_type VARCHAR(100),
    size BIGINT,
    attachment_url TEXT,
    
    -- 연결 정보
    ticket_original_id VARCHAR(255),
    conversation_original_id VARCHAR(255),
    
    -- 메타데이터
    description TEXT,
    alt_text TEXT,
    raw_data TEXT,                                  -- 전체 원본 데이터 JSON
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    UNIQUE(company_id, platform, original_id)
);

-- 10. 통합 객체 (integrated_objects)
CREATE TABLE integrated_objects (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk',
    
    -- 통합 정보
    ticket_id VARCHAR(255) NOT NULL,
    integrated_content TEXT,                        -- 티켓 + 대화 통합 텍스트
    
    -- 첨부파일 정보 (JSON)
    all_attachments TEXT,                           -- JSON 문자열 (전체 첨부파일 리스트)
    selected_attachments TEXT,                      -- JSON 문자열 (선별된 첨부파일)
    
    -- 요약 정보
    summary TEXT,
    summary_generated_at TIMESTAMP,                 -- SQLite: TEXT
    
    -- 벡터 임베딩 정보
    embedding_id VARCHAR(255),                      -- Qdrant collection point ID
    embedding_generated_at TIMESTAMP,               -- SQLite: TEXT
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(company_id, platform, ticket_id)
);

-- =====================================================
-- 🔧 시스템 설정
-- =====================================================

-- 11. 시스템 전체 설정
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    setting_key VARCHAR(100) UNIQUE NOT NULL,       -- 'qdrant_url', 'qdrant_api_key', 'openai_api_key'
    setting_value TEXT,                             -- 암호화된 값
    is_encrypted BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. 회사별 개별 설정
CREATE TABLE company_settings (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    company_id INTEGER NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    is_encrypted BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, setting_key)
);

-- 13. 수집 로그 (기존 구조 유지)
CREATE TABLE collection_logs (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk',
    
    -- 수집 정보
    collection_type VARCHAR(50) NOT NULL,           -- 'tickets', 'conversations', 'knowledge_base'
    status VARCHAR(20) NOT NULL,                    -- 'success', 'error', 'partial'
    
    -- 통계
    total_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    
    -- 메시지
    message TEXT,
    error_details TEXT,
    
    -- 시간 정보
    started_at TIMESTAMP,                           -- SQLite: TEXT
    completed_at TIMESTAMP,                         -- SQLite: TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 📊 인덱스 생성 (성능 최적화)
-- =====================================================

-- 플랜 관련
CREATE INDEX idx_subscription_plans_active ON subscription_plans(is_active);

-- 회사 관련
CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_companies_billing_status ON companies(billing_status);
CREATE INDEX idx_companies_plan_id ON companies(subscription_plan_id);

-- 상담원 관련
CREATE INDEX idx_agents_company_id ON agents(company_id);
CREATE INDEX idx_agents_email ON agents(email);
CREATE INDEX idx_agents_seat_assigned ON agents(seat_assigned);
CREATE INDEX idx_agents_license_status ON agents(license_status);

-- 사용량 관련
CREATE INDEX idx_usage_logs_company_id ON usage_logs(company_id);
CREATE INDEX idx_usage_logs_agent_id ON usage_logs(agent_id);
CREATE INDEX idx_usage_logs_usage_date ON usage_logs(usage_date);
CREATE INDEX idx_usage_logs_usage_type ON usage_logs(usage_type);
CREATE INDEX idx_usage_logs_company_date ON usage_logs(company_id, usage_date);

-- 티켓 관련
CREATE INDEX idx_tickets_company_id ON tickets(company_id);
CREATE INDEX idx_tickets_original_id ON tickets(original_id);
CREATE INDEX idx_tickets_company_platform ON tickets(company_id, platform);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_created_at ON tickets(created_at);

-- 대화 관련
CREATE INDEX idx_conversations_company_id ON conversations(company_id);
CREATE INDEX idx_conversations_ticket_id ON conversations(ticket_original_id);
CREATE INDEX idx_conversations_company_platform ON conversations(company_id, platform);

-- 첨부파일 관련
CREATE INDEX idx_attachments_company_id ON attachments(company_id);
CREATE INDEX idx_attachments_ticket_id ON attachments(ticket_original_id);

-- 통합 객체 관련
CREATE INDEX idx_integrated_objects_company_id ON integrated_objects(company_id);
CREATE INDEX idx_integrated_objects_ticket_id ON integrated_objects(ticket_id);
CREATE INDEX idx_integrated_objects_company_platform ON integrated_objects(company_id, platform);

-- 설정 관련
CREATE INDEX idx_system_settings_key ON system_settings(setting_key);
CREATE INDEX idx_company_settings_company_id ON company_settings(company_id);

-- =====================================================
-- 📊 기본 데이터 입력
-- =====================================================

-- 기본 플랜 생성
INSERT INTO subscription_plans (plan_name, display_name, base_seats, base_monthly_cost, additional_seat_cost, max_seats, features) VALUES
('starter', 'Starter Plan', 3, 29.00, 8.00, 10, '{"ai_summary": true, "basic_analytics": true, "export_limit": 50}'),
('professional', 'Professional Plan', 10, 99.00, 6.00, 50, '{"ai_summary": true, "advanced_analytics": true, "custom_fields": true, "export_limit": 500}'),
('enterprise', 'Enterprise Plan', 25, 299.00, 5.00, NULL, '{"ai_summary": true, "advanced_analytics": true, "custom_fields": true, "api_access": true, "export_limit": null}');

-- 기본 시스템 설정
INSERT INTO system_settings (setting_key, setting_value, is_encrypted, description) VALUES
('qdrant_collection_name', 'saas_tickets', false, 'Default Qdrant collection name'),
('default_llm_model', 'gpt-4o-mini', false, 'Default LLM model for AI features'),
('max_attachment_size_mb', '10', false, 'Maximum attachment size in MB'),
('session_timeout_hours', '24', false, 'User session timeout in hours');

-- =====================================================
-- 📝 사용 예시 쿼리
-- =====================================================

/*
-- 회사별 시트 사용률 조회
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

-- 월별 기능 사용량 집계
SELECT 
    c.company_name,
    ul.usage_type,
    DATE_TRUNC('month', ul.usage_date) as month,
    SUM(ul.usage_count) as total_usage
FROM usage_logs ul
JOIN companies c ON ul.company_id = c.id
WHERE ul.usage_date >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY c.id, ul.usage_type, month
ORDER BY c.company_name, month DESC;

-- 플랜별 수익 분석
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
*/
