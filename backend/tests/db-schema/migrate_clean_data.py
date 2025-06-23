#!/usr/bin/env python3
"""
Clean Data Migration Script for Freshdesk Multi-tenant SaaS
Migrates data from original Freshdesk schema to the new clean, optimized schema.
"""

import sqlite3
import json
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class FreshdeskCleanDataMigrator:
    """Migrator for Freshdesk data to clean schema."""
    
    def __init__(self, source_db_path: str, target_db_path: str):
        self.source_db_path = source_db_path
        self.target_db_path = target_db_path
        self.source_conn = None
        self.target_conn = None
        
        # Mapping tables for ID conversions
        self.company_id_map = {}  # original_id -> new_id
        self.agent_id_map = {}    # original_id -> new_id
        self.ticket_id_map = {}   # original_id -> new_id
        self.conversation_id_map = {}  # original_id -> new_id
        
        self.stats = {
            'companies': {'processed': 0, 'migrated': 0, 'errors': 0},
            'agents': {'processed': 0, 'migrated': 0, 'errors': 0},
            'tickets': {'processed': 0, 'migrated': 0, 'errors': 0},
            'conversations': {'processed': 0, 'migrated': 0, 'errors': 0},
            'attachments': {'processed': 0, 'migrated': 0, 'errors': 0},
            'summaries': {'processed': 0, 'migrated': 0, 'errors': 0},
        }
    
    def connect_databases(self):
        """Connect to source and target databases."""
        try:
            self.source_conn = sqlite3.connect(self.source_db_path)
            self.source_conn.row_factory = sqlite3.Row
            
            self.target_conn = sqlite3.connect(self.target_db_path)
            self.target_conn.execute("PRAGMA foreign_keys = ON;")
            
            print("✅ Connected to both databases")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def close_connections(self):
        """Close database connections."""
        if self.source_conn:
            self.source_conn.close()
        if self.target_conn:
            self.target_conn.close()
    
    def log_processing(self, operation_type: str, entity_type: str, entity_id: int, 
                      status: str, message: str = None, error_details: str = None,
                      processing_time_ms: int = None):
        """Log processing operation."""
        self.target_conn.execute("""
        INSERT INTO processing_logs 
        (operation_type, entity_type, entity_id, status, message, error_details, processing_time_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (operation_type, entity_type, entity_id, status, message, error_details, 
              processing_time_ms, datetime.now().isoformat()))
    
    def get_source_table_info(self, table_name: str) -> List[str]:
        """Get column names from source table."""
        try:
            cursor = self.source_conn.execute(f"PRAGMA table_info({table_name});")
            return [row[1] for row in cursor.fetchall()]
        except Exception:
            return []
    
    def migrate_companies(self) -> bool:
        """Migrate companies data."""
        print("🏢 Migrating companies...")
        
        # Check if companies table exists in source
        columns = self.get_source_table_info('companies')
        if not columns:
            print("⚠️  No companies table found in source, creating default company...")
            # Create a default company
            cursor = self.target_conn.execute("""
            INSERT INTO companies (original_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """, (1, "Default Company", "Default company for migrated data", 
                  datetime.now().isoformat(), datetime.now().isoformat()))
            
            company_id = cursor.lastrowid
            self.company_id_map[1] = company_id
            self.stats['companies']['migrated'] = 1
            print(f"✅ Created default company with ID: {company_id}")
            return True
        
        try:
            cursor = self.source_conn.execute("SELECT * FROM companies;")
            for row in cursor.fetchall():
                self.stats['companies']['processed'] += 1
                
                try:
                    target_cursor = self.target_conn.execute("""
                    INSERT INTO companies (original_id, name, domain, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        row['id'],
                        row.get('name', 'Unknown Company'),
                        row.get('domain', ''),
                        row.get('description', ''),
                        row.get('created_at', datetime.now().isoformat()),
                        row.get('updated_at', datetime.now().isoformat())
                    ))
                    
                    new_id = target_cursor.lastrowid
                    self.company_id_map[row['id']] = new_id
                    self.stats['companies']['migrated'] += 1
                    
                    self.log_processing('migration', 'company', row['id'], 'completed')
                    
                except Exception as e:
                    self.stats['companies']['errors'] += 1
                    self.log_processing('migration', 'company', row['id'], 'failed', error_details=str(e))
                    print(f"⚠️  Failed to migrate company ID {row['id']}: {e}")
            
            self.target_conn.commit()
            print(f"✅ Companies migration completed: {self.stats['companies']['migrated']}/{self.stats['companies']['processed']}")
            return True
            
        except Exception as e:
            print(f"❌ Companies migration failed: {e}")
            return False
    
    def migrate_agents(self) -> bool:
        """Migrate agents data."""
        print("👥 Migrating agents...")
        
        columns = self.get_source_table_info('agents')
        if not columns:
            print("⚠️  No agents table found in source, skipping...")
            return True
        
        try:
            cursor = self.source_conn.execute("SELECT * FROM agents;")
            for row in cursor.fetchall():
                self.stats['agents']['processed'] += 1
                
                try:
                    target_cursor = self.target_conn.execute("""
                    INSERT INTO agents (original_id, email, name, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['id'],
                        row.get('email', f'agent{row["id"]}@unknown.com'),
                        row.get('name', f'Agent {row["id"]}'),
                        row.get('role', 'agent'),
                        row.get('available', True),
                        row.get('created_at', datetime.now().isoformat()),
                        row.get('updated_at', datetime.now().isoformat())
                    ))
                    
                    new_id = target_cursor.lastrowid
                    self.agent_id_map[row['id']] = new_id
                    self.stats['agents']['migrated'] += 1
                    
                    self.log_processing('migration', 'agent', row['id'], 'completed')
                    
                except Exception as e:
                    self.stats['agents']['errors'] += 1
                    self.log_processing('migration', 'agent', row['id'], 'failed', error_details=str(e))
                    print(f"⚠️  Failed to migrate agent ID {row['id']}: {e}")
            
            self.target_conn.commit()
            print(f"✅ Agents migration completed: {self.stats['agents']['migrated']}/{self.stats['agents']['processed']}")
            return True
            
        except Exception as e:
            print(f"❌ Agents migration failed: {e}")
            return False
    
    def migrate_tickets(self) -> bool:
        """Migrate tickets data."""
        print("🎫 Migrating tickets...")
        
        try:
            cursor = self.source_conn.execute("SELECT * FROM tickets ORDER BY id;")
            for row in cursor.fetchall():
                self.stats['tickets']['processed'] += 1
                
                try:
                    # Get or create default company
                    company_id = self.company_id_map.get(row.get('company_id'), 1)
                    if company_id not in self.company_id_map.values():
                        company_id = 1  # Default company
                    
                    # Get agent ID if exists
                    agent_id = self.agent_id_map.get(row.get('responder_id'))
                    
                    # Prepare tags and custom fields as JSON
                    tags = json.dumps(row.get('tags', [])) if row.get('tags') else None
                    
                    target_cursor = self.target_conn.execute("""
                    INSERT INTO tickets (
                        original_id, company_id, subject, description, status, priority, 
                        ticket_type, source, requester_id, agent_id, created_at, updated_at,
                        due_by, resolved_at, closed_at, tags
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['id'],
                        company_id,
                        row.get('subject', 'No Subject'),
                        row.get('description', ''),
                        row.get('status', 'Open'),
                        row.get('priority', 1),
                        row.get('type', 'Question'),
                        row.get('source', 'Email'),
                        row.get('requester_id'),
                        agent_id,
                        row.get('created_at', datetime.now().isoformat()),
                        row.get('updated_at', datetime.now().isoformat()),
                        row.get('due_by'),
                        row.get('resolved_at'),
                        row.get('closed_at'),
                        tags
                    ))
                    
                    new_id = target_cursor.lastrowid
                    self.ticket_id_map[row['id']] = new_id
                    self.stats['tickets']['migrated'] += 1
                    
                    self.log_processing('migration', 'ticket', row['id'], 'completed')
                    
                    if self.stats['tickets']['migrated'] % 500 == 0:
                        print(f"   📊 Progress: {self.stats['tickets']['migrated']} tickets migrated...")
                        self.target_conn.commit()
                    
                except Exception as e:
                    self.stats['tickets']['errors'] += 1
                    self.log_processing('migration', 'ticket', row['id'], 'failed', error_details=str(e))
                    print(f"⚠️  Failed to migrate ticket ID {row['id']}: {e}")
            
            self.target_conn.commit()
            print(f"✅ Tickets migration completed: {self.stats['tickets']['migrated']}/{self.stats['tickets']['processed']}")
            return True
            
        except Exception as e:
            print(f"❌ Tickets migration failed: {e}")
            return False
    
    def migrate_conversations(self) -> bool:
        """Migrate conversations data."""
        print("💬 Migrating conversations...")
        
        try:
            cursor = self.source_conn.execute("SELECT * FROM conversations ORDER BY id;")
            for row in cursor.fetchall():
                self.stats['conversations']['processed'] += 1
                
                try:
                    # Get the new ticket ID
                    ticket_id = self.ticket_id_map.get(row['ticket_id'])
                    if not ticket_id:
                        self.stats['conversations']['errors'] += 1
                        self.log_processing('migration', 'conversation', row['id'], 'failed', 
                                          error_details=f"Ticket {row['ticket_id']} not found")
                        continue
                    
                    # Clean up body_text for better search
                    body_text = None
                    if row.get('body_text'):
                        # Remove HTML tags and extra whitespace
                        body_text = re.sub(r'<[^>]+>', ' ', row['body_text'])
                        body_text = re.sub(r'\s+', ' ', body_text).strip()
                    
                    # Prepare email arrays as JSON
                    to_emails = json.dumps(row.get('to_emails', [])) if row.get('to_emails') else None
                    cc_emails = json.dumps(row.get('cc_emails', [])) if row.get('cc_emails') else None
                    bcc_emails = json.dumps(row.get('bcc_emails', [])) if row.get('bcc_emails') else None
                    
                    target_cursor = self.target_conn.execute("""
                    INSERT INTO conversations (
                        original_id, ticket_id, body, body_text, from_email, to_emails, 
                        cc_emails, bcc_emails, user_id, is_private, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['id'],
                        ticket_id,
                        row.get('body', ''),
                        body_text,
                        row.get('from_email'),
                        to_emails,
                        cc_emails,
                        bcc_emails,
                        row.get('user_id'),
                        row.get('private', False),
                        row.get('created_at', datetime.now().isoformat()),
                        row.get('updated_at', datetime.now().isoformat())
                    ))
                    
                    new_id = target_cursor.lastrowid
                    self.conversation_id_map[row['id']] = new_id
                    self.stats['conversations']['migrated'] += 1
                    
                    self.log_processing('migration', 'conversation', row['id'], 'completed')
                    
                    if self.stats['conversations']['migrated'] % 1000 == 0:
                        print(f"   📊 Progress: {self.stats['conversations']['migrated']} conversations migrated...")
                        self.target_conn.commit()
                    
                except Exception as e:
                    self.stats['conversations']['errors'] += 1
                    self.log_processing('migration', 'conversation', row['id'], 'failed', error_details=str(e))
                    print(f"⚠️  Failed to migrate conversation ID {row['id']}: {e}")
            
            self.target_conn.commit()
            print(f"✅ Conversations migration completed: {self.stats['conversations']['migrated']}/{self.stats['conversations']['processed']}")
            return True
            
        except Exception as e:
            print(f"❌ Conversations migration failed: {e}")
            return False
    
    def migrate_attachments(self) -> bool:
        """Migrate attachments data with new parent_type/parent_id schema."""
        print("📎 Migrating attachments...")
        
        try:
            cursor = self.source_conn.execute("SELECT * FROM attachments ORDER BY id;")
            for row in cursor.fetchall():
                self.stats['attachments']['processed'] += 1
                
                try:
                    parent_type = None
                    parent_id = None
                    parent_original_id = None
                    
                    # Determine parent type and ID based on source data
                    if row.get('ticket_id'):
                        parent_type = 'ticket'
                        parent_id = self.ticket_id_map.get(row['ticket_id'])
                        parent_original_id = row['ticket_id']
                    elif row.get('conversation_id'):
                        parent_type = 'conversation'
                        parent_id = self.conversation_id_map.get(row['conversation_id'])
                        parent_original_id = row['conversation_id']
                    else:
                        # Skip attachments without parent
                        self.stats['attachments']['errors'] += 1
                        self.log_processing('migration', 'attachment', row['id'], 'failed', 
                                          error_details="No parent ticket or conversation found")
                        continue
                    
                    if not parent_id:
                        # Parent entity not migrated, skip
                        self.stats['attachments']['errors'] += 1
                        self.log_processing('migration', 'attachment', row['id'], 'failed', 
                                          error_details=f"Parent {parent_type} not found in mapping")
                        continue
                    
                    self.target_conn.execute("""
                    INSERT INTO attachments (
                        original_id, parent_type, parent_id, parent_original_id, name, 
                        content_type, size, file_url, is_inline, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['id'],
                        parent_type,
                        parent_id,
                        parent_original_id,
                        row.get('name', 'Unknown File'),
                        row.get('content_type', 'application/octet-stream'),
                        row.get('size', 0),
                        row.get('attachment_url'),
                        row.get('inline', False),
                        row.get('created_at', datetime.now().isoformat()),
                        row.get('updated_at', datetime.now().isoformat())
                    ))
                    
                    self.stats['attachments']['migrated'] += 1
                    self.log_processing('migration', 'attachment', row['id'], 'completed')
                    
                    if self.stats['attachments']['migrated'] % 100 == 0:
                        print(f"   📊 Progress: {self.stats['attachments']['migrated']} attachments migrated...")
                        self.target_conn.commit()
                    
                except Exception as e:
                    self.stats['attachments']['errors'] += 1
                    self.log_processing('migration', 'attachment', row['id'], 'failed', error_details=str(e))
                    print(f"⚠️  Failed to migrate attachment ID {row['id']}: {e}")
            
            self.target_conn.commit()
            print(f"✅ Attachments migration completed: {self.stats['attachments']['migrated']}/{self.stats['attachments']['processed']}")
            return True
            
        except Exception as e:
            print(f"❌ Attachments migration failed: {e}")
            return False
    
    def migrate_summaries(self) -> bool:
        """Migrate existing summaries data."""
        print("📝 Migrating summaries...")
        
        columns = self.get_source_table_info('summaries')
        if not columns:
            print("⚠️  No summaries table found in source, skipping...")
            return True
        
        try:
            cursor = self.source_conn.execute("SELECT * FROM summaries ORDER BY id;")
            for row in cursor.fetchall():
                self.stats['summaries']['processed'] += 1
                
                try:
                    # Get the new ticket ID
                    ticket_id = self.ticket_id_map.get(row['ticket_id'])
                    if not ticket_id:
                        self.stats['summaries']['errors'] += 1
                        self.log_processing('migration', 'summary', row['id'], 'failed', 
                                          error_details=f"Ticket {row['ticket_id']} not found")
                        continue
                    
                    self.target_conn.execute("""
                    INSERT INTO summaries (
                        ticket_id, summary_text, summary_type, model_used, 
                        confidence_score, token_count, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticket_id,
                        row.get('summary_text', ''),
                        row.get('summary_type', 'auto'),
                        row.get('model_used', 'unknown'),
                        row.get('confidence_score'),
                        row.get('token_count'),
                        row.get('created_at', datetime.now().isoformat()),
                        row.get('updated_at', datetime.now().isoformat())
                    ))
                    
                    self.stats['summaries']['migrated'] += 1
                    self.log_processing('migration', 'summary', row['id'], 'completed')
                    
                except Exception as e:
                    self.stats['summaries']['errors'] += 1
                    self.log_processing('migration', 'summary', row['id'], 'failed', error_details=str(e))
                    print(f"⚠️  Failed to migrate summary ID {row['id']}: {e}")
            
            self.target_conn.commit()
            print(f"✅ Summaries migration completed: {self.stats['summaries']['migrated']}/{self.stats['summaries']['processed']}")
            return True
            
        except Exception as e:
            print(f"❌ Summaries migration failed: {e}")
            return False
    
    def run_migration(self) -> bool:
        """Run the complete migration process."""
        print("🚀 Starting clean data migration...")
        
        if not self.connect_databases():
            return False
        
        try:
            # Migration order is important due to foreign key constraints
            migration_steps = [
                ('Companies', self.migrate_companies),
                ('Agents', self.migrate_agents),
                ('Tickets', self.migrate_tickets),
                ('Conversations', self.migrate_conversations),
                ('Attachments', self.migrate_attachments),
                ('Summaries', self.migrate_summaries),
            ]
            
            for step_name, migration_func in migration_steps:
                print(f"\n--- {step_name} Migration ---")
                if not migration_func():
                    print(f"❌ {step_name} migration failed, stopping...")
                    return False
            
            # Final statistics
            print("\n🎉 Migration completed successfully!")
            print("\n📊 Final Statistics:")
            total_processed = 0
            total_migrated = 0
            total_errors = 0
            
            for entity, stats in self.stats.items():
                print(f"   {entity.capitalize()}:")
                print(f"     Processed: {stats['processed']}")
                print(f"     Migrated:  {stats['migrated']}")
                print(f"     Errors:    {stats['errors']}")
                
                total_processed += stats['processed']
                total_migrated += stats['migrated']
                total_errors += stats['errors']
            
            print(f"\n   Total:")
            print(f"     Processed: {total_processed}")
            print(f"     Migrated:  {total_migrated}")
            print(f"     Errors:    {total_errors}")
            print(f"     Success Rate: {(total_migrated/total_processed*100):.1f}%" if total_processed > 0 else "N/A")
            
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False
        finally:
            self.close_connections()


def main():
    """Main function to run the migration."""
    source_db = "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_freshdesk_data.db"
    target_db = "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_freshdesk_data_clean.db"
    
    print("🧹 Freshdesk Clean Data Migration")
    print(f"📥 Source: {source_db}")
    print(f"📤 Target: {target_db}")
    
    migrator = FreshdeskCleanDataMigrator(source_db, target_db)
    
    if migrator.run_migration():
        print("\n✅ Migration completed successfully!")
        return 0
    else:
        print("\n❌ Migration failed!")
        return 1


if __name__ == "__main__":
    exit(main())
