#!/usr/bin/env python3
"""
Initialize Supabase database schema with direct PostgreSQL connection
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Get PostgreSQL connection using .env variables"""
    host = os.getenv("SUPABASE_DB_HOST")
    port = int(os.getenv("SUPABASE_DB_PORT", "6543"))
    database = os.getenv("SUPABASE_DB_NAME", "postgres")
    user = os.getenv("SUPABASE_DB_USER")
    password = os.getenv("SUPABASE_DB_PASSWORD")

    print(f"🔗 Connecting to: {host}:{port}")
    print(f"   Database: {database}")
    print(f"   User: {user}")

    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )

def create_schema():
    """Create database schema"""

    # DDL for all tables
    ddl_sql = """
    -- Issue Blocks Table (티켓 지식 = 경험)
    CREATE TABLE IF NOT EXISTS issue_blocks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        block_type TEXT CHECK (block_type IN ('symptom', 'cause', 'resolution')),
        product TEXT,
        component TEXT,
        error_code TEXT,
        content TEXT NOT NULL,
        meta JSONB,
        embedding_id TEXT UNIQUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- KB Blocks Table (정책/절차 = 규범)
    CREATE TABLE IF NOT EXISTS kb_blocks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        article_id TEXT,
        intent TEXT,
        step TEXT,
        constraint_text TEXT,
        example TEXT,
        meta JSONB,
        embedding_id TEXT UNIQUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Approval Logs Table (승인 이력)
    CREATE TABLE IF NOT EXISTS approval_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        draft_response TEXT,
        final_response TEXT,
        field_updates JSONB,
        approval_status TEXT CHECK (approval_status IN ('approved', 'modified', 'rejected')),
        agent_id TEXT,
        feedback_notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_issue_blocks_tenant_id ON issue_blocks(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_issue_blocks_ticket_id ON issue_blocks(ticket_id);
    CREATE INDEX IF NOT EXISTS idx_issue_blocks_block_type ON issue_blocks(block_type);
    CREATE INDEX IF NOT EXISTS idx_issue_blocks_product ON issue_blocks(product);
    CREATE INDEX IF NOT EXISTS idx_issue_blocks_component ON issue_blocks(component);
    CREATE INDEX IF NOT EXISTS idx_issue_blocks_error_code ON issue_blocks(error_code);

    CREATE INDEX IF NOT EXISTS idx_kb_blocks_tenant_id ON kb_blocks(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_kb_blocks_article_id ON kb_blocks(article_id);

    CREATE INDEX IF NOT EXISTS idx_approval_logs_tenant_id ON approval_logs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_approval_logs_ticket_id ON approval_logs(ticket_id);
    CREATE INDEX IF NOT EXISTS idx_approval_logs_status ON approval_logs(approval_status);
    CREATE INDEX IF NOT EXISTS idx_approval_logs_created_at ON approval_logs(created_at DESC);
    """

    # RLS policies
    rls_sql = """
    -- Enable RLS on all tables
    ALTER TABLE issue_blocks ENABLE ROW LEVEL SECURITY;
    ALTER TABLE kb_blocks ENABLE ROW LEVEL SECURITY;
    ALTER TABLE approval_logs ENABLE ROW LEVEL SECURITY;

    -- RLS policies for issue_blocks
    DROP POLICY IF EXISTS "Tenant isolation for issue_blocks" ON issue_blocks;
    CREATE POLICY "Tenant isolation for issue_blocks" ON issue_blocks
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE));

    -- RLS policies for kb_blocks
    DROP POLICY IF EXISTS "Tenant isolation for kb_blocks" ON kb_blocks;
    CREATE POLICY "Tenant isolation for kb_blocks" ON kb_blocks
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE));

    -- RLS policies for approval_logs
    DROP POLICY IF EXISTS "Tenant isolation for approval_logs" ON approval_logs;
    CREATE POLICY "Tenant isolation for approval_logs" ON approval_logs
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE));
    """

    # Sample data
    sample_sql = """
    -- Sample tenant: demo-tenant
    SET app.current_tenant_id = 'demo-tenant';

    -- Sample issue_blocks
    INSERT INTO issue_blocks (tenant_id, ticket_id, block_type, product, component, content)
    VALUES
        ('demo-tenant', 'TICKET-001', 'symptom', 'Product A', 'Login', '사용자가 로그인 시 "Invalid credentials" 에러 발생'),
        ('demo-tenant', 'TICKET-001', 'cause', 'Product A', 'Login', 'JWT 토큰 만료 시간이 너무 짧게 설정됨 (5분)'),
        ('demo-tenant', 'TICKET-001', 'resolution', 'Product A', 'Login', 'JWT 만료 시간을 30분으로 연장하고 refresh token 구현')
    ON CONFLICT DO NOTHING;

    -- Sample kb_blocks
    INSERT INTO kb_blocks (tenant_id, article_id, intent, step, constraint_text)
    VALUES
        ('demo-tenant', 'KB-AUTH-001', '로그인 문제 해결', '1. JWT 설정 확인 2. 토큰 만료 시간 검증 3. Refresh token 구현 확인', 'JWT 만료 시간은 최소 15분 이상'),
        ('demo-tenant', 'KB-AUTH-002', '비밀번호 재설정', '1. 이메일 인증 2. 임시 비밀번호 발급 3. 강제 변경 유도', '비밀번호는 8자 이상, 특수문자 포함')
    ON CONFLICT DO NOTHING;

    -- Sample approval_logs
    INSERT INTO approval_logs (tenant_id, ticket_id, draft_response, approval_status, agent_id)
    VALUES
        ('demo-tenant', 'TICKET-001', 'JWT 토큰 만료 시간을 확인하고 연장하는 것을 권장합니다.', 'approved', 'agent-001'),
        ('demo-tenant', 'TICKET-002', '비밀번호 재설정 절차를 안내해드립니다.', 'modified', 'agent-002')
    ON CONFLICT DO NOTHING;
    """

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        print("🔧 Creating database schema...")
        cur.execute(ddl_sql)
        conn.commit()
        print("✅ DDL executed successfully")

        print("🛡️ Applying RLS policies...")
        cur.execute(rls_sql)
        conn.commit()
        print("✅ RLS policies applied")

        print("📝 Inserting sample data...")
        cur.execute(sample_sql)
        conn.commit()
        print("✅ Sample data inserted")

        # Verify tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('issue_blocks', 'kb_blocks', 'approval_logs')
            ORDER BY table_name
        """)
        tables = cur.fetchall()

        print("\n📊 Created tables:")
        for table in tables:
            print(f"  - {table[0]}")

        # Count records
        for table_name in ['issue_blocks', 'kb_blocks', 'approval_logs']:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"  {table_name}: {count} records")

        cur.close()
        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import sys
    success = create_schema()
    sys.exit(0 if success else 1)
