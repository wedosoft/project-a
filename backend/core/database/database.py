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
        
        # 이미 테이블이 생성되었다면 스킵
        if self._tables_created:
            logger.debug("테이블이 이미 생성되어 있음 - 스킵")
            return
        
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
    
    # 레거시 메서드들 (호환성을 위해 간단한 형태로 유지)
    def log_usage(self, usage_data: Dict[str, Any]) -> int:
        """사용량 로그 기록 - 레거시 메서드"""
        logger.warning("log_usage 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return 1  # 임시 반환값
    
    def get_usage_summary(self, tenant_id: int, usage_type: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """사용량 요약 조회 - 레거시 메서드"""
        logger.warning("get_usage_summary 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return []
    
    def update_seat_usage(self, tenant_id: int, used_seats: int) -> bool:
        """시트 사용량 업데이트 - 레거시 메서드"""
        logger.warning("update_seat_usage 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return True
    
    def get_subscription_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """구독 플랜 정보 조회 - 레거시 메서드"""
        logger.warning("get_subscription_plan 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return None
    
    def insert_billing_record(self, billing_data: Dict[str, Any]) -> int:
        """결제 기록 생성 - 레거시 메서드"""
        logger.warning("insert_billing_record 메서드는 레거시입니다. ORM 모델을 직접 사용하세요.")
        return 1
    
    def get_integrated_objects_count(self, object_type: str = None) -> int:
        """통합 객체 개수 조회 - ORM 기반으로 수정"""
        session = self.get_session()
        try:
            from .models import IntegratedObject
            
            query = session.query(IntegratedObject).filter_by(tenant_id=self.tenant_id)
            if object_type:
                query = query.filter_by(object_type=object_type)
            
            count = query.count()
            return count
            
        except Exception as e:
            logger.error(f"{object_type} 타입 객체 개수 조회 오류: {e}")
            return 0
        finally:
            session.close()
    
    def get_integrated_objects_statistics(self) -> Dict[str, Any]:
        """통합 객체 통계 정보 반환 - ORM 기반으로 수정"""
        session = self.get_session()
        try:
            from .models import IntegratedObject
            from sqlalchemy import func
            
            # 전체 개수
            total_count = session.query(IntegratedObject).filter_by(tenant_id=self.tenant_id).count()
            
            # 타입별 개수
            type_counts_query = session.query(
                IntegratedObject.object_type,
                func.count(IntegratedObject.id).label('count')
            ).filter_by(tenant_id=self.tenant_id).group_by(IntegratedObject.object_type).all()
            
            type_counts = {obj_type: count for obj_type, count in type_counts_query}
            
            # 최근 생성된 객체들
            latest_by_type_query = session.query(
                IntegratedObject.object_type,
                func.max(IntegratedObject.created_at).label('latest_created')
            ).filter_by(tenant_id=self.tenant_id).group_by(IntegratedObject.object_type).all()
            
            latest_by_type = {obj_type: latest for obj_type, latest in latest_by_type_query}
            
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
            session.close()
    
    def log_progress(self, job_id: str = None, tenant_id: str = None, message: str = "", 
                    percentage: float = 0, step: int = 0, total_steps: int = 100,
                    stage: str = None, **kwargs) -> int:
        """
        작업 진행 상황을 데이터베이스에 로그 (ORM 기반)
        
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
        # 기본값 설정
        if job_id is None:
            job_id = "default_job"
        if tenant_id is None:
            tenant_id = self.tenant_id or "default_tenant"
        
        session = self.get_session()
        try:
            from .models import ProgressLog
            
            # 진행 상황 로그 생성
            progress_log = ProgressLog(
                job_id=job_id,
                tenant_id=tenant_id,
                message=message,
                percentage=percentage,
                step=step,
                total_steps=total_steps
            )
            
            session.add(progress_log)
            session.commit()
            log_id = progress_log.id
            
            logger.debug(f"진행 상황 로그 저장: job_id={job_id}, tenant_id={tenant_id}, "
                        f"message='{message}', percentage={percentage}%")
            return log_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"진행 상황 로그 저장 실패: {e}")
            # 호환성을 위해 예외를 발생시키지 않고 0 반환
            return 0
        finally:
            session.close()
    
    def get_progress_logs(self, job_id: str = None, tenant_id: str = None, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        진행 상황 로그 조회 (ORM 기반)
        
        Args:
            job_id: 작업 ID (선택사항)
            tenant_id: 테넌트 ID (선택사항)
            limit: 최대 조회 개수
            
        Returns:
            List[Dict]: 진행 상황 로그 목록
        """
        session = self.get_session()
        try:
            from .models import ProgressLog
            from sqlalchemy import desc
            
            # 쿼리 구성
            query = session.query(ProgressLog)
            
            if job_id:
                query = query.filter(ProgressLog.job_id == job_id)
            if tenant_id:
                query = query.filter(ProgressLog.tenant_id == tenant_id)
            
            # 최신 순으로 정렬하고 제한
            logs = query.order_by(desc(ProgressLog.created_at)).limit(limit).all()
            
            # 딕셔너리로 변환
            result = []
            for log in logs:
                result.append({
                    'id': log.id,
                    'job_id': log.job_id,
                    'tenant_id': log.tenant_id,
                    'message': log.message,
                    'percentage': log.percentage,
                    'step': log.step,
                    'total_steps': log.total_steps,
                    'created_at': log.created_at
                })
            
            return result
            
        except Exception as e:
            logger.error(f"진행 상황 로그 조회 실패: {e}")
            return []
        finally:
            session.close()
    
    def clear_progress_logs(self, job_id: str = None, tenant_id: str = None) -> int:
        """
        진행 상황 로그 삭제 (ORM 기반)
        
        Args:
            job_id: 작업 ID (선택사항)
            tenant_id: 테넌트 ID (선택사항)
            
        Returns:
            int: 삭제된 로그 개수
        """
        session = self.get_session()
        try:
            from .models import ProgressLog
            
            # 쿼리 구성
            query = session.query(ProgressLog)
            
            if job_id:
                query = query.filter(ProgressLog.job_id == job_id)
            if tenant_id:
                query = query.filter(ProgressLog.tenant_id == tenant_id)
            
            # 삭제 실행
            deleted_count = query.delete()
            session.commit()
            
            logger.info(f"진행 상황 로그 {deleted_count}개 삭제됨")
            return deleted_count
            
        except Exception as e:
            session.rollback()
            logger.error(f"진행 상황 로그 삭제 실패: {e}")
            return 0
        finally:
            session.close()


# 호환성을 위한 alias
DatabaseManager = SQLiteDatabase

# 데이터베이스 인스턴스 캐시
_database_cache = {}

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
    
    cache_key = f"{tenant_id}:{platform}"
    
    if cache_key not in _database_cache:
        _database_cache[cache_key] = SQLiteDatabase(tenant_id, platform)
    
    return _database_cache[cache_key]


def get_session(tenant_id: str = None, platform: str = "freshdesk"):
    """
    데이터베이스 세션을 반환하는 헬퍼 함수
    
    Args:
        tenant_id: 테넌트 ID (필수)
        platform: 플랫폼 이름 (기본값: "freshdesk")
    
    Returns:
        SQLAlchemy 세션
    """
    if not tenant_id:
        raise ValueError("tenant_id는 필수 매개변수입니다")
    
    db_instance = get_database(tenant_id, platform)
    return db_instance.get_session()


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
