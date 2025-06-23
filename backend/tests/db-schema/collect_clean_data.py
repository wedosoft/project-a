#!/usr/bin/env python3
"""
Clean Data Collector for Freshdesk Multi-tenant SaaS
Collects data directly from the original source into the new clean schema.
"""

import sqlite3
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any


class FreshdeskCleanDataCollector:
    """Direct data collector for the clean schema."""
    
    def __init__(self, source_db_path: str, target_db_path: str):
        self.source_db_path = source_db_path
        self.target_db_path = target_db_path
        
        self.stats = {
            'tickets': {'processed': 0, 'collected': 0, 'errors': 0},
            'conversations': {'processed': 0, 'collected': 0, 'errors': 0},
            'attachments': {'processed': 0, 'collected': 0, 'errors': 0},
        }
    
    def collect_all_data(self):
        """Collect all data from source to target schema."""
        print("🚀 Starting clean data collection...")
        
        source_conn = sqlite3.connect(self.source_db_path)
        target_conn = sqlite3.connect(self.target_db_path)
        
        try:
            # Collect in order: tickets -> conversations -> attachments
            self.collect_tickets(source_conn, target_conn)
            self.collect_conversations(source_conn, target_conn)
            self.collect_attachments(source_conn, target_conn)
            
            # Print final statistics
            self.print_statistics()
            
        except Exception as e:
            print(f"❌ Collection failed: {e}")
            raise
        finally:
            source_conn.close()
            target_conn.close()
    
    def collect_tickets(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection):
        """Collect tickets from integrated_objects table."""
        print("🎫 Collecting tickets...")
        
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Get tickets from integrated_objects
        source_cursor.execute("""
        SELECT original_id, company_id, original_data, raw_data, created_at, updated_at
        FROM integrated_objects 
        WHERE object_type = 'integrated_ticket'
        AND (original_data IS NOT NULL OR raw_data IS NOT NULL)
        ORDER BY original_id
        """)
        
        for row in source_cursor.fetchall():
            self.stats['tickets']['processed'] += 1
            
            try:
                original_id, company_id, original_data, raw_data, created_at, updated_at = row
                
                # Parse JSON data (prefer raw_data over original_data)
                data_str = raw_data if raw_data else original_data
                if not data_str:
                    continue
                
                data = json.loads(data_str)
                
                # Extract ticket ID
                ticket_id = self._extract_id(data, original_id)
                
                # Basic ticket info
                subject = self._clean_text(data.get('subject', 'No Subject'))
                description = self._clean_text(data.get('description', ''))
                
                # Status and priority
                status = self._normalize_status(data.get('status'))
                priority = self._normalize_priority(data.get('priority'))
                
                # Requester and agent info
                requester_id = self._extract_requester_id(data)
                agent_id = self._extract_agent_id(data)
                
                # Timestamps
                created_at_iso = self._parse_datetime(data.get('created_at', created_at))
                updated_at_iso = self._parse_datetime(data.get('updated_at', updated_at))
                due_by_iso = self._parse_datetime(data.get('due_by'))
                resolved_at_iso = self._parse_datetime(data.get('resolved_at'))
                closed_at_iso = self._parse_datetime(data.get('closed_at'))
                
                # Tags and custom fields
                tags = json.dumps(data.get('tags', []), ensure_ascii=False) if data.get('tags') else None
                custom_fields = json.dumps(data.get('custom_fields', {}), ensure_ascii=False) if data.get('custom_fields') else None
                
                # Insert ticket
                target_cursor.execute("""
                INSERT OR REPLACE INTO tickets (
                    original_id, company_id, subject, description, status, priority,
                    ticket_type, source, requester_id, agent_id, created_at, updated_at,
                    due_by, resolved_at, closed_at, tags, custom_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    1,  # Default company ID
                    subject,
                    description,
                    status,
                    priority,
                    data.get('type', 'Question'),
                    data.get('source', 'Email'),
                    requester_id,
                    agent_id,
                    created_at_iso,
                    updated_at_iso,
                    due_by_iso,
                    resolved_at_iso,
                    closed_at_iso,
                    tags,
                    custom_fields
                ))
                
                self.stats['tickets']['collected'] += 1
                
                if self.stats['tickets']['collected'] % 500 == 0:
                    print(f"   📊 Progress: {self.stats['tickets']['collected']} tickets collected...")
                    target_conn.commit()
                
            except Exception as e:
                self.stats['tickets']['errors'] += 1
                print(f"⚠️  Failed to collect ticket {original_id}: {e}")
                continue
        
        target_conn.commit()
        print(f"✅ Tickets collection completed: {self.stats['tickets']['collected']}/{self.stats['tickets']['processed']}")
    
    def collect_conversations(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection):
        """Collect conversations from conversations table."""
        print("💬 Collecting conversations...")
        
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Get conversations
        source_cursor.execute("""
        SELECT original_id, ticket_original_id, body, body_text, 
               incoming, private, created_at, updated_at, raw_data
        FROM conversations 
        WHERE (body IS NOT NULL OR body_text IS NOT NULL OR raw_data IS NOT NULL)
        ORDER BY original_id
        """)
        
        for row in source_cursor.fetchall():
            self.stats['conversations']['processed'] += 1
            
            try:
                original_id, ticket_original_id, body, body_text, incoming, private, created_at, updated_at, raw_data = row
                
                # Extract conversation ID
                conversation_id = self._extract_id_from_string(original_id)
                
                # Get ticket ID from our tickets table
                ticket_original_id = self._extract_id_from_string(ticket_original_id)
                target_cursor.execute("SELECT id FROM tickets WHERE original_id = ?", (ticket_original_id,))
                ticket_result = target_cursor.fetchone()
                
                if not ticket_result:
                    self.stats['conversations']['errors'] += 1
                    continue
                
                ticket_id = ticket_result[0]
                
                # Parse additional data from raw_data if available
                additional_data = {}
                if raw_data:
                    try:
                        additional_data = json.loads(raw_data)
                    except:
                        pass
                
                # Clean up body text
                clean_body_text = body_text or self._clean_html(body or '')
                
                # Extract email info
                from_email = additional_data.get('from_email', '')
                to_emails = json.dumps(additional_data.get('to_emails', []), ensure_ascii=False) if additional_data.get('to_emails') else None
                cc_emails = json.dumps(additional_data.get('cc_emails', []), ensure_ascii=False) if additional_data.get('cc_emails') else None
                bcc_emails = json.dumps(additional_data.get('bcc_emails', []), ensure_ascii=False) if additional_data.get('bcc_emails') else None
                
                # Timestamps
                created_at_iso = self._parse_datetime(created_at)
                updated_at_iso = self._parse_datetime(updated_at)
                
                # Insert conversation
                target_cursor.execute("""
                INSERT OR REPLACE INTO conversations (
                    original_id, ticket_id, body, body_text, from_email, 
                    to_emails, cc_emails, bcc_emails, user_id, is_private,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conversation_id,
                    ticket_id,
                    body or '',
                    clean_body_text,
                    from_email,
                    to_emails,
                    cc_emails,
                    bcc_emails,
                    additional_data.get('user_id'),
                    bool(private),
                    created_at_iso,
                    updated_at_iso
                ))
                
                self.stats['conversations']['collected'] += 1
                
                if self.stats['conversations']['collected'] % 1000 == 0:
                    print(f"   📊 Progress: {self.stats['conversations']['collected']} conversations collected...")
                    target_conn.commit()
                
            except Exception as e:
                self.stats['conversations']['errors'] += 1
                print(f"⚠️  Failed to collect conversation {original_id}: {e}")
                continue
        
        target_conn.commit()
        print(f"✅ Conversations collection completed: {self.stats['conversations']['collected']}/{self.stats['conversations']['processed']}")
    
    def collect_attachments(self, source_conn: sqlite3.Connection, target_conn: sqlite3.Connection):
        """Collect attachments with new parent_type/parent_id schema."""
        print("📎 Collecting attachments...")
        
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        # Get attachments
        source_cursor.execute("""
        SELECT original_id, parent_type, parent_original_id, name, content_type,
               size, created_at, updated_at, attachment_url, raw_data
        FROM attachments
        ORDER BY original_id
        """)
        
        for row in source_cursor.fetchall():
            self.stats['attachments']['processed'] += 1
            
            try:
                original_id, parent_type, parent_original_id, name, content_type, size, created_at, updated_at, attachment_url, raw_data = row
                
                # Extract attachment ID
                attachment_id = self._extract_id_from_string(original_id)
                
                # Determine parent based on type
                parent_id = None
                parent_schema_id = None
                
                if parent_type == 'ticket':
                    parent_original_id_clean = self._extract_id_from_string(parent_original_id)
                    target_cursor.execute("SELECT id FROM tickets WHERE original_id = ?", (parent_original_id_clean,))
                    result = target_cursor.fetchone()
                    if result:
                        parent_id = result[0]
                        parent_schema_id = parent_original_id_clean
                
                elif parent_type == 'conversation':
                    parent_original_id_clean = self._extract_id_from_string(parent_original_id)
                    target_cursor.execute("SELECT id FROM conversations WHERE original_id = ?", (parent_original_id_clean,))
                    result = target_cursor.fetchone()
                    if result:
                        parent_id = result[0]
                        parent_schema_id = parent_original_id_clean
                
                elif parent_type == 'article':
                    # Knowledge base attachments - keep for future
                    parent_type = 'knowledge_base'
                    parent_id = None  # Will be handled later when KB is implemented
                    parent_schema_id = self._extract_id_from_string(parent_original_id)
                
                # Skip if parent not found (except for knowledge_base)
                if parent_type != 'knowledge_base' and not parent_id:
                    self.stats['attachments']['errors'] += 1
                    continue
                
                # Parse additional data
                additional_data = {}
                if raw_data:
                    try:
                        additional_data = json.loads(raw_data)
                    except:
                        pass
                
                # File info
                file_name = name or additional_data.get('name', 'unknown_file')
                file_size = size or additional_data.get('size', 0)
                file_content_type = content_type or additional_data.get('content_type', 'application/octet-stream')
                file_url = attachment_url or additional_data.get('attachment_url', '')
                
                # Timestamps
                created_at_iso = self._parse_datetime(created_at)
                updated_at_iso = self._parse_datetime(updated_at)
                
                # Insert attachment
                target_cursor.execute("""
                INSERT OR REPLACE INTO attachments (
                    original_id, parent_type, parent_id, parent_original_id,
                    name, content_type, size, file_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attachment_id,
                    parent_type,
                    parent_id,
                    parent_schema_id,
                    file_name,
                    file_content_type,
                    file_size,
                    file_url,
                    created_at_iso or datetime.now().isoformat(),
                    updated_at_iso or datetime.now().isoformat()
                ))
                
                self.stats['attachments']['collected'] += 1
                
                if self.stats['attachments']['collected'] % 100 == 0:
                    print(f"   📊 Progress: {self.stats['attachments']['collected']} attachments collected...")
                    target_conn.commit()
                
            except Exception as e:
                self.stats['attachments']['errors'] += 1
                print(f"⚠️  Failed to collect attachment {original_id}: {e}")
                continue
        
        target_conn.commit()
        print(f"✅ Attachments collection completed: {self.stats['attachments']['collected']}/{self.stats['attachments']['processed']}")
    
    # Helper methods
    def _extract_id(self, data: Dict[str, Any], fallback_id: str) -> int:
        """Extract ID from data or fallback string."""
        if 'id' in data and data['id']:
            return int(data['id'])
        return self._extract_id_from_string(fallback_id)
    
    def _extract_id_from_string(self, id_string: str) -> int:
        """Extract numeric ID from string."""
        if not id_string:
            return 0
        
        # Find first number in string
        match = re.search(r'\d+', str(id_string))
        if match:
            return int(match.group())
        return 0
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ''
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', str(text))
        return text.strip()
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and clean text."""
        if not html:
            return ''
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', str(html))
        return self._clean_text(text)
    
    def _normalize_status(self, status: Any) -> str:
        """Normalize ticket status."""
        if not status:
            return 'Open'
        
        status_str = str(status).lower()
        status_map = {
            '2': 'Open', 'open': 'Open',
            '3': 'Pending', 'pending': 'Pending',
            '4': 'Resolved', 'resolved': 'Resolved',
            '5': 'Closed', 'closed': 'Closed'
        }
        
        return status_map.get(status_str, str(status))
    
    def _normalize_priority(self, priority: Any) -> int:
        """Normalize ticket priority."""
        if not priority:
            return 1
        
        try:
            return int(priority)
        except:
            priority_str = str(priority).lower()
            priority_map = {
                'low': 1, 'medium': 2, 'high': 3, 'urgent': 4
            }
            return priority_map.get(priority_str, 1)
    
    def _extract_requester_id(self, data: Dict[str, Any]) -> Optional[int]:
        """Extract requester ID."""
        requester = data.get('requester')
        if isinstance(requester, dict) and 'id' in requester:
            return int(requester['id'])
        elif data.get('requester_id'):
            return int(data['requester_id'])
        return None
    
    def _extract_agent_id(self, data: Dict[str, Any]) -> Optional[int]:
        """Extract agent ID."""
        responder = data.get('responder')
        if isinstance(responder, dict) and 'id' in responder:
            return int(responder['id'])
        elif data.get('responder_id'):
            return int(data['responder_id'])
        return None
    
    def _parse_datetime(self, dt_value: Any) -> Optional[str]:
        """Parse datetime to ISO format."""
        if not dt_value:
            return None
        
        try:
            # If already a string, return as is
            if isinstance(dt_value, str):
                return dt_value
            
            # Convert to string
            return str(dt_value)
        except:
            return None
    
    def print_statistics(self):
        """Print collection statistics."""
        print("\n🎉 Data collection completed!")
        print("\n📊 Collection Statistics:")
        
        total_processed = 0
        total_collected = 0
        total_errors = 0
        
        for entity, stats in self.stats.items():
            print(f"   {entity.capitalize()}:")
            print(f"     Processed: {stats['processed']}")
            print(f"     Collected: {stats['collected']}")
            print(f"     Errors:    {stats['errors']}")
            
            total_processed += stats['processed']
            total_collected += stats['collected']
            total_errors += stats['errors']
        
        print(f"\n   Total:")
        print(f"     Processed: {total_processed}")
        print(f"     Collected: {total_collected}")
        print(f"     Errors:    {total_errors}")
        
        if total_processed > 0:
            success_rate = (total_collected / total_processed) * 100
            print(f"     Success Rate: {success_rate:.1f}%")


def main():
    """Main function to collect clean data."""
    source_db = "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_freshdesk_data.db"
    target_db = "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_freshdesk_data_clean.db"
    
    print("🧹 Freshdesk Clean Data Collection")
    print(f"📥 Source: {source_db}")
    print(f"📤 Target: {target_db}")
    
    collector = FreshdeskCleanDataCollector(source_db, target_db)
    
    try:
        collector.collect_all_data()
        print("\n✅ Collection completed successfully!")
        return 0
    except Exception as e:
        print(f"\n❌ Collection failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
