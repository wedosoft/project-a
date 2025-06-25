-- =====================================================
-- 🏗️ 통합 객체 중심 스키마 (Integrated Object Schema)
-- =====================================================
-- 모든 비즈니스 로직은 'integrated_objects' 테이블을 중심으로 작동
-- 기존 tickets, conversations, attachments 테이블은 제거됨
-- PostgreSQL 기준 (운영환경) / SQLite 호환 주석 포함

-- =====================================================
-- 📊 SaaS 라이선스 관리
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
    billing_status VARCHAR(20) DEFAULT 'active',    -- 'active', 'past_due', 'cancelled'
    billing_cycle VARCHAR(20) DEFAULT 'monthly',    -- 'monthly', 'yearly'
    monthly_cost DECIMAL(10,2) NOT NULL,           -- 실제 월 비용 (기본+추가)
    
    -- 시간 정보
    subscription_start_date DATE NOT NULL,          -- SQLite: TEXT
    subscription_end_date DATE,                     -- SQLite: TEXT
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    
    FOREIGN KEY (subscription_plan_id) REFERENCES subscription_plans(id)
);

-- 3. 에이전트 정보
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    company_id INTEGER NOT NULL,
    
    -- 기본 정보
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    freshdesk_agent_id INTEGER,                     -- Freshdesk 내부 ID
    
    -- 역할 정보
    role VARCHAR(100),                              -- 'admin', 'agent', 'viewer'
    department VARCHAR(100),
    
    -- 시트 관리
    seat_assigned BOOLEAN DEFAULT false,            -- 시트 할당 여부
    assigned_by INTEGER,                            -- 할당한 관리자 ID
    assigned_at TIMESTAMP,                          -- SQLite: TEXT
    
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
    resource_id VARCHAR(255),                       -- 예: ticket_id, summary_id, integrated_object_id
    metadata JSONB,                                 -- SQLite: TEXT (JSON 문자열)
    
    -- 시간 정보
    usage_date DATE NOT NULL,                       -- SQLite: TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 5. 결제 이력
