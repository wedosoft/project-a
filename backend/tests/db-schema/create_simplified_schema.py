#!/usr/bin/env python3
"""
단순화된 최적화 스키마 생성

현실적인 데이터 규모에 맞춘 단순하고 효율적인 스키마
- 과도한 정규화 제거
- 실제 데이터에 맞춘 최적화
- 유지보수성 향상
"""

import sqlite3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimplifiedSchemaCreator:
    """단순화된 스키마 생성기"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def create_simplified_schema(self):
        """단순화된 스키마 생성"""
        
        logger.info(f"단순화된 최적화 스키마 생성: {self.db_path}")
        
        # 기존 데이터베이스 백업
        if os.path.exists(self.db_path):
            logger.info(f"기존 데이터베이스 백업: {self.backup_path}")
            shutil.copy2(self.db_path, self.backup_path)
        
        # 새 데이터베이스 생성
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 기존 테이블/뷰 모두 제거
            self._drop_all_objects(cursor)
            
            # 1. 티켓 메인 테이블 (단순화)
            self._create_tickets_table(cursor)
            
            # 2. 대화 테이블
            self._create_conversations_table(cursor)
            
            # 3. 첨부파일 테이블
            self._create_attachments_table(cursor)
            
            # 4. 요약 테이블 (핵심)
            self._create_summaries_table(cursor)
            
            # 5. 처리 로그 테이블
            self._create_processing_logs_table(cursor)
            
            # 6. 효율적인 인덱스
            self._create_optimized_indexes(cursor)
            
            # 7. 편의 뷰
            self._create_views(cursor)
            
            conn.commit()
            logger.info("✅ 단순화된 스키마 생성 완료")
            
            # 스키마 정보 출력
            self._print_schema_info(cursor)
            
        except Exception as e:
            logger.error(f"❌ 스키마 생성 실패: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _drop_all_objects(self, cursor):
        """모든 기존 객체 삭제"""
        
        # 뷰 삭제
        cursor.execute("DROP VIEW IF EXISTS v_ticket_details")
        cursor.execute("DROP VIEW IF EXISTS v_ticket_summary")
        cursor.execute("DROP VIEW IF EXISTS v_conversation_summary")
        cursor.execute("DROP VIEW IF EXISTS v_processing_stats")
        
        # 테이블 삭제
        tables = [
            "integrated_objects", "tickets", "conversations", "attachments",
            "companies", "agents", "summaries", "categories", "processing_logs"
        ]
        
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
        logger.info("✓ 기존 객체 모두 삭제")
    
    def _create_tickets_table(self, cursor):
        """티켓 메인 테이블 (단순화)"""
        cursor.execute("""
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Freshdesk 정보
            freshdesk_id INTEGER UNIQUE NOT NULL,
            company_domain TEXT DEFAULT 'wedosoft',  -- 현재는 단일 회사
            
            -- 기본 정보
            subject TEXT NOT NULL,
            description_text TEXT,
            description_html TEXT,
            
            -- 상태 정보 (정수 ID 대신 텍스트)
            status TEXT NOT NULL DEFAULT 'Open',
            priority TEXT NOT NULL DEFAULT 'Medium',
            ticket_type TEXT,
            source TEXT,
            
            -- 담당자 정보 (정규화 없이 직접 저장)
            requester_email TEXT,
            requester_name TEXT,
            agent_email TEXT,
            agent_name TEXT,
            
            -- 분류 (단순화)
            category TEXT,
            subcategory TEXT,
            tags_json TEXT,  -- JSON 배열로 저장
            
            -- 메타데이터
            due_by TIMESTAMP,
            is_escalated BOOLEAN DEFAULT 0,
            spam BOOLEAN DEFAULT 0,
            
            -- 커스텀 필드 (JSON으로 압축)
            custom_fields_json TEXT,
            
            -- 통계 (비정규화로 성능 최적화)
            conversation_count INTEGER DEFAULT 0,
            attachment_count INTEGER DEFAULT 0,
            
            -- 시간 정보
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            
            -- 처리 상태
            processed_for_summary BOOLEAN DEFAULT 0,
            last_processed_at TIMESTAMP
        )
        """)
        logger.info("✓ tickets 테이블 생성 (단순화)")
    
    def _create_conversations_table(self, cursor):
        """대화 테이블"""
        cursor.execute("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            freshdesk_id INTEGER,
            
            -- 내용
            body_text TEXT NOT NULL,
            body_html TEXT,
            
            -- 발신자 정보
            from_email TEXT,
            from_name TEXT,
            to_emails_json TEXT,  -- JSON 배열
            cc_emails_json TEXT,  -- JSON 배열
            
            -- 메타데이터
            incoming BOOLEAN DEFAULT 1,
            private BOOLEAN DEFAULT 0,
            
            -- 첨부파일 정보 (비정규화)
            has_attachments BOOLEAN DEFAULT 0,
            attachment_count INTEGER DEFAULT 0,
            
            -- 시간 정보
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
        """)
        logger.info("✓ conversations 테이블 생성")
    
    def _create_attachments_table(self, cursor):
        """첨부파일 테이블"""
        cursor.execute("""
        CREATE TABLE attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            conversation_id INTEGER,
            freshdesk_id INTEGER,
            
            -- 파일 정보
            name TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER,
            
            -- 텍스트 추출 (검색용)
            extracted_text TEXT,
            extraction_status TEXT DEFAULT 'pending',  -- pending, success, failed
            
            -- URL 정보
            attachment_url TEXT,
            
            -- 시간 정보
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
        )
        """)
        logger.info("✓ attachments 테이블 생성")
    
    def _create_summaries_table(self, cursor):
        """요약 테이블 (핵심)"""
        cursor.execute("""
        CREATE TABLE summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER UNIQUE NOT NULL,
            
            -- 요약 내용
            summary_text TEXT NOT NULL,
            summary_html TEXT,
            
            -- 품질 관리
            quality_score REAL NOT NULL DEFAULT 0.0,
            quality_details_json TEXT,  -- 상세 품질 점수들
            
            -- 처리 정보
            model_used TEXT NOT NULL DEFAULT 'gpt-4o',
            processing_time_ms INTEGER,
            token_usage_json TEXT,  -- {input: N, output: N}
            cost_estimate REAL DEFAULT 0.0,
            
            -- 메타데이터
            content_length INTEGER,  -- 원본 내용 길이
            summary_length INTEGER,  -- 요약 길이
            compression_ratio REAL,  -- 압축 비율
            
            -- 재처리 정보
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            
            -- 시간 정보
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
        """)
        logger.info("✓ summaries 테이블 생성")
    
    def _create_processing_logs_table(self, cursor):
        """처리 로그 테이블"""
        cursor.execute("""
        CREATE TABLE processing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- 처리 대상
            ticket_id INTEGER,
            batch_id TEXT,
            
            -- 로그 정보
            log_level TEXT NOT NULL DEFAULT 'INFO',  -- DEBUG, INFO, WARNING, ERROR
            message TEXT NOT NULL,
            details_json TEXT,  -- 상세 정보 JSON
            
            -- 성능 정보
            processing_time_ms INTEGER,
            memory_usage_mb REAL,
            
            -- 시간 정보
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE SET NULL
        )
        """)
        logger.info("✓ processing_logs 테이블 생성")
    
    def _create_optimized_indexes(self, cursor):
        """최적화된 인덱스 생성"""
        
        indexes = [
            # tickets 테이블
            "CREATE INDEX idx_tickets_freshdesk_id ON tickets(freshdesk_id)",
            "CREATE INDEX idx_tickets_status ON tickets(status)",
            "CREATE INDEX idx_tickets_created_at ON tickets(created_at)",
            "CREATE INDEX idx_tickets_processed ON tickets(processed_for_summary)",
            "CREATE INDEX idx_tickets_agent_email ON tickets(agent_email)",
            
            # conversations 테이블
            "CREATE INDEX idx_conversations_ticket_id ON conversations(ticket_id)",
            "CREATE INDEX idx_conversations_created_at ON conversations(created_at)",
            "CREATE INDEX idx_conversations_from_email ON conversations(from_email)",
            
            # attachments 테이블
            "CREATE INDEX idx_attachments_ticket_id ON attachments(ticket_id)",
            "CREATE INDEX idx_attachments_conversation_id ON attachments(conversation_id)",
            "CREATE INDEX idx_attachments_extraction_status ON attachments(extraction_status)",
            
            # summaries 테이블
            "CREATE INDEX idx_summaries_ticket_id ON summaries(ticket_id)",
            "CREATE INDEX idx_summaries_quality_score ON summaries(quality_score)",
            "CREATE INDEX idx_summaries_created_at ON summaries(created_at)",
            "CREATE INDEX idx_summaries_model_used ON summaries(model_used)",
            
            # processing_logs 테이블
            "CREATE INDEX idx_logs_ticket_id ON processing_logs(ticket_id)",
            "CREATE INDEX idx_logs_batch_id ON processing_logs(batch_id)",
            "CREATE INDEX idx_logs_created_at ON processing_logs(created_at)",
            "CREATE INDEX idx_logs_level ON processing_logs(log_level)",
        ]
        
        for idx_sql in indexes:
            cursor.execute(idx_sql)
        
        logger.info(f"✓ {len(indexes)}개 인덱스 생성 완료")
    
    def _create_views(self, cursor):
        """편의 뷰 생성"""
        
        # 티켓 상세 뷰
        cursor.execute("""
        CREATE VIEW v_ticket_details AS
        SELECT 
            t.id,
            t.freshdesk_id,
            t.subject,
            t.description_text,
            t.status,
            t.priority,
            t.requester_name,
            t.requester_email,
            t.agent_name,
            t.agent_email,
            t.category,
            t.conversation_count,
            t.attachment_count,
            t.created_at,
            t.updated_at,
            s.summary_text,
            s.quality_score,
            s.cost_estimate,
            s.created_at as summary_created_at,
            CASE 
                WHEN s.id IS NOT NULL THEN 1 
                ELSE 0 
            END as has_summary
        FROM tickets t
        LEFT JOIN summaries s ON t.id = s.ticket_id
        """)
        
        # 요약 통계 뷰
        cursor.execute("""
        CREATE VIEW v_summary_stats AS
        SELECT 
            COUNT(*) as total_summaries,
            AVG(quality_score) as avg_quality,
            SUM(cost_estimate) as total_cost,
            COUNT(CASE WHEN quality_score >= 0.9 THEN 1 END) as high_quality_count,
            AVG(processing_time_ms) as avg_processing_time,
            AVG(compression_ratio) as avg_compression_ratio,
            DATE(created_at) as date
        FROM summaries
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        """)
        
        logger.info("✓ 편의 뷰 생성 완료")
    
    def _print_schema_info(self, cursor):
        """스키마 정보 출력"""
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
        indexes = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
        views = [row[0] for row in cursor.fetchall()]
        
        print("\n" + "="*60)
        print("📊 단순화된 최적화 스키마 정보")
        print("="*60)
        print(f"📋 테이블: {len(tables)}개")
        for table in tables:
            print(f"   ✓ {table}")
            
        print(f"\n🔍 인덱스: {len(indexes)}개")
        for idx in indexes:
            print(f"   ✓ {idx}")
            
        print(f"\n👁️ 뷰: {len(views)}개")
        for view in views:
            print(f"   ✓ {view}")
        
        print("\n💡 주요 개선사항:")
        print("   • 과도한 정규화 제거 (companies, categories 테이블 삭제)")
        print("   • 실제 데이터에 맞춘 단순한 구조")
        print("   • 필수 정보만 별도 테이블로 분리")
        print("   • 검색/집계 최적화 인덱스")
        print("   • 요약 품질 관리 강화")
        print("   • 운영 모니터링 로그 시스템")
        
        print("="*60)


def main():
    """메인 함수"""
    
    print("🚀 단순화된 최적화 데이터베이스 스키마 생성")
    print("📁 대상 경로: core/data/wedosoft_freshdesk_data_simplified.db")
    
    # 디렉토리 생성
    db_dir = Path("core/data")
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # 스키마 생성
    db_path = "core/data/wedosoft_freshdesk_data_simplified.db"
    creator = SimplifiedSchemaCreator(db_path)
    creator.create_simplified_schema()
    
    print("\n✨ 단순화된 스키마 생성 완료!")
    print("이제 기존 데이터를 새 스키마로 마이그레이션할 준비가 되었습니다.")


if __name__ == "__main__":
    main()
