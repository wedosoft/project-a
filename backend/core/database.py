"""
SQLite 데이터베이스 연결 및 모델 정의

Freshdesk 데이터 수집을 위한 SQLite 데이터베이스 구조를 정의합니다.
테스트용 데이터는 freshdesk_test_data.db에, 전체 데이터는 freshdesk_full_data.db에 저장됩니다.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class SQLiteDatabase:
    """SQLite 데이터베이스 연결 및 관리 클래스"""
    
    def __init__(self, db_name: str = "freshdesk_test_data.db"):
        """
        SQLite 데이터베이스 초기화
        
        Args:
            db_name: 데이터베이스 파일명 
                    - "freshdesk_test_data.db" (테스트용, 100건 제한)
                    - "freshdesk_full_data.db" (전체 데이터)
        """
        self.db_path = Path(__file__).parent.parent / "data" / db_name
        self.db_path.parent.mkdir(exist_ok=True)
        
        self.connection = None
        logger.info(f"SQLite 데이터베이스 초기화: {self.db_path}")
    
    def connect(self):
        """데이터베이스 연결"""
        self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row  # dict 형태로 결과 반환
        logger.info(f"데이터베이스 연결 완료: {self.db_path}")
    
    def disconnect(self):
        """데이터베이스 연결 해제"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("데이터베이스 연결 해제")
    
    def create_tables(self):
        """테이블 생성"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        # 1. 티켓 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY,
                freshdesk_id INTEGER UNIQUE NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT DEFAULT 'freshdesk',
                subject TEXT,
                description TEXT,
                status TEXT,
                priority TEXT,
                type TEXT,
                source TEXT,
                requester_id INTEGER,
                responder_id INTEGER,
                group_id INTEGER,
                created_at TEXT,
                updated_at TEXT,
                due_by TEXT,
                fr_due_by TEXT,
                is_escalated BOOLEAN,
                tags TEXT, -- JSON 문자열
                custom_fields TEXT, -- JSON 문자열
                raw_data TEXT, -- 전체 원본 데이터 JSON
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 대화 테이블 (티켓 내 대화)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                freshdesk_id INTEGER UNIQUE NOT NULL,
                ticket_id INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT DEFAULT 'freshdesk',
                user_id INTEGER,
                body TEXT,
                body_text TEXT,
                incoming BOOLEAN,
                private BOOLEAN,
                source TEXT,
                created_at TEXT,
                updated_at TEXT,
                attachments TEXT, -- JSON 문자열
                raw_data TEXT, -- 전체 원본 데이터 JSON
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(ticket_id) REFERENCES tickets(freshdesk_id)
            )
        """)
        
        # 3. 지식베이스 문서 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base_articles (
                id INTEGER PRIMARY KEY,
                freshdesk_id INTEGER UNIQUE NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT DEFAULT 'freshdesk',
                title TEXT,
                description TEXT,
                status TEXT,
                category_id INTEGER,
                folder_id INTEGER,
                author_id INTEGER,
                type TEXT,
                tags TEXT, -- JSON 문자열
                created_at TEXT,
                updated_at TEXT,
                thumbs_up INTEGER DEFAULT 0,
                thumbs_down INTEGER DEFAULT 0,
                raw_data TEXT, -- 전체 원본 데이터 JSON
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. 첨부파일 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY,
                freshdesk_id INTEGER UNIQUE NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT DEFAULT 'freshdesk',
                parent_type TEXT, -- 'ticket', 'conversation', 'article'
                parent_id INTEGER,
                name TEXT,
                content_type TEXT,
                size INTEGER,
                created_at TEXT,
                updated_at TEXT,
                attachment_url TEXT,
                raw_data TEXT, -- 전체 원본 데이터 JSON
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 5. 수집 작업 로그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                job_type TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                tickets_collected INTEGER DEFAULT 0,
                conversations_collected INTEGER DEFAULT 0,
                articles_collected INTEGER DEFAULT 0,
                attachments_collected INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                error_message TEXT,
                config_data TEXT, -- JSON 문자열
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 인덱스 생성
        # Tickets 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_company_id ON tickets(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_freshdesk_id ON tickets(freshdesk_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)")
        
        # Conversations 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_company_id ON conversations(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_ticket_id ON conversations(ticket_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)")
        
        # Knowledge base articles 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_company_id ON knowledge_base_articles(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_freshdesk_id ON knowledge_base_articles(freshdesk_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_status ON knowledge_base_articles(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_category_id ON knowledge_base_articles(category_id)")
        
        # Attachments 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_company_id ON attachments(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_parent ON attachments(parent_type, parent_id)")
        
        # Collection logs 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_company_id ON collection_logs(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_job_id ON collection_logs(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_status ON collection_logs(status)")
        
        self.connection.commit()
        logger.info("모든 테이블 생성 완료")
    
    def insert_ticket(self, ticket_data: Dict[str, Any]) -> int:
        """티켓 데이터 삽입"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO tickets (
                freshdesk_id, company_id, platform, subject, description,
                status, priority, type, source, requester_id, responder_id,
                group_id, created_at, updated_at, due_by, fr_due_by,
                is_escalated, tags, custom_fields, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_data.get('id'),
            ticket_data.get('company_id'),
            ticket_data.get('platform', 'freshdesk'),
            ticket_data.get('subject'),
            ticket_data.get('description'),
            ticket_data.get('status'),
            ticket_data.get('priority'),
            ticket_data.get('type'),
            ticket_data.get('source'),
            ticket_data.get('requester_id'),
            ticket_data.get('responder_id'),
            ticket_data.get('group_id'),
            ticket_data.get('created_at'),
            ticket_data.get('updated_at'),
            ticket_data.get('due_by'),
            ticket_data.get('fr_due_by'),
            ticket_data.get('is_escalated'),
            json.dumps(ticket_data.get('tags', [])),
            json.dumps(ticket_data.get('custom_fields', {})),
            json.dumps(ticket_data)
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def insert_conversation(self, conversation_data: Dict[str, Any]) -> int:
        """대화 데이터 삽입"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO conversations (
                freshdesk_id, ticket_id, company_id, platform, user_id,
                body, body_text, incoming, private, source,
                created_at, updated_at, attachments, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation_data.get('id'),
            conversation_data.get('ticket_id'),
            conversation_data.get('company_id'),
            conversation_data.get('platform', 'freshdesk'),
            conversation_data.get('user_id'),
            conversation_data.get('body'),
            conversation_data.get('body_text'),
            conversation_data.get('incoming'),
            conversation_data.get('private'),
            conversation_data.get('source'),
            conversation_data.get('created_at'),
            conversation_data.get('updated_at'),
            json.dumps(conversation_data.get('attachments', [])),
            json.dumps(conversation_data)
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def insert_article(self, article_data: Dict[str, Any]) -> int:
        """지식베이스 문서 삽입"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO knowledge_base_articles (
                freshdesk_id, company_id, platform, title, description,
                status, category_id, folder_id, author_id, type,
                tags, created_at, updated_at, thumbs_up, thumbs_down, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article_data.get('id'),
            article_data.get('company_id'),
            article_data.get('platform', 'freshdesk'),
            article_data.get('title'),
            article_data.get('description'),
            article_data.get('status'),
            article_data.get('category_id'),
            article_data.get('folder_id'),
            article_data.get('author_id'),
            article_data.get('type'),
            json.dumps(article_data.get('tags', [])),
            article_data.get('created_at'),
            article_data.get('updated_at'),
            article_data.get('thumbs_up', 0),
            article_data.get('thumbs_down', 0),
            json.dumps(article_data)
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def log_collection_job(self, job_data: Dict[str, Any]) -> int:
        """수집 작업 로그 기록"""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT INTO collection_logs (
                job_id, company_id, job_type, status, start_time, end_time,
                tickets_collected, conversations_collected, articles_collected,
                attachments_collected, errors_count, error_message, config_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_data.get('job_id'),
            job_data.get('company_id'),
            job_data.get('job_type'),
            job_data.get('status'),
            job_data.get('start_time'),
            job_data.get('end_time'),
            job_data.get('tickets_collected', 0),
            job_data.get('conversations_collected', 0),
            job_data.get('articles_collected', 0),
            job_data.get('attachments_collected', 0),
            job_data.get('errors_count', 0),
            job_data.get('error_message'),
            json.dumps(job_data.get('config', {}))
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def get_collection_stats(self, company_id: str) -> Dict[str, int]:
        """수집 통계 조회"""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # 티켓 수
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE company_id = ?", (company_id,))
        stats['tickets'] = cursor.fetchone()[0]
        
        # 대화 수
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE company_id = ?", (company_id,))
        stats['conversations'] = cursor.fetchone()[0]
        
        # 지식베이스 문서 수
        cursor.execute("SELECT COUNT(*) FROM knowledge_base_articles WHERE company_id = ?", (company_id,))
        stats['articles'] = cursor.fetchone()[0]
        
        # 첨부파일 수
        cursor.execute("SELECT COUNT(*) FROM attachments WHERE company_id = ?", (company_id,))
        stats['attachments'] = cursor.fetchone()[0]
        
        return stats


# 글로벌 데이터베이스 인스턴스
test_db = SQLiteDatabase("freshdesk_test_data.db")
full_db = SQLiteDatabase("freshdesk_full_data.db")


def get_database(test_mode: bool = True) -> SQLiteDatabase:
    """데이터베이스 인스턴스 반환
    
    Args:
        test_mode: True면 테스트 DB, False면 전체 데이터 DB
    
    Returns:
        SQLiteDatabase 인스턴스
    """
    db = test_db if test_mode else full_db
    
    if not db.connection:
        db.connect()
        db.create_tables()
    
    return db