CREATE TABLE billing_history (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    company_id INTEGER NOT NULL,
    
    -- 결제 정보
    billing_period_start DATE NOT NULL,             -- SQLite: TEXT
    billing_period_end DATE NOT NULL,               -- SQLite: TEXT
    
    -- 요금 계산
    base_cost DECIMAL(10,2) NOT NULL,               -- 기본 플랜 비용
    additional_seats INTEGER DEFAULT 0,             -- 추가 시트 수
    additional_seat_cost DECIMAL(10,2) DEFAULT 0,   -- 추가 시트 비용
    total_cost DECIMAL(10,2) NOT NULL,              -- 총 비용
    
    -- 결제 상태
    status VARCHAR(20) DEFAULT 'pending',           -- 'pending', 'paid', 'failed'
    paid_at TIMESTAMP,                              -- SQLite: TEXT
    
    -- 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- =====================================================
-- 🗂️ 통합 객체 저장소 (핵심 테이블)
-- =====================================================

-- 6. 통합 객체 테이블 (모든 비즈니스 로직의 중심)
CREATE TABLE integrated_objects (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    -- 식별 정보
    original_id VARCHAR(255) NOT NULL,              -- 원본 시스템의 ID (ticket_id, article_id 등)
    company_id VARCHAR(100) NOT NULL,               -- 멀티테넌트 지원
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk', -- 플랫폼 구분
    object_type VARCHAR(50) NOT NULL,               -- 'integrated_ticket', 'integrated_article'
    
    -- 핵심 데이터
    original_data JSONB NOT NULL,                   -- SQLite: TEXT (전체 원본 데이터 JSON)
    integrated_content TEXT,                        -- LLM 처리용 통합 텍스트
    summary TEXT,                                   -- AI 생성 요약
    
    -- 메타데이터 (검색 및 필터링용)
    metadata JSONB,                                 -- SQLite: TEXT (구조화된 메타데이터)
    -- 메타데이터 구조 예시:
    -- {
    --   "has_conversations": true,
    --   "has_attachments": true,
    --   "conversation_count": 5,
    --   "attachment_count": 3,
    --   "attachments": [{"id": 123, "name": "file.pdf", "content_type": "application/pdf"}],
    --   "subject": "로그인 문제",
    --   "status": "open",
    --   "priority": 2,
    --   "created_at": "2024-01-01T00:00:00Z"
    -- }
    
    -- 시간 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 인덱스 최적화를 위한 제약조건
    UNIQUE(company_id, platform, object_type, original_id)
);

-- 7. AI 처리 로그 (통합 객체 기반)
CREATE TABLE ai_processing_logs (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    
    integrated_object_id INTEGER NOT NULL,          -- integrated_objects 테이블 참조
    
    -- 처리 정보
    processing_type VARCHAR(50) NOT NULL,           -- 'summary', 'embedding', 'classification'
    model_used VARCHAR(100) NOT NULL,               -- 'gpt-4o-mini', 'text-embedding-ada-002'
    
    -- 성능 정보
    processing_time_ms INTEGER,
    token_usage JSONB,                              -- SQLite: TEXT {"input": 150, "output": 50}
    cost_estimate DECIMAL(10,4),
    
    -- 품질 정보
    quality_score DECIMAL(3,2),                     -- 0.00 ~ 1.00
    error_message TEXT,
    
    -- 시간 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    
    FOREIGN KEY (integrated_object_id) REFERENCES integrated_objects(id) ON DELETE CASCADE
);

-- =====================================================
-- 🔧 시스템 설정
-- =====================================================

-- 8. 시스템 전체 설정
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    setting_key VARCHAR(100) UNIQUE NOT NULL,       -- 'qdrant_url', 'qdrant_api_key', 'openai_api_key'
    setting_value TEXT,                             -- 암호화된 값
    is_encrypted BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. 회사별 개별 설정
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

-- 10. 수집 로그 (통합 객체 기반)
CREATE TABLE collection_logs (
    id SERIAL PRIMARY KEY,                          -- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    company_id INTEGER NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'freshdesk',
    
    -- 수집 정보
    collection_type VARCHAR(50) NOT NULL,           -- 'tickets', 'knowledge_base', 'agents'
    status VARCHAR(20) NOT NULL,                    -- 'success', 'error', 'partial'
    
    -- 통계 (통합 객체 기반)
    total_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    integrated_objects_created INTEGER DEFAULT 0,   -- 생성된 통합 객체 수
    
    -- 메시지
    message TEXT,
    error_details JSONB,                            -- SQLite: TEXT
    
    -- 시간 정보
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- SQLite: TEXT DEFAULT CURRENT_TIMESTAMP
    completed_at TIMESTAMP,                         -- SQLite: TEXT
    
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- =====================================================
-- 📊 인덱스 (성능 최적화)
-- =====================================================

-- 통합 객체 테이블 인덱스
CREATE INDEX idx_integrated_objects_company_platform ON integrated_objects(company_id, platform);
CREATE INDEX idx_integrated_objects_type ON integrated_objects(object_type);
CREATE INDEX idx_integrated_objects_created_at ON integrated_objects(created_at);

-- 메타데이터 기반 검색 인덱스 (PostgreSQL GIN 인덱스)
-- CREATE INDEX idx_integrated_objects_metadata ON integrated_objects USING GIN(metadata);

-- 전문 검색 인덱스 (PostgreSQL)
-- CREATE INDEX idx_integrated_objects_content_search ON integrated_objects USING GIN(to_tsvector('english', integrated_content));

-- 사용량 로그 인덱스
CREATE INDEX idx_usage_logs_company_date ON usage_logs(company_id, usage_date);
CREATE INDEX idx_usage_logs_agent ON usage_logs(agent_id);

-- AI 처리 로그 인덱스
CREATE INDEX idx_ai_processing_logs_object ON ai_processing_logs(integrated_object_id);
CREATE INDEX idx_ai_processing_logs_type ON ai_processing_logs(processing_type);

-- =====================================================
-- 🚀 기본 데이터 삽입
-- =====================================================

-- 기본 플랜 생성
INSERT INTO subscription_plans (plan_name, display_name, base_seats, base_monthly_cost, additional_seat_cost, max_seats, features) VALUES
('starter', 'Starter Plan', 5, 49.00, 8.00, 20, '{"ai_summary": true, "basic_analytics": true, "api_access": false}'),
('professional', 'Professional Plan', 15, 149.00, 12.00, 100, '{"ai_summary": true, "advanced_analytics": true, "api_access": true, "custom_fields": true}'),
('enterprise', 'Enterprise Plan', 50, 499.00, 15.00, NULL, '{"ai_summary": true, "advanced_analytics": true, "api_access": true, "custom_fields": true, "sso": true, "premium_support": true}');

-- 기본 시스템 설정
INSERT INTO system_settings (setting_key, setting_value, is_encrypted, description) VALUES
('qdrant_collection_name', 'saas_integrated_objects', false, 'Qdrant collection name for integrated objects'),
('default_llm_model', 'gpt-4o-mini', false, 'Default LLM model for AI features'),
('max_attachment_size_mb', '10', false, 'Maximum attachment size in MB'),
('session_timeout_hours', '24', false, 'User session timeout in hours'),
('enable_ai_processing', 'true', false, 'Enable AI processing for integrated objects');

-- =====================================================
-- 📝 사용 예시 쿼리
-- =====================================================

/*
-- 회사의 모든 통합 티켓 조회
SELECT 
    original_id,
    JSON_EXTRACT(metadata, '$.subject') as subject,
    JSON_EXTRACT(metadata, '$.status') as status,
    JSON_EXTRACT(metadata, '$.priority') as priority,
    JSON_EXTRACT(metadata, '$.conversation_count') as conversation_count,
    JSON_EXTRACT(metadata, '$.attachment_count') as attachment_count,
    created_at
FROM integrated_objects 
WHERE company_id = 'wedosoft' 
  AND object_type = 'integrated_ticket'
ORDER BY created_at DESC;

-- AI 요약이 있는 티켓 조회
SELECT 
    original_id,
    JSON_EXTRACT(metadata, '$.subject') as subject,
    summary,
    LENGTH(summary) as summary_length
FROM integrated_objects 
WHERE company_id = 'wedosoft' 
  AND object_type = 'integrated_ticket'
  AND summary IS NOT NULL
ORDER BY created_at DESC;

-- 첨부파일이 있는 티켓 조회
SELECT 
    original_id,
    JSON_EXTRACT(metadata, '$.subject') as subject,
    JSON_EXTRACT(metadata, '$.attachments') as attachments,
    JSON_EXTRACT(metadata, '$.attachment_count') as attachment_count
FROM integrated_objects 
WHERE company_id = 'wedosoft' 
  AND object_type = 'integrated_ticket'
  AND JSON_EXTRACT(metadata, '$.has_attachments') = true
ORDER BY created_at DESC;

-- 월별 처리 통계
SELECT 
    DATE_TRUNC('month', created_at) as month,
    object_type,
    COUNT(*) as object_count,
    COUNT(CASE WHEN summary IS NOT NULL THEN 1 END) as summarized_count
FROM integrated_objects 
WHERE company_id = 'wedosoft'
  AND created_at >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY month, object_type
ORDER BY month DESC;

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
*/

-- =====================================================
-- 🔄 마이그레이션 노트
-- =====================================================

/*
기존 테이블에서 통합 객체로 마이그레이션:

1. tickets → integrated_objects
   - object_type = 'integrated_ticket'
   - original_id = ticket.id
   - original_data = 전체 티켓 데이터 (conversations, attachments 포함)
   - integrated_content = 요약용 통합 텍스트
   - metadata = 검색용 메타데이터

2. articles → integrated_objects  
   - object_type = 'integrated_article'
   - original_id = article.id
   - original_data = 전체 문서 데이터 (attachments 포함)
   - integrated_content = 요약용 통합 텍스트
   - metadata = 검색용 메타데이터

3. 기존 테이블 삭제
   - DROP TABLE attachments;
   - DROP TABLE conversations;
   - DROP TABLE tickets;
   - DROP TABLE articles;
*/
