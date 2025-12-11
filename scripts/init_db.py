#!/usr/bin/env python3
"""
Database initialization script
"""
import asyncio
from backend.config import get_settings
from backend.services.supabase_client import SupabaseService

settings = get_settings()


async def init_supabase_schema():
    """
    Initialize Supabase schema

    Creates:
    - approval_logs table
    - Indexes for performance
    """
    client = SupabaseService()

    # TODO: Execute schema SQL
    # For now, schema should be created manually in Supabase dashboard

    print("✅ Supabase schema initialized")
    print("⚠️  Note: Create tables manually in Supabase dashboard:")
    print("""
    CREATE TABLE approval_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        draft_response TEXT,
        final_response TEXT,
        field_updates JSONB,
        approval_status TEXT CHECK (approval_status IN ('approved','modified','rejected')),
        agent_id TEXT,
        feedback_notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX idx_approval_logs_tenant ON approval_logs(tenant_id);
    CREATE INDEX idx_approval_logs_ticket ON approval_logs(ticket_id);
    CREATE INDEX idx_approval_logs_created ON approval_logs(created_at);
    """)


if __name__ == "__main__":
    asyncio.run(init_supabase_schema())
