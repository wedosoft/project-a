#!/usr/bin/env python3
"""
Clean Schema Creator for Freshdesk Multi-tenant SaaS
Creates a simplified, flexible schema with optimized attachment handling.
"""

import sqlite3
import os
from datetime import datetime


def create_clean_schema(db_path):
    """Create a clean, optimized schema for Freshdesk data."""
    
    # Remove existing database if it exists
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(db_path, backup_path)
        print(f"✅ Backed up existing database to: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    print("🚀 Creating clean schema tables...")
    
    # 1. Companies table (multi-tenant support)
    cursor.execute("""
    CREATE TABLE companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER UNIQUE NOT NULL,  -- Original Freshdesk company ID
        name TEXT NOT NULL,
        domain TEXT,
        description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        UNIQUE(original_id)
    );
    """)
    
    # 2. Agents table
    cursor.execute("""
    CREATE TABLE agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER UNIQUE NOT NULL,  -- Original Freshdesk agent ID
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(original_id)
    );
    """)
    
    # 3. Categories table (for ticket categorization)
    cursor.execute("""
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        parent_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES categories (id)
    );
    """)
    
    # 4. Tickets table (core entity)
    cursor.execute("""
    CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER UNIQUE NOT NULL,  -- Original Freshdesk ticket ID
        company_id INTEGER,
        subject TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        priority INTEGER DEFAULT 1,
        ticket_type TEXT,
        source TEXT,
        requester_id INTEGER,  -- Original Freshdesk requester ID
        agent_id INTEGER,      -- References agents.id
        category_id INTEGER,   -- References categories.id
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        due_by TEXT,
        resolved_at TEXT,
        closed_at TEXT,
        tags TEXT,  -- JSON array of tags
        custom_fields TEXT,  -- JSON object for custom fields
        is_deleted BOOLEAN DEFAULT 0,
        FOREIGN KEY (company_id) REFERENCES companies (id),
        FOREIGN KEY (agent_id) REFERENCES agents (id),
        FOREIGN KEY (category_id) REFERENCES categories (id),
        UNIQUE(original_id)
    );
    """)
    
    # 5. Conversations table (ticket replies/notes)
    cursor.execute("""
    CREATE TABLE conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER UNIQUE NOT NULL,  -- Original Freshdesk conversation ID
        ticket_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        body_text TEXT,  -- Plain text version for search/analysis
        from_email TEXT,
        to_emails TEXT,  -- JSON array of recipient emails
        cc_emails TEXT,  -- JSON array of CC emails
        bcc_emails TEXT, -- JSON array of BCC emails
        user_id INTEGER, -- Original Freshdesk user ID
        is_private BOOLEAN DEFAULT 0,
        conversation_type TEXT,  -- 'reply', 'note', 'forward', etc.
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_deleted BOOLEAN DEFAULT 0,
        FOREIGN KEY (ticket_id) REFERENCES tickets (id) ON DELETE CASCADE,
        UNIQUE(original_id)
    );
    """)
    
    # 6. Attachments table (unified for all entities)
    cursor.execute("""
    CREATE TABLE attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER UNIQUE NOT NULL,  -- Original Freshdesk attachment ID
        parent_type TEXT NOT NULL,  -- 'ticket', 'conversation', 'knowledge_base'
        parent_id INTEGER NOT NULL, -- ID of the parent entity in our schema
        parent_original_id INTEGER, -- Original ID of the parent entity in Freshdesk
        name TEXT NOT NULL,
        content_type TEXT,
        size INTEGER,
        file_url TEXT,
        file_path TEXT,  -- Local file path if downloaded
        is_inline BOOLEAN DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_deleted BOOLEAN DEFAULT 0,
        UNIQUE(original_id),
        -- Ensure parent_type is valid
        CHECK (parent_type IN ('ticket', 'conversation', 'knowledge_base'))
    );
    """)
    
    # 7. Summaries table (LLM-generated summaries)
    cursor.execute("""
    CREATE TABLE summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        summary_text TEXT NOT NULL,
        summary_type TEXT DEFAULT 'auto',  -- 'auto', 'manual', 'batch'
        model_used TEXT,  -- LLM model identifier
        confidence_score REAL,
        token_count INTEGER,
        processing_time_ms INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (ticket_id) REFERENCES tickets (id) ON DELETE CASCADE
    );
    """)
    
    # 8. Processing logs table (for monitoring and debugging)
    cursor.execute("""
    CREATE TABLE processing_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_type TEXT NOT NULL,  -- 'migration', 'summarization', 'attachment_download', etc.
        entity_type TEXT,  -- 'ticket', 'conversation', 'attachment', etc.
        entity_id INTEGER,
        status TEXT NOT NULL,  -- 'started', 'completed', 'failed', 'skipped'
        message TEXT,
        error_details TEXT,
        processing_time_ms INTEGER,
        created_at TEXT NOT NULL
    );
    """)
    
    print("🔧 Creating indexes for optimal performance...")
    
    # Critical indexes for performance
    indexes = [
        # Companies
        "CREATE INDEX idx_companies_original_id ON companies (original_id);",
        "CREATE INDEX idx_companies_name ON companies (name);",
        "CREATE INDEX idx_companies_domain ON companies (domain);",
        
        # Agents
        "CREATE INDEX idx_agents_original_id ON agents (original_id);",
        "CREATE INDEX idx_agents_email ON agents (email);",
        "CREATE INDEX idx_agents_active ON agents (is_active);",
        
        # Tickets
        "CREATE INDEX idx_tickets_original_id ON tickets (original_id);",
        "CREATE INDEX idx_tickets_company_id ON tickets (company_id);",
        "CREATE INDEX idx_tickets_status ON tickets (status);",
        "CREATE INDEX idx_tickets_priority ON tickets (priority);",
        "CREATE INDEX idx_tickets_agent_id ON tickets (agent_id);",
        "CREATE INDEX idx_tickets_created_at ON tickets (created_at);",
        "CREATE INDEX idx_tickets_updated_at ON tickets (updated_at);",
        "CREATE INDEX idx_tickets_status_priority ON tickets (status, priority);",
        "CREATE INDEX idx_tickets_company_status ON tickets (company_id, status);",
        
        # Conversations
        "CREATE INDEX idx_conversations_original_id ON conversations (original_id);",
        "CREATE INDEX idx_conversations_ticket_id ON conversations (ticket_id);",
        "CREATE INDEX idx_conversations_created_at ON conversations (created_at);",
        "CREATE INDEX idx_conversations_ticket_created ON conversations (ticket_id, created_at);",
        
        # Attachments - optimized for the new schema
        "CREATE INDEX idx_attachments_original_id ON attachments (original_id);",
        "CREATE INDEX idx_attachments_parent ON attachments (parent_type, parent_id);",
        "CREATE INDEX idx_attachments_parent_original ON attachments (parent_type, parent_original_id);",
        "CREATE INDEX idx_attachments_name ON attachments (name);",
        "CREATE INDEX idx_attachments_content_type ON attachments (content_type);",
        
        # Summaries
        "CREATE INDEX idx_summaries_ticket_id ON summaries (ticket_id);",
        "CREATE INDEX idx_summaries_type ON summaries (summary_type);",
        "CREATE INDEX idx_summaries_active ON summaries (is_active);",
        "CREATE INDEX idx_summaries_created_at ON summaries (created_at);",
        
        # Processing logs
        "CREATE INDEX idx_processing_logs_operation ON processing_logs (operation_type);",
        "CREATE INDEX idx_processing_logs_entity ON processing_logs (entity_type, entity_id);",
        "CREATE INDEX idx_processing_logs_status ON processing_logs (status);",
        "CREATE INDEX idx_processing_logs_created_at ON processing_logs (created_at);",
    ]
    
    for index_sql in indexes:
        cursor.execute(index_sql)
    
    # Create some default categories
    default_categories = [
        ('General', 'General inquiries and requests'),
        ('Technical Support', 'Technical issues and troubleshooting'),
        ('Bug Report', 'Software bugs and issues'),
        ('Feature Request', 'New feature requests and suggestions'),
        ('Account Issues', 'Account-related problems and questions'),
    ]
    
    print("📋 Creating default categories...")
    for name, description in default_categories:
        cursor.execute("""
        INSERT INTO categories (name, description, created_at)
        VALUES (?, ?, ?)
        """, (name, description, datetime.now().isoformat()))
    
    conn.commit()
    
    # Verify schema creation
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"✅ Schema created successfully!")
    print(f"📊 Tables created: {', '.join(tables)}")
    
    # Show table counts
    print("\n📈 Initial table counts:")
    for table in tables:
        if table != 'sqlite_sequence':
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count}")
    
    conn.close()
    return True


def main():
    """Main function to create the clean schema."""
    db_path = "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_freshdesk_data_clean.db"
    
    print("🧹 Creating clean Freshdesk schema...")
    print(f"📍 Database path: {db_path}")
    
    if create_clean_schema(db_path):
        print(f"\n🎉 Clean schema created successfully at: {db_path}")
        print("🚀 Ready for data migration!")
    else:
        print("\n❌ Failed to create clean schema")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
