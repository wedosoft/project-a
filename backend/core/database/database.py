"""
SQLite 데이터베이스 연결 및 모델 정의 (Freshdesk 전용)

Freshdesk 멀티테넌트 데이터 수집을 위한 SQLite 데이터베이스 구조를 정의합니다.
회사별로 별도 데이터베이스 파일이 생성됩니다 (예: company1_data.db, company2_data.db).
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

# 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv가 설치되지 않은 경우 무시

logger = logging.getLogger(__name__)

# 멀티테넌트 데이터베이스 인스턴스 캐시
_database_instances = {}


class SQLiteDatabase:
    """SQLite 데이터베이스 연결 및 관리 클래스 (멀티테넌트 지원)"""
    
    def __init__(self, tenant_id: str, platform: str = "freshdesk"):
        """
        SQLite 데이터베이스 초기화 (Freshdesk 전용 멀티테넌트)
        
        Args:
            tenant_id: 테넌트 ID (필수, 예: "wedosoft", "acme")
            platform: 플랫폼 이름 (기본값: "freshdesk", 현재는 Freshdesk만 지원)
                     {tenant_id}_data.db 형식으로 회사별 데이터베이스 파일이 생성됩니다.
        """
        if not tenant_id:
            raise ValueError("tenant_id는 필수 매개변수입니다")
        
        # Freshdesk 전용 플랫폼으로 고정 (점진적 단순화)
        if platform and platform != "freshdesk":
            logger.warning(f"현재는 Freshdesk만 지원됩니다. platform='{platform}' 무시하고 'freshdesk'로 설정")
        
        # 멀티테넌트: 회사별 데이터베이스 파일 분리 (Freshdesk 전용)
        db_name = f"{tenant_id}_data.db"
        self.tenant_id = tenant_id
        self.platform = "freshdesk"  # 항상 고정
        self.db_path = Path(__file__).parent.parent / "data" / db_name
        self.db_path.parent.mkdir(exist_ok=True)
        
        self.connection = None
        self._tables_created = False  # 테이블 생성 여부 추적
        logger.info(f"SQLite 데이터베이스 초기화: {self.db_path} (회사: {tenant_id}, 플랫폼: Freshdesk 전용)")
    
    @property
    def tenant_id(self) -> str:
        """호환성을 위한 tenant_id property (tenant_id와 동일)"""
        return self.tenant_id
    
    def connect(self):
        """데이터베이스 연결"""
        self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row  # dict 형태로 결과 반환
        logger.info(f"데이터베이스 연결 완료: {self.db_path}")
        
        # 테이블이 아직 생성되지 않았다면 생성
        if not self._tables_created:
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
        
        # =====================================================
        # 🏢 SaaS 라이선스 관리 테이블 (레거시 도메인 테이블 제거됨)
        # =====================================================

        # =====================================================
        # 🏢 SaaS 라이선스 관리 테이블 추가
        # =====================================================
        
        # 구독 플랜 정의 (SQLite 버전)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                base_seats INTEGER NOT NULL,
                base_monthly_cost REAL NOT NULL,
                additional_seat_cost REAL NOT NULL,
                max_seats INTEGER,
                max_tickets_per_month INTEGER,
                max_api_calls_per_day INTEGER,
                features TEXT NOT NULL, -- JSON 문자열
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 고객사 정보 (SQLite 버전)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
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
                monthly_cost REAL NOT NULL,
                current_month_tickets INTEGER DEFAULT 0,
                current_day_api_calls INTEGER DEFAULT 0,
                last_reset_month TEXT,
                last_reset_day TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                freshdesk_domain TEXT NOT NULL,
                FOREIGN KEY (subscription_plan_id) REFERENCES subscription_plans(id)
            )
        """)
        
        # 상담원 정보 (SQLite 버전)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                name TEXT NOT NULL,
                freshdesk_agent_id INTEGER,
                freshdesk_role TEXT,
                license_status TEXT DEFAULT 'inactive',
                seat_assigned BOOLEAN DEFAULT 0,
                assigned_by INTEGER,
                assigned_at TEXT,
                feature_overrides TEXT, -- JSON 문자열
                last_login_at TEXT,
                last_activity_at TEXT,
                monthly_tickets_processed INTEGER DEFAULT 0,
                monthly_ai_summaries_used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (tenant_id) REFERENCES companies(id),
                FOREIGN KEY (assigned_by) REFERENCES agents(id),
                UNIQUE(tenant_id, email),
                UNIQUE(tenant_id, freshdesk_agent_id)
            )
        """)
        
        # 사용량 추적 로그 (SQLite 버전)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                agent_id INTEGER,
                usage_type TEXT NOT NULL,
                usage_count INTEGER DEFAULT 1,
                resource_id TEXT,
                metadata TEXT, -- JSON 문자열
                usage_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES companies(id),
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        # 결제 이력 (SQLite 버전)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                billing_period_start TEXT NOT NULL,
                billing_period_end TEXT NOT NULL,
                base_amount REAL NOT NULL,
                additional_seats_count INTEGER DEFAULT 0,
                additional_seats_amount REAL DEFAULT 0,
                total_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                payment_method TEXT,
                transaction_id TEXT,
                plan_name TEXT NOT NULL,
                plan_features TEXT, -- JSON 문자열
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES companies(id)
            )
        """)
        
        # 시스템 설정 (SQLite 버전)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                is_encrypted BOOLEAN DEFAULT 0,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 회사별 개별 설정 (SQLite 버전) - 테넌트별 설정 관리
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                is_encrypted BOOLEAN DEFAULT 0,
                description TEXT,  -- 설정 설명 컬럼 추가
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES companies(id),
                UNIQUE(tenant_id, setting_key)
            )
        """)
        
        # =====================================================
        # 📊 SaaS 관련 인덱스 생성
        # =====================================================
        
        # 회사 관련 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_billing_status ON companies(billing_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_plan_id ON companies(subscription_plan_id)")
        
        # 상담원 관련 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_tenant_id ON agents(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_email ON agents(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_seat_assigned ON agents(seat_assigned)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_license_status ON agents(license_status)")
        
        # 사용량 관련 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_logs_tenant_id ON usage_logs(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_logs_agent_id ON usage_logs(agent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_logs_usage_date ON usage_logs(usage_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_logs_usage_type ON usage_logs(usage_type)")
        
        # =====================================================
        # 📊 기본 SaaS 데이터 입력
        # =====================================================
        
        # 기본 플랜 생성 (존재하지 않을 경우에만)
        cursor.execute("SELECT COUNT(*) FROM subscription_plans")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO subscription_plans (plan_name, display_name, base_seats, base_monthly_cost, additional_seat_cost, max_seats, features) VALUES
                ('starter', 'Starter Plan', 3, 29.00, 8.00, 10, '{"ai_summary": true, "basic_analytics": true, "export_limit": 50}'),
                ('professional', 'Professional Plan', 10, 99.00, 6.00, 50, '{"ai_summary": true, "advanced_analytics": true, "custom_fields": true, "export_limit": 500}'),
                ('enterprise', 'Enterprise Plan', 25, 299.00, 5.00, null, '{"ai_summary": true, "advanced_analytics": true, "custom_fields": true, "api_access": true, "export_limit": null}')
            """)
            logger.info("기본 구독 플랜 생성 완료")
        
        # 기본 시스템 설정 (존재하지 않을 경우에만)
        # 🔐 보안정책: API 키, 도메인 등 민감한 정보는 절대 DB 저장 금지
        # 💡 인프라 관련 설정만 저장 (벡터DB URL, LLM 모델명 등)
        cursor.execute("SELECT COUNT(*) FROM system_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value, is_encrypted, description) VALUES
                ('qdrant_url', 'http://localhost:6333', 0, 'Qdrant vector database URL'),
                ('qdrant_collection_name', 'saas_tickets', 0, 'Default Qdrant collection name'),
                ('default_llm_model', 'gpt-4o-mini', 0, 'Default LLM model for AI features'),
                ('openai_base_url', 'https://api.openai.com/v1', 0, 'OpenAI API base URL'),
                ('max_attachment_size_mb', '10', 0, 'Maximum attachment size in MB'),
                ('session_timeout_hours', '24', 0, 'User session timeout in hours'),
                ('max_tokens_per_request', '4000', 0, 'Maximum tokens per LLM request'),
                ('chunk_size', '1000', 0, 'Default text chunk size for vectorization'),
                ('chunk_overlap', '200', 0, 'Default chunk overlap for vectorization')
            """)
            logger.info("기본 시스템 설정 생성 완료 (인프라 설정만)")

        # =====================================================
        # 📊 통합 데이터 테이블 (UNIFIED SCHEMA)
        # =====================================================
        
        # 통합 객체 테이블 - 모든 도메인 데이터를 저장
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrated_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                object_type TEXT NOT NULL, -- 'ticket', 'conversation', 'article', 'attachment'
                original_data TEXT NOT NULL, -- 원본 데이터 JSON
                integrated_content TEXT, -- 통합된 콘텐츠 (검색용)
                summary TEXT, -- LLM 요약
                metadata TEXT, -- 메타데이터 JSON (parent_id, status, dates 등)
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tenant_id, platform, object_type, original_id)
            )
        """)
        
        # 진행상황 로그 테이블 (실시간 작업 진행상황 추적)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                message TEXT NOT NULL,
                percentage REAL NOT NULL,
                step INTEGER NOT NULL,
                total_steps INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, tenant_id, step)
            )
        """)
        
        # =====================================================
        # 📊 통합 스키마 인덱스 생성 (레거시 테이블 인덱스 제거됨)
        # =====================================================
        
        # Integrated objects 테이블 인덱스 (모든 도메인 데이터용)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_tenant_id ON integrated_objects(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_object_type ON integrated_objects(object_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_original_id ON integrated_objects(original_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_company_platform ON integrated_objects(tenant_id, platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_company_type ON integrated_objects(tenant_id, object_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_content_search ON integrated_objects(integrated_content)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_created_at ON integrated_objects(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrated_updated_at ON integrated_objects(updated_at)")
        
        # Progress logs 테이블 인덱스
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_job_id ON progress_logs(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_tenant_id ON progress_logs(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_created_at ON progress_logs(created_at)")
        
        self.connection.commit()
        logger.info("모든 테이블 생성 완료")
        self._tables_created = True  # 테이블 생성 완료 표시
    
    def insert_ticket(self, ticket_data: Dict[str, Any]) -> int:
        """티켓 데이터 삽입 - integrated_objects 테이블 사용"""
        # 티켓 데이터를 통합 형태로 변환
        integrated_data = {
            'original_id': str(ticket_data.get('id')),
            'tenant_id': ticket_data.get('tenant_id'),
            'platform': ticket_data.get('platform'),
            'object_type': 'ticket',
            'original_data': ticket_data,
            'integrated_content': ticket_data.get('description_text') or ticket_data.get('description'),
            'summary': ticket_data.get('subject'),
            'metadata': {
                'status': ticket_data.get('status'),
                'priority': ticket_data.get('priority'),
                'type': ticket_data.get('type'),
                'source': ticket_data.get('source'),
                'requester_id': ticket_data.get('requester_id'),
                'responder_id': ticket_data.get('responder_id'),
                'group_id': ticket_data.get('group_id'),
                'tags': ticket_data.get('tags', []),
                'custom_fields': ticket_data.get('custom_fields', {}),
                'created_at': ticket_data.get('created_at'),
                'updated_at': ticket_data.get('updated_at'),
                'due_by': ticket_data.get('due_by'),
                'fr_due_by': ticket_data.get('fr_due_by'),
                'is_escalated': ticket_data.get('is_escalated')
            }
        }
        logger.info(f"DB insert_ticket 호출됨: ticket_id={ticket_data.get('id')}, tenant_id={ticket_data.get('tenant_id')}")
        result = self.insert_integrated_object(integrated_data)
        logger.info(f"DB insert_ticket 완료: lastrowid={result}")
        return result
    
    def insert_conversation(self, conversation_data: Dict[str, Any]) -> int:
        """대화 데이터 삽입 - integrated_objects 테이블 사용"""
        # 대화 데이터를 통합 형태로 변환
        integrated_data = {
            'original_id': str(conversation_data.get('id')),
            'tenant_id': conversation_data.get('tenant_id'),
            'platform': conversation_data.get('platform'),
            'object_type': 'conversation',
            'original_data': conversation_data,
            'integrated_content': conversation_data.get('body_text') or conversation_data.get('body'),
            'summary': f"Conversation {conversation_data.get('id')} for ticket {conversation_data.get('ticket_id')}",
            'metadata': {
                'ticket_original_id': str(conversation_data.get('ticket_id')),
                'user_id': conversation_data.get('user_id'),
                'incoming': conversation_data.get('incoming'),
                'private': conversation_data.get('private'),
                'source': conversation_data.get('source'),
                'attachments': conversation_data.get('attachments', []),
                'created_at': conversation_data.get('created_at'),
                'updated_at': conversation_data.get('updated_at')
            }
        }
        return self.insert_integrated_object(integrated_data)
    
    def insert_article(self, article_data: Dict[str, Any]) -> int:
        """지식베이스 문서 삽입 - integrated_objects 테이블 사용"""
        # 문서 데이터를 통합 형태로 변환
        integrated_data = {
            'original_id': str(article_data.get('id')),
            'tenant_id': article_data.get('tenant_id'),
            'platform': article_data.get('platform'),
            'object_type': 'article',
            'original_data': article_data,
            'integrated_content': article_data.get('description_text') or article_data.get('description'),
            'summary': article_data.get('title'),
            'metadata': {
                'status': article_data.get('status'),
                'type': article_data.get('type'),
                'category_id': article_data.get('category_id'),
                'folder_id': article_data.get('folder_id'),
                'agent_id': article_data.get('agent_id'),
                'hierarchy': article_data.get('hierarchy', []),
                'thumbs_up': article_data.get('thumbs_up', 0),
                'thumbs_down': article_data.get('thumbs_down', 0),
                'hits': article_data.get('hits', 0),
                'tags': article_data.get('tags', []),
                'seo_data': article_data.get('seo_data', {}),
                'created_at': article_data.get('created_at'),
                'updated_at': article_data.get('updated_at')
            }
        }
        return self.insert_integrated_object(integrated_data)
    
    def insert_integrated_object(self, integrated_data: Dict[str, Any]) -> int:
        """통합 객체 데이터 삽입 (platform-neutral 3-tuple 기반)"""
        # DB 연결 상태 확인 및 재연결
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            # self.create_tables() # 이미 connect()에서 처리됨
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 필수 필드 검증
        if not integrated_data.get('tenant_id'):
            raise ValueError("tenant_id는 필수입니다")
        if not integrated_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        cursor.execute("""
            INSERT OR REPLACE INTO integrated_objects (
                original_id, tenant_id, platform, object_type,
                original_data, integrated_content, summary, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(integrated_data.get('original_id')),  # original_id (문자열로 변환)
            integrated_data.get('tenant_id'),
            integrated_data.get('platform'),
            integrated_data.get('object_type'),
            json.dumps(integrated_data.get('original_data', {})),
            integrated_data.get('integrated_content'),
            integrated_data.get('summary'),
            json.dumps(integrated_data.get('metadata', {}))
        ))
        
        self.connection.commit()
        return cursor.lastrowid
    
    def insert_attachment(self, attachment_data: Dict[str, Any]) -> int:
        """첨부파일 데이터 삽입 - integrated_objects 테이블 사용
        
        Args:
            attachment_data: 첨부파일 데이터 딕셔너리
                - original_id: 첨부파일 원본 ID
                - tenant_id: 테넌트 ID
                - platform: 플랫폼
                - parent_type: 부모 타입 ('ticket', 'conversation', 'article')
                - parent_original_id: 부모 객체 원본 ID
                - name: 파일명
                - content_type: 콘텐츠 타입
                - size: 파일 크기
                - attachment_url: 첨부파일 URL
                - created_at: 생성일시
                - updated_at: 수정일시
                - raw_data: 원본 데이터
                
        Returns:
            int: 생성된 레코드 ID
        """
        # 첨부파일 데이터를 통합 형태로 변환
        integrated_data = {
            'original_id': str(attachment_data.get('original_id')),
            'tenant_id': attachment_data.get('tenant_id'),
            'platform': attachment_data.get('platform'),
            'object_type': 'attachment',
            'original_data': attachment_data,
            'integrated_content': f"File: {attachment_data.get('name')}",
            'summary': f"Attachment: {attachment_data.get('name')} ({attachment_data.get('content_type')})",
            'metadata': {
                'parent_type': attachment_data.get('parent_type'),
                'parent_original_id': attachment_data.get('parent_original_id'),
                'name': attachment_data.get('name'),
                'content_type': attachment_data.get('content_type'),
                'size': attachment_data.get('size'),
                'attachment_url': attachment_data.get('attachment_url'),
                'created_at': attachment_data.get('created_at'),
                'updated_at': attachment_data.get('updated_at')
            }
        }
        result = self.insert_integrated_object(integrated_data)
        logger.debug(f"첨부파일 저장 완료: {attachment_data.get('name')} (ID: {attachment_data.get('original_id')})")
        return result

    def log_collection_job(self, job_data: Dict[str, Any]) -> int:
        """수집 작업 로그 저장 - 레거시 메서드, 현재는 로그만 출력
        
        Args:
            job_data: 작업 데이터 딕셔너리
                
        Returns:
            int: 0 (더미 값)
        """
        logger.info(f"수집 작업 로그: job_id={job_data.get('job_id')}, "
                   f"status={job_data.get('status')}, "
                   f"tickets={job_data.get('tickets_collected', 0)}, "
                   f"conversations={job_data.get('conversations_collected', 0)}, "
                   f"articles={job_data.get('articles_collected', 0)}, "
                   f"attachments={job_data.get('attachments_collected', 0)}")
        return 0

    def log_progress(self, job_id: str, step: int, total_steps: int, message: str = "", 
                    tenant_id: str = None, percentage: float = None) -> int:
        """진행상황 로그 저장
        
        Args:
            job_id: 작업 ID
            step: 현재 단계
            total_steps: 전체 단계 수
            message: 메시지
            tenant_id: 테넌트 ID
            percentage: 진행률 (0-100)
            
        Returns:
            int: 생성된 로그 ID
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            # self.create_tables() # 이미 connect()에서 처리됨
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # percentage 계산 (제공되지 않은 경우)
        if percentage is None:
            percentage = (step / total_steps) * 100 if total_steps > 0 else 0
        
        cursor.execute("""
            INSERT OR REPLACE INTO progress_logs (
                job_id, tenant_id, message, percentage, step, total_steps
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            tenant_id or getattr(self, 'tenant_id', None),
            message,
            percentage,
            step,
            total_steps
        ))
        
        self.connection.commit()
        logger.info(f"진행상황 로그 저장: job_id={job_id}, step={step}/{total_steps}, message={message}")
        return cursor.lastrowid

    def get_tickets_by_company_and_platform(self, tenant_id: str, platform: str) -> List[Dict[str, Any]]:
        """회사 및 플랫폼별 티켓 조회 - integrated_objects 테이블 사용
        
        Args:
            tenant_id: 테넌트 ID
            platform: 플랫폼명
            
        Returns:
            List[Dict[str, Any]]: 티켓 목록
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM integrated_objects 
            WHERE tenant_id = ? AND platform = ? AND object_type = 'ticket'
            ORDER BY json_extract(metadata, '$.created_at') DESC
        """, (tenant_id, platform))
        
        rows = cursor.fetchall()
        
        # Row 객체를 딕셔너리로 변환
        tickets = []
        for row in rows:
            ticket_obj = dict(row)
            
            # 메타데이터와 원본 데이터 파싱
            metadata = json.loads(ticket_obj.get('metadata', '{}'))
            original_data = json.loads(ticket_obj.get('original_data', '{}'))
            
            # 기존 ticket 형태로 변환 (ID 타입 안전 처리)
            original_id = ticket_obj.get('original_id')
            try:
                # 숫자 ID인 경우 정수로 변환, 아니면 문자열 그대로 사용
                parsed_id = int(original_id) if original_id.isdigit() else original_id
            except (ValueError, AttributeError):
                parsed_id = original_id
            
            ticket = {
                'id': parsed_id,
                'original_id': ticket_obj.get('original_id'),
                'tenant_id': ticket_obj.get('tenant_id'),
                'platform': ticket_obj.get('platform'),
                'subject': ticket_obj.get('summary'),
                'description': original_data.get('description'),
                'description_text': ticket_obj.get('integrated_content'),
                'status': metadata.get('status'),
                'priority': metadata.get('priority'),
                'type': metadata.get('type'),
                'source': metadata.get('source'),
                'requester_id': metadata.get('requester_id'),
                'responder_id': metadata.get('responder_id'),
                'group_id': metadata.get('group_id'),
                'tags': metadata.get('tags', []),
                'custom_fields': metadata.get('custom_fields', {}),
                'created_at': metadata.get('created_at'),
                'updated_at': metadata.get('updated_at'),
                'due_by': metadata.get('due_by'),
                'fr_due_by': metadata.get('fr_due_by'),
                'is_escalated': metadata.get('is_escalated'),
                'raw_data': original_data
            }
            tickets.append(ticket)
        
        return tickets

    def get_articles_by_company_and_platform(self, tenant_id: str, platform: str) -> List[Dict[str, Any]]:
        """회사 및 플랫폼별 KB 문서 조회 - integrated_objects 테이블 사용
        
        Args:
            tenant_id: 테넌트 ID
            platform: 플랫폼명
            
        Returns:
            List[Dict[str, Any]]: KB 문서 목록
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM integrated_objects 
            WHERE tenant_id = ? AND platform = ? AND object_type = 'article'
            ORDER BY json_extract(metadata, '$.created_at') DESC
        """, (tenant_id, platform))
        
        rows = cursor.fetchall()
        
        # Row 객체를 딕셔너리로 변환
        articles = []
        for row in rows:
            article_obj = dict(row)
            
            # 메타데이터와 원본 데이터 파싱
            metadata = json.loads(article_obj.get('metadata', '{}'))
            original_data = json.loads(article_obj.get('original_data', '{}'))
            
            # 기존 article 형태로 변환 (ID 타입 안전 처리)
            original_id = article_obj.get('original_id')
            try:
                # 숫자 ID인 경우 정수로 변환, 아니면 문자열 그대로 사용
                parsed_id = int(original_id) if original_id.isdigit() else original_id
            except (ValueError, AttributeError):
                parsed_id = original_id
            
            article = {
                'id': parsed_id,
                'original_id': article_obj.get('original_id'),
                'tenant_id': article_obj.get('tenant_id'),
                'platform': article_obj.get('platform'),
                'title': article_obj.get('summary'),
                'description': original_data.get('description'),
                'description_text': article_obj.get('integrated_content'),
                'status': metadata.get('status'),
                'type': metadata.get('type'),
                'category_id': metadata.get('category_id'),
                'folder_id': metadata.get('folder_id'),
                'agent_id': metadata.get('agent_id'),
                'hierarchy': metadata.get('hierarchy', []),
                'thumbs_up': metadata.get('thumbs_up', 0),
                'thumbs_down': metadata.get('thumbs_down', 0),
                'hits': metadata.get('hits', 0),
                'tags': metadata.get('tags', []),
                'seo_data': metadata.get('seo_data', {}),
                'created_at': metadata.get('created_at'),
                'updated_at': metadata.get('updated_at'),
                'raw_data': original_data
            }
            articles.append(article)
        
        return articles

    def get_attachments_by_ticket(self, ticket_original_id: str) -> List[Dict[str, Any]]:
        """티켓의 첨부파일 조회 - integrated_objects 테이블 사용
        
        Args:
            ticket_original_id: 티켓 원본 ID
            
        Returns:
            List[Dict[str, Any]]: 첨부파일 데이터 리스트
        """
        if not self.connection:
            self.connect()
            
        cursor = self.connection.cursor()
        
        # 티켓과 관련된 모든 첨부파일 조회 (티켓 직접 첨부 + 대화 첨부파일)
        # 먼저 해당 티켓의 대화들을 찾기
        conversation_ids_query = """
            SELECT original_id FROM integrated_objects 
            WHERE tenant_id = ? AND platform = ? AND object_type = 'conversation'
            AND json_extract(metadata, '$.ticket_original_id') = ?
        """
        
        cursor.execute(conversation_ids_query, (self.tenant_id, self.platform, ticket_original_id))
        conversation_ids = [row[0] for row in cursor.fetchall()]
        
        # 첨부파일 조회 - 티켓 직접 첨부 또는 대화 첨부
        placeholders = ','.join(['?'] * len(conversation_ids)) if conversation_ids else "''"
        
        query = f"""
            SELECT * FROM integrated_objects 
            WHERE tenant_id = ? AND platform = ? AND object_type = 'attachment'
            AND (
                json_extract(metadata, '$.parent_type') = 'ticket' 
                AND json_extract(metadata, '$.parent_original_id') = ?
                OR (
                    json_extract(metadata, '$.parent_type') = 'conversation'
                    AND json_extract(metadata, '$.parent_original_id') IN ({placeholders})
                )
            )
            ORDER BY json_extract(metadata, '$.created_at')
        """
        
        params = [self.tenant_id, self.platform, ticket_original_id] + conversation_ids
        cursor.execute(query, params)
        
        rows = cursor.fetchall()
        attachments = []
        
        for row in rows:
            attachment_obj = dict(row)
            metadata = json.loads(attachment_obj.get('metadata', '{}'))
            
            # 기존 형태로 변환
            attachment = {
                'attachment_id': attachment_obj.get('original_id'),
                'name': metadata.get('name'),
                'content_type': metadata.get('content_type'),
                'size': metadata.get('size'),
                'download_url': metadata.get('attachment_url'),
                'parent_type': metadata.get('parent_type'),
                'conversation_id': metadata.get('parent_original_id') if metadata.get('parent_type') == 'conversation' else None,
                'created_at': metadata.get('created_at'),
                'raw_data': attachment_obj.get('original_data')
            }
            attachments.append(attachment)
        
        logger.debug(f"티켓 {ticket_original_id}의 첨부파일 조회 완료: {len(attachments)}개")
        return attachments

    def clear_all_data(self, tenant_id: str = None, platform: str = None):
        """모든 데이터 삭제 (force_rebuild용) - integrated_objects 테이블 사용
        
        Args:
            tenant_id: 테넌트 ID (선택사항, 지정시 해당 회사 데이터만 삭제)
            platform: 플랫폼명 (선택사항, 지정시 해당 플랫폼 데이터만 삭제)
        """
        if not self.connection:
            logger.warning("DB 연결이 끊어짐. 재연결 시도...")
            self.connect()
            logger.info("DB 재연결 완료")
        
        cursor = self.connection.cursor()
        
        # 조건부 삭제 - 이제 integrated_objects와 progress_logs만 삭제
        if tenant_id and platform:
            # 특정 회사 및 플랫폼 데이터만 삭제
            cursor.execute("DELETE FROM integrated_objects WHERE tenant_id = ? AND platform = ?", 
                         (tenant_id, platform))
            logger.info(f"데이터 삭제 완료: tenant_id={tenant_id}, platform={platform}")
        elif tenant_id:
            # 특정 회사 데이터만 삭제  
            cursor.execute("DELETE FROM integrated_objects WHERE tenant_id = ?", (tenant_id,))
            cursor.execute("DELETE FROM progress_logs WHERE tenant_id = ?", (tenant_id,))
            logger.info(f"데이터 삭제 완료: tenant_id={tenant_id}")
        else:
            # 전체 데이터 삭제 - 도메인 데이터만 삭제 (SaaS 테이블은 유지)
            cursor.execute("DELETE FROM integrated_objects")
            cursor.execute("DELETE FROM progress_logs")
            logger.info("전체 도메인 데이터 삭제 완료")
        
        self.connection.commit()

    # =====================================================
    # 🏢 SaaS 라이선스 관리 메서드들
    # =====================================================
    
    def insert_company(self, company_data: Dict[str, Any]) -> int:
        """회사 정보 등록"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO companies (
                company_name, domain, contact_email, subscription_plan_id,
                purchased_seats, used_seats, billing_status, subscription_start,
                subscription_end, next_billing_date, monthly_cost,
                current_month_tickets, current_day_api_calls,
                last_reset_month, last_reset_day, freshdesk_domain
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_data.get('company_name'),
            company_data.get('domain'),
            company_data.get('contact_email'),
            company_data.get('subscription_plan_id'),
            company_data.get('purchased_seats', 0),
            company_data.get('used_seats', 0),
            company_data.get('billing_status', 'active'),
            company_data.get('subscription_start'),
            company_data.get('subscription_end'),
            company_data.get('next_billing_date'),
            company_data.get('monthly_cost', 0.0),
            company_data.get('current_month_tickets', 0),
            company_data.get('current_day_api_calls', 0),
            company_data.get('last_reset_month'),
            company_data.get('last_reset_day'),
            company_data.get('freshdesk_domain')
        ))
        
        self.connection.commit()
        tenant_id = cursor.lastrowid
        logger.info(f"회사 정보 저장 완료: ID={tenant_id}, domain={company_data.get('domain')}")
        return tenant_id
    
    def get_company_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """도메인으로 회사 정보 조회"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM companies WHERE domain = ?", (domain,))
        row = cursor.fetchone()
        
        return dict(row) if row else None
    
    def insert_agent(self, agent_data: Dict[str, Any]) -> int:
        """상담원 정보 등록"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO agents (
                tenant_id, email, name, freshdesk_agent_id, freshdesk_role,
                license_status, seat_assigned, assigned_by, assigned_at,
                feature_overrides, last_login_at, last_activity_at,
                monthly_tickets_processed, monthly_ai_summaries_used, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_data.get('tenant_id'),
            agent_data.get('email'),
            agent_data.get('name'),
            agent_data.get('freshdesk_agent_id'),
            agent_data.get('freshdesk_role'),
            agent_data.get('license_status', 'inactive'),
            agent_data.get('seat_assigned', False),
            agent_data.get('assigned_by'),
            agent_data.get('assigned_at'),
            agent_data.get('feature_overrides'),
            agent_data.get('last_login_at'),
            agent_data.get('last_activity_at'),
            agent_data.get('monthly_tickets_processed', 0),
            agent_data.get('monthly_ai_summaries_used', 0),
            agent_data.get('is_active', True)
        ))
        
        self.connection.commit()
        agent_id = cursor.lastrowid
        logger.info(f"상담원 정보 저장 완료: ID={agent_id}, email={agent_data.get('email')}")
        return agent_id
    
    def get_agents_by_company(self, tenant_id: int) -> List[Dict[str, Any]]:
        """회사별 상담원 목록 조회"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM agents 
            WHERE tenant_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (tenant_id,))
        
        rows = cursor.fetchall()
        agents = []
        for row in rows:
            agent = dict(row)
            # JSON 필드 파싱
            if agent.get('feature_overrides'):
                try:
                    agent['feature_overrides'] = json.loads(agent['feature_overrides'])
                except json.JSONDecodeError:
                    agent['feature_overrides'] = {}
            agents.append(agent)
        
        return agents
    
    def log_usage(self, usage_data: Dict[str, Any]) -> int:
        """사용량 로그 기록"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT INTO usage_logs (
                tenant_id, agent_id, usage_type, usage_count,
                resource_id, metadata, usage_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            usage_data.get('tenant_id'),
            usage_data.get('agent_id'),
            usage_data.get('usage_type'),
            usage_data.get('usage_count', 1),
            usage_data.get('resource_id'),
            json.dumps(usage_data.get('metadata', {})),
            usage_data.get('usage_date', datetime.now().strftime('%Y-%m-%d'))
        ))
        
        self.connection.commit()
        usage_id = cursor.lastrowid
        logger.info(f"사용량 로그 기록: ID={usage_id}, type={usage_data.get('usage_type')}")
        return usage_id
    
    def get_usage_summary(self, tenant_id: int, usage_type: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """사용량 요약 조회"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        query = """
            SELECT usage_type, usage_date, SUM(usage_count) as total_usage
            FROM usage_logs 
            WHERE tenant_id = ? 
            AND usage_date >= date('now', '-{} days')
        """.format(days)
        
        params = [tenant_id]
        
        if usage_type:
            query += " AND usage_type = ?"
            params.append(usage_type)
        
        query += " GROUP BY usage_type, usage_date ORDER BY usage_date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def update_seat_usage(self, tenant_id: int, used_seats: int) -> bool:
        """시트 사용량 업데이트"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        cursor.execute("""
            UPDATE companies 
            SET used_seats = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (used_seats, tenant_id))
        
        self.connection.commit()
        
        if cursor.rowcount > 0:
            logger.info(f"회사 시트 사용량 업데이트: tenant_id={tenant_id}, used_seats={used_seats}")
            return True
        else:
            logger.warning(f"회사 시트 사용량 업데이트 실패: tenant_id={tenant_id}")
            return False
    
    def get_subscription_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """구독 플랜 정보 조회"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM subscription_plans WHERE id = ? AND is_active = 1", (plan_id,))
        row = cursor.fetchone()
        
        if row:
            plan = dict(row)
            # JSON 필드 파싱
            if plan.get('features'):
                try:
                    plan['features'] = json.loads(plan['features'])
                except json.JSONDecodeError:
                    plan['features'] = {}
            return plan
        
        return None
    
    def insert_billing_record(self, billing_data: Dict[str, Any]) -> int:
        """결제 기록 생성"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        cursor.execute("""
            INSERT INTO billing_history (
                tenant_id, billing_period_start, billing_period_end,
                base_amount, additional_seats_count, additional_seats_amount,
                total_amount, status, payment_method, transaction_id,
                plan_name, plan_features
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            billing_data.get('tenant_id'),
            billing_data.get('billing_period_start'),
            billing_data.get('billing_period_end'),
            billing_data.get('base_amount'),
            billing_data.get('additional_seats_count', 0),
            billing_data.get('additional_seats_amount', 0.0),
            billing_data.get('total_amount'),
            billing_data.get('status', 'pending'),
            billing_data.get('payment_method'),
            billing_data.get('transaction_id'),
            billing_data.get('plan_name'),
            json.dumps(billing_data.get('plan_features', {}))
        ))
        
        self.connection.commit()
        billing_id = cursor.lastrowid
        logger.info(f"결제 기록 생성: ID={billing_id}, tenant_id={billing_data.get('tenant_id')}")
        return billing_id
    
    def count_integrated_objects(self) -> int:
        """통합 객체 총 개수 반환"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM integrated_objects")
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"통합 객체 개수 조회 오류: {e}")
            return 0
        finally:
            self.disconnect()
    
    def count_integrated_objects_by_type(self, object_type: str) -> int:
        """특정 타입의 통합 객체 개수 반환"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM integrated_objects WHERE object_type = ?",
                (object_type,)
            )
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"{object_type} 타입 객체 개수 조회 오류: {e}")
            return 0
        finally:
            self.disconnect()
    
    def get_integrated_objects_statistics(self) -> Dict[str, Any]:
        """통합 객체 통계 정보 반환"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            
            # 전체 개수
            cursor.execute("SELECT COUNT(*) FROM integrated_objects")
            total_count = cursor.fetchone()[0]
            
            # 타입별 개수
            cursor.execute("""
                SELECT object_type, COUNT(*) as count 
                FROM integrated_objects 
                GROUP BY object_type
            """)
            type_counts = dict(cursor.fetchall())
            
            # 최근 생성된 객체들
            cursor.execute("""
                SELECT object_type, MAX(created_at) as latest_created
                FROM integrated_objects 
                GROUP BY object_type
            """)
            latest_by_type = dict(cursor.fetchall())
            
            return {
                'total_count': total_count,
                'type_counts': type_counts,
                'latest_by_type': latest_by_type,
                'tenant_id': self.tenant_id,
                'platform': self.platform
            }
            
        except Exception as e:
            logger.error(f"통합 객체 통계 조회 오류: {e}")
            return {
                'total_count': 0,
                'type_counts': {},
                'latest_by_type': {},
                'tenant_id': self.tenant_id,
                'platform': self.platform
            }
        finally:
            self.disconnect()

    # 호환성을 위한 alias
DatabaseManager = SQLiteDatabase

def get_database(tenant_id: str = None, platform: str = "freshdesk") -> SQLiteDatabase:
    """
    데이터베이스 인스턴스 반환 (Freshdesk 전용 멀티테넌트)
    
    Args:
        tenant_id: 테넌트 ID (테넌트 ID)
        platform: 플랫폼 이름 (현재는 Freshdesk만 지원, 다른 값은 무시됨)
    
    Returns:
        SQLiteDatabase 인스턴스 (항상 Freshdesk 전용)
    """
    if not tenant_id:
        raise ValueError("멀티테넌트 환경에서는 tenant_id(tenant_id)가 필수입니다")
    
    return SQLiteDatabase(tenant_id, platform)  # platform은 내부적으로 "freshdesk"로 고정됨


def validate_multitenant_setup() -> Dict[str, Any]:
    """멀티테넌트 설정 검증"""
    validation = {
        'database_type': os.getenv('DATABASE_TYPE', 'sqlite'),
        'isolation_method': 'file-based' if os.getenv('DATABASE_TYPE', 'sqlite') == 'sqlite' else 'schema-based',
        'environment_vars': {},
        'recommendations': [],
        'is_production_ready': False
    }
    
    # 환경변수 확인
    required_vars = ['DATABASE_TYPE']
    if validation['database_type'] == 'postgresql':
        required_vars.extend(['POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD'])
    
    for var in required_vars:
        validation['environment_vars'][var] = os.getenv(var, 'NOT_SET')
        if validation['environment_vars'][var] == 'NOT_SET':
            validation['recommendations'].append(f"환경변수 {var} 설정 필요")
    
    # PostgreSQL의 경우 추가 검증
    if validation['database_type'] == 'postgresql':
        try:
            import psycopg2
            validation['postgresql_driver'] = 'Available'
            validation['is_production_ready'] = len(validation['recommendations']) == 0
        except ImportError:
            validation['postgresql_driver'] = 'Not Available'
            validation['recommendations'].append("psycopg2 드라이버 설치 필요")
    else:
        validation['is_production_ready'] = True  # SQLite는 기본적으로 사용 가능
    
    return validation
