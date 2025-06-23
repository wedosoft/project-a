"""
최적화된 데이터베이스 접근 레이어 (Repository Pattern)

고성능 데이터 액세스를 위한 최적화된 쿼리와 배치 처리 지원
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import create_engine, and_, or_, func, desc, asc
from sqlalchemy.orm import sessionmaker, Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import logging

from .optimized_models import (
    Base, Company, Agent, Category, Ticket, Conversation, 
    Attachment, Summary, ProcessingLog
)

logger = logging.getLogger(__name__)


class OptimizedRepository:
    """최적화된 데이터베이스 접근 레이어"""
    
    def __init__(self, db_url: str):
        self.engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            # SQLite 최적화 설정
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            } if "sqlite" in db_url else {}
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # 테이블 생성
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """세션 반환"""
        return self.SessionLocal()
    
    # ===================
    # 티켓 관련 메서드
    # ===================
    
    def get_tickets_for_summary(
        self, 
        company_id: Optional[int] = None,
        limit: int = 100,
        skip_existing_summaries: bool = True
    ) -> List[Ticket]:
        """요약 대상 티켓 조회 (최적화)"""
        
        with self.get_session() as db:
            query = db.query(Ticket).options(
                joinedload(Ticket.company),
                joinedload(Ticket.agent),
                joinedload(Ticket.category),
                selectinload(Ticket.conversations)
            )
            
            # 회사 필터
            if company_id:
                query = query.filter(Ticket.company_id == company_id)
            
            # 기존 요약이 없는 티켓만 조회
            if skip_existing_summaries:
                query = query.outerjoin(Summary, and_(
                    Summary.ticket_id == Ticket.id,
                    Summary.is_active == True
                )).filter(Summary.id.is_(None))
            
            # 대화가 있는 티켓만 (요약할 내용이 있는)
            query = query.filter(Ticket.conversation_count > 0)
            
            # 최신 순으로 정렬
            query = query.order_by(desc(Ticket.created_at))
            
            return query.limit(limit).all()
    
    def get_ticket_with_conversations(self, ticket_id: int) -> Optional[Ticket]:
        """티켓과 대화 내용 전체 조회"""
        
        with self.get_session() as db:
            return db.query(Ticket).options(
                joinedload(Ticket.company),
                joinedload(Ticket.agent),
                joinedload(Ticket.category),
                selectinload(Ticket.conversations).selectinload(Conversation.attachments)
            ).filter(Ticket.id == ticket_id).first()
    
    def update_ticket_stats(self, ticket_id: int) -> bool:
        """티켓 통계 정보 업데이트"""
        
        with self.get_session() as db:
            try:
                # 대화 수 계산
                conversation_count = db.query(func.count(Conversation.id)).filter(
                    Conversation.ticket_id == ticket_id
                ).scalar()
                
                # 첨부파일 수 계산
                attachment_count = db.query(func.count(Attachment.id)).join(
                    Conversation
                ).filter(Conversation.ticket_id == ticket_id).scalar()
                
                # 티켓 업데이트
                db.query(Ticket).filter(Ticket.id == ticket_id).update({
                    'conversation_count': conversation_count,
                    'attachment_count': attachment_count,
                    'updated_at': datetime.utcnow()
                })
                
                db.commit()
                return True
                
            except Exception as e:
                logger.error(f"티켓 통계 업데이트 실패: {ticket_id} - {e}")
                db.rollback()
                return False
    
    # ===================
    # 요약 관련 메서드
    # ===================
    
    def create_summary(
        self,
        ticket_id: int,
        summary_text: str,
        quality_score: float,
        model_used: str,
        tokens_input: int,
        tokens_output: int,
        processing_time_ms: int,
        cost_estimate: float = 0.0,
        **kwargs
    ) -> Optional[Summary]:
        """요약 생성"""
        
        with self.get_session() as db:
            try:
                # 기존 활성 요약 비활성화
                db.query(Summary).filter(
                    Summary.ticket_id == ticket_id,
                    Summary.is_active == True
                ).update({'is_active': False})
                
                # 새 요약 생성
                summary = Summary(
                    ticket_id=ticket_id,
                    summary_text=summary_text,
                    quality_score=quality_score,
                    model_used=model_used,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    processing_time_ms=processing_time_ms,
                    cost_estimate=cost_estimate,
                    **kwargs
                )
                
                db.add(summary)
                db.commit()
                db.refresh(summary)
                
                logger.info(f"요약 생성 완료: ticket_id={ticket_id}, quality={quality_score:.3f}")
                return summary
                
            except Exception as e:
                logger.error(f"요약 생성 실패: {ticket_id} - {e}")
                db.rollback()
                return None
    
    def get_summary_by_ticket(self, ticket_id: int) -> Optional[Summary]:
        """티켓별 활성 요약 조회"""
        
        with self.get_session() as db:
            return db.query(Summary).filter(
                Summary.ticket_id == ticket_id,
                Summary.is_active == True
            ).first()
    
    def get_summaries_by_quality(
        self, 
        min_quality: float = 0.9,
        limit: int = 100
    ) -> List[Summary]:
        """품질 점수별 요약 조회"""
        
        with self.get_session() as db:
            return db.query(Summary).options(
                joinedload(Summary.ticket).joinedload(Ticket.company)
            ).filter(
                Summary.is_active == True,
                Summary.quality_score >= min_quality
            ).order_by(desc(Summary.quality_score)).limit(limit).all()
    
    def get_summary_statistics(
        self, 
        company_id: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """요약 통계 조회"""
        
        with self.get_session() as db:
            # 기본 쿼리
            query = db.query(Summary).filter(Summary.is_active == True)
            
            # 회사 필터
            if company_id:
                query = query.join(Ticket).filter(Ticket.company_id == company_id)
            
            # 날짜 필터
            if days > 0:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query = query.filter(Summary.created_at >= cutoff_date)
            
            # 통계 계산
            stats = query.with_entities(
                func.count(Summary.id).label('total_count'),
                func.avg(Summary.quality_score).label('avg_quality'),
                func.sum(Summary.tokens_input + Summary.tokens_output).label('total_tokens'),
                func.sum(Summary.cost_estimate).label('total_cost'),
                func.count(func.nullif(Summary.quality_score >= 0.9, False)).label('high_quality_count')
            ).first()
            
            return {
                'total_summaries': stats.total_count or 0,
                'average_quality': round(stats.avg_quality or 0, 3),
                'total_tokens': stats.total_tokens or 0,
                'total_cost': round(stats.total_cost or 0, 2),
                'high_quality_count': stats.high_quality_count or 0,
                'high_quality_rate': round(
                    (stats.high_quality_count or 0) / max(stats.total_count or 1, 1) * 100, 1
                )
            }
    
    # ===================
    # 배치 처리 관련 메서드
    # ===================
    
    def get_batch_processing_candidates(
        self,
        batch_size: int = 100,
        process_type: str = 'summary'
    ) -> List[Ticket]:
        """배치 처리 대상 조회"""
        
        with self.get_session() as db:
            # 처리 로그가 없거나 실패한 티켓 조회
            subquery = db.query(ProcessingLog.record_id).filter(
                ProcessingLog.table_name == 'tickets',
                ProcessingLog.process_type == process_type,
                ProcessingLog.status.in_(['completed', 'processing'])
            ).subquery()
            
            return db.query(Ticket).filter(
                ~Ticket.id.in_(subquery),
                Ticket.conversation_count > 0
            ).order_by(desc(Ticket.created_at)).limit(batch_size).all()
    
    def create_processing_log(
        self,
        table_name: str,
        record_id: int,
        process_type: str,
        status: str = 'pending',
        batch_id: Optional[str] = None,
        **kwargs
    ) -> ProcessingLog:
        """처리 로그 생성"""
        
        with self.get_session() as db:
            log = ProcessingLog(
                table_name=table_name,
                record_id=record_id,
                process_type=process_type,
                status=status,
                batch_id=batch_id,
                **kwargs
            )
            
            db.add(log)
            db.commit()
            db.refresh(log)
            
            return log
    
    def update_processing_log(
        self,
        log_id: int,
        status: str,
        result_message: Optional[str] = None,
        error_message: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        **kwargs
    ) -> bool:
        """처리 로그 업데이트"""
        
        with self.get_session() as db:
            try:
                update_data = {
                    'status': status,
                    'completed_at': datetime.utcnow(),
                    **kwargs
                }
                
                if result_message:
                    update_data['result_message'] = result_message
                if error_message:
                    update_data['error_message'] = error_message
                if processing_time_ms:
                    update_data['processing_time_ms'] = processing_time_ms
                
                db.query(ProcessingLog).filter(
                    ProcessingLog.id == log_id
                ).update(update_data)
                
                db.commit()
                return True
                
            except Exception as e:
                logger.error(f"처리 로그 업데이트 실패: {log_id} - {e}")
                db.rollback()
                return False
    
    def get_processing_stats(
        self,
        process_type: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """처리 통계 조회"""
        
        with self.get_session() as db:
            query = db.query(ProcessingLog)
            
            if process_type:
                query = query.filter(ProcessingLog.process_type == process_type)
            
            if hours > 0:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                query = query.filter(ProcessingLog.started_at >= cutoff_time)
            
            # 상태별 집계
            stats = query.with_entities(
                ProcessingLog.status,
                func.count(ProcessingLog.id).label('count'),
                func.avg(ProcessingLog.processing_time_ms).label('avg_time')
            ).group_by(ProcessingLog.status).all()
            
            result = {
                'total': 0,
                'by_status': {},
                'average_processing_time_ms': 0
            }
            
            total_time = 0
            total_count = 0
            
            for stat in stats:
                result['by_status'][stat.status] = {
                    'count': stat.count,
                    'avg_time_ms': int(stat.avg_time or 0)
                }
                result['total'] += stat.count
                
                if stat.avg_time:
                    total_time += stat.avg_time * stat.count
                    total_count += stat.count
            
            if total_count > 0:
                result['average_processing_time_ms'] = int(total_time / total_count)
            
            return result
    
    # ===================
    # 유틸리티 메서드
    # ===================
    
    def get_database_size(self) -> Dict[str, Any]:
        """데이터베이스 크기 정보"""
        
        with self.get_session() as db:
            tables = [
                ('companies', Company),
                ('agents', Agent),
                ('categories', Category),
                ('tickets', Ticket),
                ('conversations', Conversation),
                ('attachments', Attachment),
                ('summaries', Summary),
                ('processing_logs', ProcessingLog)
            ]
            
            sizes = {}
            total_records = 0
            
            for table_name, model in tables:
                count = db.query(func.count(model.id)).scalar()
                sizes[table_name] = count
                total_records += count
            
            return {
                'tables': sizes,
                'total_records': total_records,
                'summary_coverage': round(
                    sizes.get('summaries', 0) / max(sizes.get('tickets', 1), 1) * 100, 1
                )
            }
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """오래된 로그 정리"""
        
        with self.get_session() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = db.query(ProcessingLog).filter(
                ProcessingLog.started_at < cutoff_date,
                ProcessingLog.status.in_(['completed', 'failed'])
            ).delete()
            
            db.commit()
            
            logger.info(f"오래된 로그 {deleted_count}개 정리 완료")
            return deleted_count
    
    def vacuum_database(self):
        """데이터베이스 최적화 (SQLite)"""
        
        if 'sqlite' in str(self.engine.url):
            with self.engine.connect() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
            logger.info("데이터베이스 최적화 완료")


# 싱글톤 인스턴스
_repository = None

def get_repository(db_url: str = None) -> OptimizedRepository:
    """Repository 싱글톤 인스턴스 반환"""
    global _repository
    
    if _repository is None:
        if db_url is None:
            db_url = "sqlite:///core/data/wedosoft_freshdesk_data_optimized.db"
        _repository = OptimizedRepository(db_url)
    
    return _repository
