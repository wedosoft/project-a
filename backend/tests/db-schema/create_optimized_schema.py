#!/usr/bin/env python3
"""
최적화된 데이터베이스 스키마 생성

100만건 이상의 대량 데이터 처리를 위한 최적화된 스키마 설계
- 정규화를 통한 중복 제거
- 효율적인 인덱싱
- 압축 및 최적화
- 대용량 처리를 위한 파티셔닝 준비
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


class OptimizedSchemaCreator:
    """최적화된 스키마 생성기"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def create_optimized_schema(self):
        """최적화된 스키마 생성"""
        
        logger.info(f"최적화된 데이터베이스 스키마 생성: {self.db_path}")
        
        # 기존 데이터베이스 백업
        if os.path.exists(self.db_path):
            logger.info(f"기존 데이터베이스 백업: {self.backup_path}")
            shutil.copy2(self.db_path, self.backup_path)
        
        # 새 데이터베이스 생성
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 기존 뷰 제거
            cursor.execute("DROP VIEW IF EXISTS v_ticket_details")
            cursor.execute("DROP VIEW IF EXISTS v_ticket_summary")
            cursor.execute("DROP VIEW IF EXISTS v_conversation_summary")
            cursor.execute("DROP VIEW IF EXISTS v_processing_stats")
            
            # 기존 테이블 제거 (새로 시작)
            cursor.execute("DROP TABLE IF EXISTS integrated_objects")
            cursor.execute("DROP TABLE IF EXISTS tickets")
            cursor.execute("DROP TABLE IF EXISTS conversations")
            cursor.execute("DROP TABLE IF EXISTS attachments")
            cursor.execute("DROP TABLE IF EXISTS companies")
            cursor.execute("DROP TABLE IF EXISTS agents")
            cursor.execute("DROP TABLE IF EXISTS summaries")
            cursor.execute("DROP TABLE IF EXISTS categories")
            cursor.execute("DROP TABLE IF EXISTS processing_logs")
            
            # 1. 회사 정보 테이블 (정규화)
            self._create_companies_table(cursor)
            
            # 2. 상담원 정보 테이블
            self._create_agents_table(cursor)
            
            # 3. 카테고리 테이블
            self._create_categories_table(cursor)
            
            # 4. 티켓 메인 테이블 (최적화)
            self._create_tickets_table(cursor)
            
            # 5. 대화 테이블 (정규화)
            self._create_conversations_table(cursor)
            
            # 6. 첨부파일 테이블
            self._create_attachments_table(cursor)
            
            # 7. 요약 테이블 (별도 관리)
            self._create_summaries_table(cursor)
            
            # 8. 처리 로그 테이블
            self._create_processing_logs_table(cursor)
            
            # 9. 인덱스 생성
            self._create_optimized_indexes(cursor)
            
            # 10. 트리거 생성 (자동 업데이트)
            self._create_triggers(cursor)
            
            # 11. 뷰 생성 (편의성)
            self._create_views(cursor)
            
            conn.commit()
            logger.info("✅ 최적화된 스키마 생성 완료")
            
            # 스키마 정보 출력
            self._print_schema_info(cursor)
            
        except Exception as e:
            logger.error(f"❌ 스키마 생성 실패: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _create_companies_table(self, cursor):
        """회사 정보 테이블"""
        cursor.execute("""
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            freshdesk_domain TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            api_key_hash TEXT,
            settings_json TEXT,  -- 압축된 JSON 설정
            timezone TEXT DEFAULT 'UTC',
            language TEXT DEFAULT 'ko',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.info("✓ companies 테이블 생성")
    
    def _create_agents_table(self, cursor):
        """상담원 정보 테이블"""
        cursor.execute("""
        CREATE TABLE agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            freshdesk_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT,
            department TEXT,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            UNIQUE(company_id, freshdesk_id)
        )
        """)
        logger.info("✓ agents 테이블 생성")
    
    def _create_categories_table(self, cursor):
        """카테고리 테이블"""
        cursor.execute("""
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            freshdesk_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            parent_id INTEGER,
            level INTEGER DEFAULT 0,
            path TEXT,  -- 계층 경로 (예: "1/5/12")
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (parent_id) REFERENCES categories(id),
            UNIQUE(company_id, freshdesk_id)
        )
        """)
        logger.info("✓ categories 테이블 생성")
    
    def _create_tickets_table(self, cursor):
        """티켓 메인 테이블 (최적화)"""
        cursor.execute("""
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            freshdesk_id INTEGER NOT NULL,
            
            -- 기본 정보
            subject TEXT NOT NULL,
            description_text TEXT,  -- HTML 제거된 순수 텍스트
            description_html TEXT,  -- 원본 HTML (압축 저장)
            
            -- 분류 정보
            status_id INTEGER NOT NULL,
            priority_id INTEGER NOT NULL,
            category_id INTEGER,
            sub_category_id INTEGER,
            type_id INTEGER,
            source_id INTEGER,
            
            -- 담당자 정보
            requester_id INTEGER,
            agent_id INTEGER,
            group_id INTEGER,
            
            -- 메타데이터 (정규화)
            due_by TIMESTAMP,
            fr_due_by TIMESTAMP,
            is_escalated BOOLEAN DEFAULT 0,
            spam BOOLEAN DEFAULT 0,
            
            -- 태그 (JSON 배열로 압축)
            tags_json TEXT,
            
            -- 커스텀 필드 (JSON으로 압축)
            custom_fields_json TEXT,
            
            -- 시간 정보
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            resolved_at TIMESTAMP,
            closed_at TIMESTAMP,
            
            -- 통계 정보 (비정규화 - 성능 최적화)
            conversation_count INTEGER DEFAULT 0,
            attachment_count INTEGER DEFAULT 0,
            resolution_time_hours INTEGER,
            first_response_time_hours INTEGER,
            
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (category_id) REFERENCES categories(id),
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            UNIQUE(company_id, freshdesk_id)
        )
        """)
        logger.info("✓ tickets 테이블 생성")
    
    def _create_conversations_table(self, cursor):
        """대화 테이블 (정규화)"""
        cursor.execute("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            freshdesk_id INTEGER NOT NULL,
            
            -- 메시지 내용
            body_text TEXT NOT NULL,  -- HTML 제거된 순수 텍스트
            body_html TEXT,           -- 원본 HTML (필요시)
            
            -- 발신자 정보
            user_id INTEGER,
            from_email TEXT,
            
            -- 메시지 유형
            incoming BOOLEAN NOT NULL,
            private BOOLEAN DEFAULT 0,
            source_id INTEGER,
            
            -- 시간 정보
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            
            -- 첨부파일 개수 (성능 최적화)
            attachment_count INTEGER DEFAULT 0,
            
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
            UNIQUE(ticket_id, freshdesk_id)
        )
        """)
        logger.info("✓ conversations 테이블 생성")
    
    def _create_attachments_table(self, cursor):
        """첨부파일 테이블"""
        cursor.execute("""
        CREATE TABLE attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            freshdesk_id INTEGER NOT NULL,
            
            -- 파일 정보
            name TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER,
            
            -- 다운로드 정보
            attachment_url TEXT,
            download_url TEXT,
            
            -- 처리 상태
            downloaded BOOLEAN DEFAULT 0,
            local_path TEXT,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            UNIQUE(conversation_id, freshdesk_id)
        )
        """)
        logger.info("✓ attachments 테이블 생성")
    
    def _create_summaries_table(self, cursor):
        """요약 테이블 (별도 관리)"""
        cursor.execute("""
        CREATE TABLE summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            
            -- 요약 내용
            summary_text TEXT NOT NULL,
            summary_type TEXT DEFAULT 'ticket',  -- 'ticket', 'conversation', 'custom'
            
            -- 품질 관리
            quality_score REAL NOT NULL DEFAULT 0.0,
            structure_score REAL DEFAULT 0.0,
            completion_score REAL DEFAULT 0.0,
            language_score REAL DEFAULT 0.0,
            
            -- 생성 정보
            model_used TEXT,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            processing_time_ms INTEGER DEFAULT 0,
            cost_estimate REAL DEFAULT 0.0,
            
            -- 메타데이터
            ui_language TEXT DEFAULT 'ko',
            content_language TEXT DEFAULT 'ko',
            retry_count INTEGER DEFAULT 0,
            
            -- 시간 정보
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- 버전 관리
            version INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            
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
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            
            -- 처리 유형
            process_type TEXT NOT NULL,  -- 'summary', 'sync', 'cleanup', etc.
            status TEXT NOT NULL,        -- 'pending', 'processing', 'completed', 'failed'
            
            -- 처리 결과
            result_message TEXT,
            error_message TEXT,
            
            -- 성능 메트릭
            processing_time_ms INTEGER,
            memory_usage_mb REAL,
            
            -- 배치 정보
            batch_id TEXT,
            batch_size INTEGER,
            
            -- 시간 정보
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            
            -- 재시도 정보
            attempt_count INTEGER DEFAULT 1,
            max_attempts INTEGER DEFAULT 3
        )
        """)
        logger.info("✓ processing_logs 테이블 생성")
    
    def _create_optimized_indexes(self, cursor):
        """최적화된 인덱스 생성"""
        
        indexes = [
            # 티켓 테이블 인덱스
            "CREATE INDEX idx_tickets_company_freshdesk ON tickets(company_id, freshdesk_id)",
            "CREATE INDEX idx_tickets_status_priority ON tickets(status_id, priority_id)",
            "CREATE INDEX idx_tickets_created_at ON tickets(created_at)",
            "CREATE INDEX idx_tickets_updated_at ON tickets(updated_at)",
            "CREATE INDEX idx_tickets_agent ON tickets(agent_id)",
            "CREATE INDEX idx_tickets_category ON tickets(category_id)",
            
            # 대화 테이블 인덱스
            "CREATE INDEX idx_conversations_ticket ON conversations(ticket_id)",
            "CREATE INDEX idx_conversations_created_at ON conversations(created_at)",
            "CREATE INDEX idx_conversations_incoming ON conversations(incoming)",
            
            # 첨부파일 테이블 인덱스
            "CREATE INDEX idx_attachments_conversation ON attachments(conversation_id)",
            "CREATE INDEX idx_attachments_downloaded ON attachments(downloaded)",
            
            # 요약 테이블 인덱스
            "CREATE INDEX idx_summaries_ticket ON summaries(ticket_id)",
            "CREATE INDEX idx_summaries_quality ON summaries(quality_score)",
            "CREATE INDEX idx_summaries_active ON summaries(is_active, version)",
            "CREATE INDEX idx_summaries_created_at ON summaries(created_at)",
            
            # 처리 로그 인덱스
            "CREATE INDEX idx_processing_logs_table_record ON processing_logs(table_name, record_id)",
            "CREATE INDEX idx_processing_logs_status ON processing_logs(status)",
            "CREATE INDEX idx_processing_logs_batch ON processing_logs(batch_id)",
            "CREATE INDEX idx_processing_logs_started_at ON processing_logs(started_at)",
            
            # 복합 인덱스 (성능 최적화)
            "CREATE INDEX idx_tickets_company_status_created ON tickets(company_id, status_id, created_at)",
            "CREATE INDEX idx_summaries_ticket_active_quality ON summaries(ticket_id, is_active, quality_score)",
            "CREATE INDEX idx_conversations_ticket_created ON conversations(ticket_id, created_at)",
        ]
        
        for idx in indexes:
            cursor.execute(idx)
            
        logger.info(f"✓ {len(indexes)}개 인덱스 생성 완료")
    
    def _create_triggers(self, cursor):
        """자동 업데이트 트리거 생성"""
        
        # 티켓 업데이트 시 자동으로 updated_at 갱신
        cursor.execute("""
        CREATE TRIGGER update_tickets_timestamp 
        AFTER UPDATE ON tickets
        BEGIN
            UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
        """)
        
        # 대화 추가/삭제 시 티켓의 대화 수 자동 업데이트
        cursor.execute("""
        CREATE TRIGGER update_conversation_count_insert
        AFTER INSERT ON conversations
        BEGIN
            UPDATE tickets 
            SET conversation_count = (
                SELECT COUNT(*) FROM conversations WHERE ticket_id = NEW.ticket_id
            )
            WHERE id = NEW.ticket_id;
        END
        """)
        
        cursor.execute("""
        CREATE TRIGGER update_conversation_count_delete
        AFTER DELETE ON conversations
        BEGIN
            UPDATE tickets 
            SET conversation_count = (
                SELECT COUNT(*) FROM conversations WHERE ticket_id = OLD.ticket_id
            )
            WHERE id = OLD.ticket_id;
        END
        """)
        
        # 요약 업데이트 시 자동으로 updated_at 갱신
        cursor.execute("""
        CREATE TRIGGER update_summaries_timestamp 
        AFTER UPDATE ON summaries
        BEGIN
            UPDATE summaries SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
        """)
        
        logger.info("✓ 트리거 생성 완료")
    
    def _create_views(self, cursor):
        """편의성을 위한 뷰 생성"""
        
        logger.info("뷰 생성 중...")
        
        # 기존 뷰들 삭제
        view_names = [
            'v_ticket_details',
            'v_ticket_summary', 
            'v_processing_stats',
            'v_agent_workload',
            'v_quality_metrics'
        ]
        
        for view_name in view_names:
            try:
                cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
                logger.debug(f"기존 뷰 삭제: {view_name}")
            except Exception as e:
                logger.warning(f"뷰 삭제 실패 (무시됨): {view_name} - {e}")
        
        # 티켓 상세 뷰 (JOIN 최적화)
        cursor.execute("""
        CREATE VIEW v_ticket_details AS
        SELECT 
            t.id,
            t.freshdesk_id,
            t.subject,
            t.description_text,
            t.status_id,
            t.priority_id,
            t.created_at,
            t.updated_at,
            c.company_name,
            a.name as agent_name,
            a.email as agent_email,
            cat.name as category_name,
            t.conversation_count,
            t.attachment_count,
            s.summary_text,
            s.quality_score,
            s.created_at as summary_created_at
        FROM tickets t
        LEFT JOIN companies c ON t.company_id = c.id
        LEFT JOIN agents a ON t.agent_id = a.id
        LEFT JOIN categories cat ON t.category_id = cat.id
        LEFT JOIN summaries s ON t.id = s.ticket_id AND s.is_active = 1
        """)
        
        # 처리 대기 티켓 뷰
        cursor.execute("""
        CREATE VIEW v_pending_summaries AS
        SELECT 
            t.id as ticket_id,
            t.freshdesk_id,
            t.subject,
            t.created_at,
            t.conversation_count,
            c.company_name
        FROM tickets t
        LEFT JOIN companies c ON t.company_id = c.id
        LEFT JOIN summaries s ON t.id = s.ticket_id AND s.is_active = 1
        WHERE s.id IS NULL
        AND t.conversation_count > 0
        ORDER BY t.created_at DESC
        """)
        
        # 품질 통계 뷰
        cursor.execute("""
        CREATE VIEW v_quality_stats AS
        SELECT 
            DATE(s.created_at) as summary_date,
            COUNT(*) as total_summaries,
            AVG(s.quality_score) as avg_quality,
            COUNT(CASE WHEN s.quality_score >= 0.9 THEN 1 END) as high_quality_count,
            SUM(s.tokens_input + s.tokens_output) as total_tokens,
            SUM(s.cost_estimate) as total_cost
        FROM summaries s
        WHERE s.is_active = 1
        GROUP BY DATE(s.created_at)
        ORDER BY summary_date DESC
        """)
        
        logger.info("✓ 뷰 생성 완료")
    
    def _print_schema_info(self, cursor):
        """스키마 정보 출력"""
        
        print("\n" + "="*50)
        print("🗄️  최적화된 데이터베이스 스키마")
        print("="*50)
        
        # 테이블 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📋 테이블 ({len(tables)}개):")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  • {table}: {count:,}개 레코드")
        
        # 인덱스 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"\n🔍 인덱스 ({len(indexes)}개):")
        for idx in indexes[:10]:  # 처음 10개만 표시
            print(f"  • {idx}")
        if len(indexes) > 10:
            print(f"  ... 및 {len(indexes)-10}개 더")
        
        # 뷰 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
        views = [row[0] for row in cursor.fetchall()]
        print(f"\n👁️  뷰 ({len(views)}개):")
        for view in views:
            print(f"  • {view}")
        
        # 트리거 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name")
        triggers = [row[0] for row in cursor.fetchall()]
        print(f"\n⚡ 트리거 ({len(triggers)}개):")
        for trigger in triggers:
            print(f"  • {trigger}")
        
        print("\n" + "="*50)
        print("✅ 스키마 최적화 완료")
        print("="*50)


def main():
    """메인 함수"""
    
    db_path = "core/data/wedosoft_freshdesk_data_optimized.db"
    
    print("🚀 최적화된 데이터베이스 스키마 생성")
    print(f"📁 대상 경로: {db_path}")
    
    # 디렉토리 생성
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # 스키마 생성
    creator = OptimizedSchemaCreator(db_path)
    creator.create_optimized_schema()
    
    print(f"\n🎉 최적화된 데이터베이스가 준비되었습니다!")
    print(f"📍 경로: {os.path.abspath(db_path)}")
    
    # 다음 단계 안내
    print(f"\n📝 다음 단계:")
    print(f"1. 데이터 수집: python collect_freshdesk_data.py")
    print(f"2. 대량 요약 처리: python large_scale_summarization.py")
    print(f"3. 모니터링: python summarization_monitor.py")


if __name__ == "__main__":
    main()
