"""
SQLite 데이터베이스 연결 및 모델 정의 (Freshdesk 전용)

Freshdesk 멀티테넌트 데이터 수집을 위한 SQLite 데이터베이스 구조를 정의합니다.
회사별로 별도 데이터베이스 파일이 생성됩니다 (예: company1_data.db, company2_data.db).

이 파일은 SQLAlchemy ORM을 사용하여 데이터베이스 스키마를 관리합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

# SQLAlchemy imports
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import Engine

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
    """SQLAlchemy ORM 기반 SQLite 데이터베이스 연결 및 관리 클래스 (멀티테넌트 지원)"""
    
    def __init__(self, tenant_id: str, platform: str = "freshdesk"):
        """
        SQLAlchemy ORM 기반 SQLite 데이터베이스 초기화 (Freshdesk 전용 멀티테넌트)
        
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
        self._tenant_id = tenant_id  # 내부 저장용 변수명 변경
        self.platform = "freshdesk"  # 항상 고정
        self.db_path = Path(__file__).parent.parent / "data" / db_name
        self.db_path.parent.mkdir(exist_ok=True)
        
        # SQLAlchemy 엔진 및 세션 설정
        self.database_url = f"sqlite:///{self.db_path}"
        self.engine: Optional[Engine] = None
        self.SessionLocal = None
        self._tables_created = False  # 테이블 생성 여부 추적
        
        logger.info(f"SQLite 데이터베이스 초기화: {self.db_path} (회사: {tenant_id}, 플랫폼: Freshdesk 전용)")
    
    @property
    def tenant_id(self) -> str:
        """호환성을 위한 tenant_id property"""
        return self._tenant_id
    
    @tenant_id.setter
    def tenant_id(self, value: str) -> None:
        """tenant_id setter for compatibility"""
        self._tenant_id = value
    
    def connect(self):
        """SQLAlchemy 엔진 및 세션 생성"""
        if self.engine is None:
            self.engine = create_engine(
                self.database_url,
                echo=False,  # SQL 로깅 (디버그시 True로 변경)
                connect_args={"check_same_thread": False}  # SQLite 멀티스레딩 지원
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            logger.info(f"SQLAlchemy 엔진 생성 완료: {self.database_url}")
        
        # 테이블이 아직 생성되지 않았다면 ORM을 사용하여 생성
        if not self._tables_created:
            self.create_tables()
    
    def disconnect(self):
        """SQLAlchemy 엔진 해제"""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.SessionLocal = None
            logger.info("SQLAlchemy 엔진 해제")
    
    def create_tables(self):
        """SQLAlchemy ORM을 사용하여 테이블 생성"""
        if self.engine is None:
            self.connect()
        
        try:
            # ORM 모델들을 import
            from .models import Base
            
            # ORM을 사용하여 모든 테이블 생성
            Base.metadata.create_all(bind=self.engine)
            self._tables_created = True
            logger.info("SQLAlchemy ORM을 사용하여 모든 테이블 생성 완료")
            
        except Exception as e:
            logger.error(f"테이블 생성 중 오류 발생: {e}")
            raise
    
    def get_session(self):
        """새로운 데이터베이스 세션 반환"""
        if self.SessionLocal is None:
            self.connect()
        return self.SessionLocal()
    
    @property 
    def connection(self):
        """레거시 호환성을 위한 connection property (더 이상 사용하지 않음)"""
        logger.warning("connection property는 더 이상 사용되지 않습니다. get_session()을 사용하세요.")
        return None
    
    
    # 레거시 메서드들 (호환성을 위해 유지하지만 ORM 세션을 사용하도록 수정)
    def insert_ticket(self, ticket_data: Dict[str, Any]) -> int:
        """티켓 데이터 삽입 - ORM 기반으로 변경 필요"""
        logger.warning("insert_ticket 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return self.insert_integrated_object(ticket_data)
    
    def insert_conversation(self, conversation_data: Dict[str, Any]) -> int:
        """대화 데이터 삽입 - ORM 기반으로 변경 필요"""
        logger.warning("insert_conversation 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return self.insert_integrated_object(conversation_data)
    
    def insert_article(self, article_data: Dict[str, Any]) -> int:
        """지식베이스 문서 삽입 - ORM 기반으로 변경 필요"""
        logger.warning("insert_article 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return self.insert_integrated_object(article_data)
    
    def insert_integrated_object(self, integrated_data: Dict[str, Any]) -> int:
        """통합 객체 데이터 삽입 - ORM 기반으로 변경 필요"""
        logger.warning("insert_integrated_object 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        
        # ORM 세션 사용
        session = self.get_session()
        try:
            from .models import IntegratedObject
            
            # 통합 객체 생성
            obj = IntegratedObject(
                original_id=integrated_data.get('original_id'),
                tenant_id=integrated_data.get('tenant_id', self.tenant_id),
                platform=integrated_data.get('platform', self.platform),
                object_type=integrated_data.get('object_type'),
                original_data=integrated_data.get('original_data'),
                integrated_content=integrated_data.get('integrated_content'),
                summary=integrated_data.get('summary'),
                tenant_metadata=integrated_data.get('tenant_metadata')
            )
            
            session.add(obj)
            session.commit()
            object_id = obj.id
            return object_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"통합 객체 삽입 중 오류: {e}")
            raise
        finally:
            session.close()
        if not integrated_data.get('platform'):
            raise ValueError("platform은 필수입니다")
        
        cursor.execute("""
            INSERT OR REPLACE INTO integrated_objects (
                original_id, tenant_id, platform, object_type,
                original_data, integrated_content, summary, tenant_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(integrated_data.get('original_id')),  # original_id (문자열로 변환)
            integrated_data.get('tenant_id'),
            integrated_data.get('platform'),
            integrated_data.get('object_type'),
            json.dumps(integrated_data.get('original_data', {})),
            integrated_data.get('integrated_content'),
            integrated_data.get('summary'),
            json.dumps(integrated_data.get('tenant_metadata', {}))
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
            'tenant_metadata': {
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

    def log_progress(self, job_id: str = None, tenant_id: str = None, message: str = "", 
                    percentage: float = 0, step: int = 0, total_steps: int = 100,
                    stage: str = None, **kwargs) -> int:
        """
        작업 진행 상황을 데이터베이스에 로그
        
        Args:
            job_id: 작업 ID (선택사항, 없으면 자동 생성)
            tenant_id: 테넌트 ID (선택사항, 없으면 기본값 사용)
            message: 진행 상황 메시지
            percentage: 진행률 (0-100)
            step: 현재 단계
            total_steps: 전체 단계 수
            stage: 단계 이름 (호환성을 위해, 무시됨)
            **kwargs: 기타 파라미터 (호환성을 위해, 무시됨)
        
        Returns:
            int: 로그 ID
        """
        if not self.connection:
            self.connect()
        
        # 기본값 설정
        if job_id is None:
            job_id = "default_job"
        if tenant_id is None:
            tenant_id = self.tenant_id or "default_tenant"
        
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO progress_logs (
                    job_id, tenant_id, message, percentage, step, total_steps
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (job_id, tenant_id, message, percentage, step, total_steps))
            
            self.connection.commit()
            log_id = cursor.lastrowid
            logger.debug(f"진행 상황 로그 저장: job_id={job_id}, tenant_id={tenant_id}, "
                        f"message='{message}', percentage={percentage}%")
            return log_id
            
        except Exception as e:
            logger.error(f"진행 상황 로그 저장 실패: {e}")
            # 호환성을 위해 예외를 발생시키지 않고 0 반환
            return 0
    
    def get_progress_logs(self, job_id: str = None, tenant_id: str = None, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        진행 상황 로그 조회
        
        Args:
            job_id: 작업 ID (선택사항)
            tenant_id: 테넌트 ID (선택사항)
            limit: 최대 조회 개수
            
        Returns:
            List[Dict]: 진행 상황 로그 목록
        """
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        query = "SELECT * FROM progress_logs WHERE 1=1"
        params = []
        
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def clear_progress_logs(self, job_id: str = None, tenant_id: str = None) -> int:
        """
        진행 상황 로그 삭제
        
        Args:
            job_id: 작업 ID (선택사항)
            tenant_id: 테넌트 ID (선택사항)
            
        Returns:
            int: 삭제된 로그 개수
        """
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        if job_id and tenant_id:
            cursor.execute("DELETE FROM progress_logs WHERE job_id = ? AND tenant_id = ?", 
                          (job_id, tenant_id))
        elif job_id:
            cursor.execute("DELETE FROM progress_logs WHERE job_id = ?", (job_id,))
        elif tenant_id:
            cursor.execute("DELETE FROM progress_logs WHERE tenant_id = ?", (tenant_id,))
        else:
            cursor.execute("DELETE FROM progress_logs")
        
        self.connection.commit()
        deleted_count = cursor.rowcount
        logger.info(f"진행 상황 로그 삭제 완료: {deleted_count}개")
        return deleted_count

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
            AND usage_date >= date('now', '-' || ? || ' days')
        """
        
        params = [tenant_id, days]
        
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
