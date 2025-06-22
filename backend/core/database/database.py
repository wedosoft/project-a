"""
SQLite 데이터베이스 연결 및 모델 정의

멀티플랫폼 데이터 수집을 위한 SQLite 데이터베이스 구조를 정의합니다.
플랫폼별로 별도 데이터베이스 파일이 생성됩니다 (예: freshdesk_data.db, zendesk_data.db).
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)

# 멀티테넌트 데이터베이스 인스턴스 캐시
_database_instances = {}


class SQLiteDatabase:
    """SQLite 데이터베이스 연결 및 관리 클래스 (멀티테넌트 지원)"""
    
    def __init__(self, company_id: str, platform: str = "freshdesk"):
        """
        SQLite 데이터베이스 초기화 (멀티테넌트 지원)
        
        Args:
            company_id: 회사 ID (필수, 예: "wedosoft", "acme")
            platform: 플랫폼 이름 (기본값: "freshdesk")
                     {company_id}_{platform}_data.db 형식으로 회사별 데이터베이스 파일이 생성됩니다.
        """
        if not company_id:
            raise ValueError("company_id는 필수 매개변수입니다")
        if not platform:
            raise ValueError("platform은 필수 매개변수입니다")
        
        # 멀티테넌트: 회사별 데이터베이스 파일 분리
        db_name = f"{company_id}_{platform}_data.db"
        self.company_id = company_id
        self.platform = platform
        self.db_path = Path(__file__).parent.parent / "data" / db_name
        self.db_path.parent.mkdir(exist_ok=True)
        
        self.connection = None
        logger.info(f"SQLite 데이터베이스 초기화: {self.db_path} (회사: {company_id}, 플랫폼: {platform})")
    
    def connect(self):
        """데이터베이스 연결"""
        self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row  # dict 형태로 결과 반환
        logger.info(f"데이터베이스 연결 완료: {self.db_path}")
        
        # 연결 후 자동으로 테이블 생성
        self.create_tables()
    
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
        
        # 1. 티켓 테이블 (platform-neutral 3-tuple 기반)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY,
                original_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                subject TEXT,
                description TEXT,
                description_text TEXT, -- HTML 제거된 순수 텍스트 (검색/임베딩용)
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
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, platform, original_id)
            )
        """)
        
        # 2. 대화 테이블 (platform-neutral 3-tuple 기반)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                original_id TEXT NOT NULL,
                ticket_original_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT NOT NULL,
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
                UNIQUE(company_id, platform, original_id),
                FOREIGN KEY(company_id, platform, ticket_original_id) REFERENCES tickets(company_id, platform, original_id)
            )
        """)
        
        # 3. 지식베이스 문서 테이블 (platform-neutral 3-tuple 기반) - Freshdesk API 구조 반영
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY,
                original_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                title TEXT,
                description TEXT,
                description_text TEXT, -- HTML 제거된 순수 텍스트 (검색/임베딩용)
                status INTEGER, -- Freshdesk status는 숫자형
                type INTEGER, -- Freshdesk type은 숫자형 (1=permanent, 2=workaround)
                category_id INTEGER,
                folder_id INTEGER,
                agent_id INTEGER, -- 작성자 ID (author_id → agent_id)
                hierarchy TEXT, -- JSON 문자열로 저장 (카테고리/폴더 계층구조)
                thumbs_up INTEGER DEFAULT 0,
                thumbs_down INTEGER DEFAULT 0,
                hits INTEGER DEFAULT 0, -- 조회수 (검색 필터링 시 유용)
                tags TEXT, -- JSON 문자열
                seo_data TEXT, -- JSON 문자열 (SEO 메타데이터)
                created_at TEXT,
                updated_at TEXT,
                raw_data TEXT, -- 전체 원본 데이터 JSON
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, platform, original_id)
            )
        """)
        
        # 4. 첨부파일 테이블 (platform-neutral 3-tuple 기반)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY,
                original_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                parent_type TEXT, -- 'ticket', 'conversation', 'article'
                parent_original_id TEXT,
                name TEXT,
                content_type TEXT,
                size INTEGER,
                created_at TEXT,
                updated_at TEXT,
                attachment_url TEXT,
                raw_data TEXT, -- 전체 원본 데이터 JSON
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, platform, original_id)
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
        
        # 6. 통합 객체 테이블 (platform-neutral 3-tuple 기반)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrated_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                object_type TEXT NOT NULL, -- 'integrated_ticket', 'integrated_article'
                original_data TEXT NOT NULL, -- 원본 데이터 JSON
                integrated_content TEXT, -- 통합된 콘텐츠 (검색용)
                summary TEXT, -- LLM 요약
                metadata TEXT, -- 메타데이터 JSON
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, platform, object_type, original_id)
            )
        """)
        
        # 7. 진행상황 로그 테이블 (실시간 작업 진행상황 추적)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                message TEXT NOT NULL,
                percentage REAL NOT NULL,
                step INTEGER NOT NULL,
                total_steps INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, company_id, step)
            )
        """)
        
        # 인덱스 생성 (platform-neutral 3-tuple 기반)
        # Tickets 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_company_id ON tickets(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_original_id ON tickets(original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_company_platform ON tickets(company_id, platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)")
        
        # Conversations 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_company_id ON conversations(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_original_id ON conversations(original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_ticket_id ON conversations(ticket_original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_company_platform ON conversations(company_id, platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)")
        
        # Knowledge base 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_company_id ON " \
        "knowledge_base(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_original_id ON knowledge_base(original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_company_platform ON knowledge_base(company_id, platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_status ON knowledge_base(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_category_id ON knowledge_base(category_id)")
        
        # Attachments 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_company_id ON attachments(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_original_id ON attachments(original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_parent ON attachments(parent_type, parent_original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_company_platform ON attachments(company_id, platform)")
        
        # Collection logs 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_company_id ON collection_logs(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_job_id ON collection_logs(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_status ON collection_logs(status)")
        
        # Integrated objects 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_company_id ON integrated_objects(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_object_type ON integrated_objects(object_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_original_id ON integrated_objects(original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_company_platform ON integrated_objects(company_id, platform)")
        
        # Progress logs 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_job_id ON progress_logs(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_company_id ON progress_logs(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_created_at ON progress_logs(created_at)")
        
        self.connection.commit()
        logger.info("모든 테이블 생성 완료")
    
    def insert_ticket(self, ticket_data: Dict[str, Any]) -> int:
        """티켓 데이터 삽입 (platform-neutral 3-tuple 기반)"""
        # DB 연결 상태 확인 및 재연결
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 필수 필드 검증
        if not ticket_data.get('company_id'):
            raise ValueError("company_id는 필수입니다")
        if not ticket_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        logger.info(f"DB insert_ticket 호출됨: ticket_id={ticket_data.get('id')}, company_id={ticket_data.get('company_id')}")
        
        cursor.execute("""
            INSERT OR REPLACE INTO tickets (
                original_id, company_id, platform, subject, description, description_text,
                status, priority, type, source, requester_id, responder_id,
                group_id, created_at, updated_at, due_by, fr_due_by,
                is_escalated, tags, custom_fields, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(ticket_data.get('id')),  # original_id (문자열로 변환)
            ticket_data.get('company_id'),
            ticket_data.get('platform'),
            ticket_data.get('subject'),
            ticket_data.get('description'),
            ticket_data.get('description_text'),  # HTML 제거된 순수 텍스트
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
        logger.info(f"DB insert_ticket 완료: lastrowid={cursor.lastrowid}")
        return cursor.lastrowid
    
    def insert_conversation(self, conversation_data: Dict[str, Any]) -> int:
        """대화 데이터 삽입 (platform-neutral 3-tuple 기반)"""
        # DB 연결 상태 확인 및 재연결
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 필수 필드 검증
        if not conversation_data.get('company_id'):
            raise ValueError("company_id는 필수입니다")
        if not conversation_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        cursor.execute("""
            INSERT OR REPLACE INTO conversations (
                original_id, ticket_original_id, company_id, platform, user_id,
                body, body_text, incoming, private, source,
                created_at, updated_at, attachments, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(conversation_data.get('id')),  # original_id (문자열로 변환)
            str(conversation_data.get('ticket_id')),  # ticket_original_id (문자열로 변환)
            conversation_data.get('company_id'),
            conversation_data.get('platform'),
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
        """지식베이스 문서 삽입 (platform-neutral 3-tuple 기반) - Freshdesk API 구조 반영"""
        # DB 연결 상태 확인 및 재연결
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 필수 필드 검증
        if not article_data.get('company_id'):
            raise ValueError("company_id는 필수입니다")
        if not article_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        cursor.execute("""
            INSERT OR REPLACE INTO knowledge_base (
                original_id, company_id, platform, title, description, description_text,
                status, type, category_id, folder_id, agent_id, hierarchy,
                thumbs_up, thumbs_down, hits, tags, seo_data, 
                created_at, updated_at, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(article_data.get('id')),  # original_id (문자열로 변환)
            article_data.get('company_id'),
            article_data.get('platform'),
            article_data.get('title'),
            article_data.get('description'),
            article_data.get('description_text'),  # HTML 제거된 순수 텍스트
            article_data.get('status'),  # 숫자형
            article_data.get('type'),    # 숫자형
            article_data.get('category_id'),
            article_data.get('folder_id'),
            article_data.get('agent_id'),  # author_id → agent_id
            json.dumps(article_data.get('hierarchy', [])),  # 계층구조 JSON
            article_data.get('thumbs_up', 0),
            article_data.get('thumbs_down', 0),
            article_data.get('hits', 0),  # 조회수
            json.dumps(article_data.get('tags', [])),
            json.dumps(article_data.get('seo_data', {})),  # SEO 데이터
            article_data.get('created_at'),
            article_data.get('updated_at'),
            json.dumps(article_data)
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def insert_integrated_object(self, integrated_data: Dict[str, Any]) -> int:
        """통합 객체 데이터 삽입 (platform-neutral 3-tuple 기반)"""
        # DB 연결 상태 확인 및 재연결
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 필수 필드 검증
        if not integrated_data.get('company_id'):
            raise ValueError("company_id는 필수입니다")
        if not integrated_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        logger.info(f"DB insert_integrated_object 호출됨: original_id={integrated_data.get('original_id')}, company_id={integrated_data.get('company_id')}")
        
        cursor.execute("""
            INSERT OR REPLACE INTO integrated_objects (
                original_id, company_id, platform, object_type,
                original_data, integrated_content, summary, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(integrated_data.get('original_id')),  # original_id (문자열로 변환)
            integrated_data.get('company_id'),
            integrated_data.get('platform'),
            integrated_data.get('object_type'),
            json.dumps(integrated_data.get('original_data', {})),
            integrated_data.get('integrated_content'),
            integrated_data.get('summary'),
            json.dumps(integrated_data.get('metadata', {}))
        ))
        
        self.connection.commit()
        logger.info(f"DB insert_integrated_object 완료: lastrowid={cursor.lastrowid}")
        return cursor.lastrowid
    
    def insert_attachment(self, attachment_data: Dict[str, Any]) -> int:
        """첨부파일 데이터 삽입 (platform-neutral 3-tuple 기반)"""
        # DB 연결 상태 확인 및 재연결
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 필수 필드 검증
        if not attachment_data.get('company_id'):
            raise ValueError("company_id는 필수입니다")
        if not attachment_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        cursor.execute("""
            INSERT OR REPLACE INTO attachments (
                original_id, company_id, platform, parent_type, parent_original_id,
                name, content_type, size, attachment_url, 
                created_at, updated_at, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(attachment_data.get('id')),  # original_id (첨부파일 자체의 Freshdesk ID)
            attachment_data.get('company_id'),
            attachment_data.get('platform'),
            attachment_data.get('parent_type'),  # 'ticket', 'conversation', 'article'
            str(attachment_data.get('parent_original_id')),  # 부모 객체의 Freshdesk 원본 ID
            attachment_data.get('name'),
            attachment_data.get('content_type'),
            attachment_data.get('size'),
            attachment_data.get('attachment_url'),
            attachment_data.get('created_at'),
            attachment_data.get('updated_at'),
            json.dumps(attachment_data)
        ))
        
        self.connection.commit()
        return cursor.lastrowid

    def log_collection_job(self, job_data: Dict[str, Any]) -> int:
        """수집 작업 로그 저장
        
        Args:
            job_data: 작업 데이터 딕셔너리
                - job_id: 작업 ID
                - company_id: 회사 ID
                - platform: 플랫폼
                - job_type: 작업 타입
                - status: 상태 (started, completed, failed)
                - start_time: 시작 시간
                - end_time: 종료 시간 (선택사항)
                - tickets_collected: 수집된 티켓 수
                - conversations_collected: 수집된 대화 수
                - articles_collected: 수집된 문서 수
                - attachments_collected: 수집된 첨부파일 수
                - errors_count: 오류 수
                - error_message: 오류 메시지
                - config: 설정 정보
                
        Returns:
            int: 생성된 로그 ID
        """
        if not self.connection:
            self.connect()
            
        cursor = self.connection.cursor()
        
        # 기존 로그가 있는지 확인 (업데이트용)
        cursor.execute("""
            SELECT id FROM collection_logs 
            WHERE job_id = ? AND company_id = ?
        """, (job_data.get('job_id'), job_data.get('company_id')))
        
        existing_log = cursor.fetchone()
        
        if existing_log:
            # 기존 로그 업데이트
            cursor.execute("""
                UPDATE collection_logs SET
                    status = ?,
                    end_time = ?,
                    tickets_collected = ?,
                    conversations_collected = ?,
                    articles_collected = ?,
                    attachments_collected = ?,
                    errors_count = ?,
                    error_message = ?,
                    config_data = ?
                WHERE id = ?
            """, (
                job_data.get('status'),
                job_data.get('end_time'),
                job_data.get('tickets_collected', 0),
                job_data.get('conversations_collected', 0),
                job_data.get('articles_collected', 0),
                job_data.get('attachments_collected', 0),
                job_data.get('errors_count', 0),
                job_data.get('error_message'),
                json.dumps(job_data.get('config', {})),
                existing_log['id']
            ))
            log_id = existing_log['id']
        else:
            # 새 로그 삽입
            cursor.execute("""
                INSERT INTO collection_logs (
                    job_id, company_id, job_type, status, start_time, end_time,
                    tickets_collected, conversations_collected, articles_collected,
                    attachments_collected, errors_count, error_message, config_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_data.get('job_id'),
                job_data.get('company_id'),
                job_data.get('job_type', 'ingest'),
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
            log_id = cursor.lastrowid
        
        self.connection.commit()
        logger.info(f"수집 작업 로그 저장 완료: job_id={job_data.get('job_id')}, status={job_data.get('status')}")
        
        return log_id

    def log_progress(self, job_id: str, step: int, total_steps: int, message: str = "", 
                    company_id: str = None, percentage: float = None) -> int:
        """진행상황 로그 저장
        
        Args:
            job_id: 작업 ID
            step: 현재 단계
            total_steps: 전체 단계 수
            message: 메시지
            company_id: 회사 ID
            percentage: 진행률 (0-100)
            
        Returns:
            int: 생성된 로그 ID
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # percentage 계산 (제공되지 않은 경우)
        if percentage is None:
            percentage = (step / total_steps) * 100 if total_steps > 0 else 0
        
        cursor.execute("""
            INSERT OR REPLACE INTO progress_logs (
                job_id, company_id, message, percentage, step, total_steps
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            company_id or getattr(self, 'company_id', None),
            message,
            percentage,
            step,
            total_steps
        ))
        
        self.connection.commit()
        logger.info(f"진행상황 로그 저장: job_id={job_id}, step={step}/{total_steps}, message={message}")
        return cursor.lastrowid

    def get_tickets_by_company_and_platform(self, company_id: str, platform: str) -> List[Dict[str, Any]]:
        """회사 및 플랫폼별 티켓 조회
        
        Args:
            company_id: 회사 ID
            platform: 플랫폼명
            
        Returns:
            List[Dict[str, Any]]: 티켓 목록
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM tickets 
            WHERE company_id = ? AND platform = ?
            ORDER BY created_at DESC
        """, (company_id, platform))
        
        rows = cursor.fetchall()
        
        # Row 객체를 딕셔너리로 변환
        tickets = []
        for row in rows:
            ticket = dict(row)
            # JSON 필드 파싱
            if ticket.get('tags'):
                try:
                    ticket['tags'] = json.loads(ticket['tags'])
                except json.JSONDecodeError:
                    ticket['tags'] = []
            if ticket.get('custom_fields'):
                try:
                    ticket['custom_fields'] = json.loads(ticket['custom_fields'])
                except json.JSONDecodeError:
                    ticket['custom_fields'] = {}
            if ticket.get('raw_data'):
                try:
                    ticket['raw_data'] = json.loads(ticket['raw_data'])
                except json.JSONDecodeError:
                    ticket['raw_data'] = {}
            # original_id 필드 추가 (processor.py에서 필요)
            ticket['original_id'] = ticket.get('original_id')
            tickets.append(ticket)
        
        return tickets

    def get_articles_by_company_and_platform(self, company_id: str, platform: str) -> List[Dict[str, Any]]:
        """회사 및 플랫폼별 KB 문서 조회
        
        Args:
            company_id: 회사 ID
            platform: 플랫폼명
            
        Returns:
            List[Dict[str, Any]]: KB 문서 목록
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM knowledge_base 
            WHERE company_id = ? AND platform = ?
            ORDER BY created_at DESC
        """, (company_id, platform))
        
        rows = cursor.fetchall()
        
        # Row 객체를 딕셔너리로 변환
        articles = []
        for row in rows:
            article = dict(row)
            # JSON 필드 파싱
            if article.get('hierarchy'):
                try:
                    article['hierarchy'] = json.loads(article['hierarchy'])
                except json.JSONDecodeError:
                    article['hierarchy'] = []
            if article.get('tags'):
                try:
                    article['tags'] = json.loads(article['tags'])
                except json.JSONDecodeError:
                    article['tags'] = []
            if article.get('seo_data'):
                try:
                    article['seo_data'] = json.loads(article['seo_data'])
                except json.JSONDecodeError:
                    article['seo_data'] = {}
            if article.get('raw_data'):
                try:
                    article['raw_data'] = json.loads(article['raw_data'])
                except json.JSONDecodeError:
                    article['raw_data'] = {}
            # original_id 필드 추가 (processor.py에서 필요)
            article['original_id'] = article.get('original_id')
            articles.append(article)
        
        return articles

    def clear_all_data(self, company_id: str = None, platform: str = None):
        """모든 데이터 삭제 (force_rebuild용)
        
        Args:
            company_id: 회사 ID (선택사항, 지정시 해당 회사 데이터만 삭제)
            platform: 플랫폼명 (선택사항, 지정시 해당 플랫폼 데이터만 삭제)
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            self.create_tables()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 조건부 삭제
        if company_id and platform:
            # 특정 회사 및 플랫폼 데이터만 삭제
            tables = ['tickets', 'conversations', 'knowledge_base', 'attachments', 'integrated_objects']
            for table in tables:
                cursor.execute(f"DELETE FROM {table} WHERE company_id = ? AND platform = ?", 
                             (company_id, platform))
            logger.info(f"데이터 삭제 완료: company_id={company_id}, platform={platform}")
        elif company_id:
            # 특정 회사 데이터만 삭제  
            tables = ['tickets', 'conversations', 'knowledge_base', 'attachments', 'integrated_objects']
            for table in tables:
                cursor.execute(f"DELETE FROM {table} WHERE company_id = ?", (company_id,))
            logger.info(f"데이터 삭제 완료: company_id={company_id}")
        else:
            # 전체 데이터 삭제
            tables = ['tickets', 'conversations', 'knowledge_base', 'attachments', 'integrated_objects', 
                     'collection_logs', 'progress_logs']
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            logger.info("전체 데이터 삭제 완료")
        
        self.connection.commit()


def get_database(company_id: str, platform: str = "freshdesk") -> SQLiteDatabase:
    """멀티테넌트 데이터베이스 인스턴스 반환
    
    Args:
        company_id: 회사 ID (필수, 예: "wedosoft", "acme") 
        platform: 플랫폼 이름 (기본값: "freshdesk")
    
    Returns:
        SQLiteDatabase 인스턴스
    """
    if not company_id:
        raise ValueError("company_id는 필수 매개변수입니다")
    if not platform:
        raise ValueError("platform은 필수 매개변수입니다")
    
    # 멀티테넌트: 회사별 + 플랫폼별 키 생성
    db_key = f"{company_id}_{platform}"
    
    if db_key not in _database_instances:
        _database_instances[db_key] = SQLiteDatabase(company_id, platform)
    
    db = _database_instances[db_key]
    
    if not db.connection:
        db.connect()
        db.create_tables()
    
    return db
