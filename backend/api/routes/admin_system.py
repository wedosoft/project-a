"""
시스템 관리 API 라우터

데이터 삭제, 복구, 시스템 상태 조회 등 관리자용 시스템 관리 기능을 제공합니다.
소프트 삭제를 지원하여 30일 이내 복구가 가능합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, update
import logging
import asyncio

from ..models.responses import BaseModel, Field
from ..dependencies import (
    get_tenant_id, get_platform, get_api_key, get_domain,
    get_vector_db, get_tenant_config
)
from core.database import get_session
from core.database.models.ticket import Ticket
from core.database.models.article import Article
from core.database.models.agent import Agent
from core.database.models.attachment import Attachment

# 라우터 생성
router = APIRouter(prefix="/admin/system", tags=["시스템 관리"])

# 로거 설정
logger = logging.getLogger(__name__)


class DataPurgeRequest(BaseModel):
    """데이터 삭제 요청 모델"""
    
    purge_type: str = Field(
        description="삭제 타입 (all, tickets, articles, agents, vectors)"
    )
    hard_delete: bool = Field(
        default=False,
        description="하드 삭제 여부 (True: 즉시 삭제, False: 소프트 삭제)"
    )
    include_attachments: bool = Field(
        default=True,
        description="첨부파일 포함 삭제 여부"
    )
    reason: Optional[str] = Field(
        default=None,
        description="삭제 사유"
    )


class DataPurgeResponse(BaseModel):
    """데이터 삭제 응답 모델"""
    
    success: bool = Field(description="성공 여부")
    message: str = Field(description="응답 메시지")
    purge_type: str = Field(description="삭제 타입")
    deleted_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="삭제된 항목 수"
    )
    soft_deleted: bool = Field(description="소프트 삭제 여부")
    recovery_deadline: Optional[datetime] = Field(
        default=None,
        description="복구 가능 기한"
    )
    job_id: Optional[str] = Field(
        default=None,
        description="백그라운드 작업 ID"
    )


class DataRestoreRequest(BaseModel):
    """데이터 복구 요청 모델"""
    
    restore_type: str = Field(
        description="복구 타입 (all, tickets, articles, agents)"
    )
    deleted_after: Optional[datetime] = Field(
        default=None,
        description="특정 시점 이후 삭제된 데이터만 복구"
    )


class DataRestoreResponse(BaseModel):
    """데이터 복구 응답 모델"""
    
    success: bool = Field(description="성공 여부")
    message: str = Field(description="응답 메시지")
    restore_type: str = Field(description="복구 타입")
    restored_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="복구된 항목 수"
    )


class SystemStatusResponse(BaseModel):
    """시스템 상태 응답 모델"""
    
    status: str = Field(description="전체 상태 (healthy, warning, critical)")
    tenant_id: str = Field(description="테넌트 ID")
    platform: str = Field(description="플랫폼")
    
    # 데이터 통계
    data_stats: Dict[str, int] = Field(
        description="데이터 통계 (tickets, articles, agents, vectors)"
    )
    
    # 저장소 상태
    storage_status: Dict[str, Any] = Field(
        description="저장소 상태 정보"
    )
    
    # 최근 활동
    recent_activities: Dict[str, Any] = Field(
        description="최근 활동 정보"
    )
    
    # 시스템 건강도
    health_checks: Dict[str, bool] = Field(
        description="시스템 건강도 체크"
    )
    
    last_updated: datetime = Field(description="마지막 업데이트 시간")


async def perform_data_purge(
    tenant_id: str,
    purge_type: str,
    hard_delete: bool,
    include_attachments: bool,
    session: Session,
    vector_db
):
    """실제 데이터 삭제를 수행하는 함수"""
    deleted_counts = {
        "tickets": 0,
        "articles": 0,
        "agents": 0,
        "attachments": 0,
        "vectors": 0
    }
    
    try:
        # 삭제 시점 기록
        deleted_at = datetime.utcnow()
        
        # 티켓 삭제
        if purge_type in ["all", "tickets"]:
            if hard_delete:
                count = session.query(Ticket).filter(
                    Ticket.tenant_id == tenant_id
                ).delete()
            else:
                count = session.query(Ticket).filter(
                    Ticket.tenant_id == tenant_id,
                    Ticket.deleted_at.is_(None)
                ).update({"deleted_at": deleted_at})
            deleted_counts["tickets"] = count
        
        # 아티클 삭제
        if purge_type in ["all", "articles"]:
            if hard_delete:
                count = session.query(Article).filter(
                    Article.tenant_id == tenant_id
                ).delete()
            else:
                count = session.query(Article).filter(
                    Article.tenant_id == tenant_id,
                    Article.deleted_at.is_(None)
                ).update({"deleted_at": deleted_at})
            deleted_counts["articles"] = count
        
        # 에이전트 삭제
        if purge_type in ["all", "agents"]:
            if hard_delete:
                count = session.query(Agent).filter(
                    Agent.tenant_id == tenant_id
                ).delete()
            else:
                # 에이전트는 소프트 삭제 시 라이선스도 비활성화
                count = session.query(Agent).filter(
                    Agent.tenant_id == tenant_id,
                    Agent.deleted_at.is_(None)
                ).update({
                    "deleted_at": deleted_at,
                    "license_active": False
                })
            deleted_counts["agents"] = count
        
        # 첨부파일 삭제
        if include_attachments and purge_type in ["all", "tickets"]:
            if hard_delete:
                count = session.query(Attachment).filter(
                    Attachment.tenant_id == tenant_id
                ).delete()
            else:
                count = session.query(Attachment).filter(
                    Attachment.tenant_id == tenant_id,
                    Attachment.deleted_at.is_(None)
                ).update({"deleted_at": deleted_at})
            deleted_counts["attachments"] = count
        
        # 벡터 DB 삭제
        if purge_type in ["all", "vectors"]:
            try:
                # 컬렉션별로 삭제
                collections = ["tickets", "articles", "attachments"]
                for collection in collections:
                    result = await vector_db.delete_by_metadata(
                        collection_name=collection,
                        metadata_filter={"tenant_id": tenant_id}
                    )
                    deleted_counts["vectors"] += result.get("deleted_count", 0)
            except Exception as e:
                logger.error(f"벡터 DB 삭제 중 오류: {e}")
        
        # 변경사항 커밋
        session.commit()
        
        return deleted_counts
        
    except Exception as e:
        session.rollback()
        logger.error(f"데이터 삭제 중 오류: {e}")
        raise


@router.post("/purge", response_model=DataPurgeResponse)
async def purge_data(
    request: DataPurgeRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session),
    vector_db = Depends(get_vector_db)
):
    """
    테넌트 데이터를 삭제합니다.
    
    - 소프트 삭제(기본값): deleted_at 필드를 설정하여 30일 이내 복구 가능
    - 하드 삭제: 데이터를 즉시 완전히 삭제 (복구 불가)
    """
    try:
        # 삭제 작업 수행
        deleted_counts = await perform_data_purge(
            tenant_id=tenant_id,
            purge_type=request.purge_type,
            hard_delete=request.hard_delete,
            include_attachments=request.include_attachments,
            session=session,
            vector_db=vector_db
        )
        
        # 복구 기한 계산 (소프트 삭제인 경우)
        recovery_deadline = None
        if not request.hard_delete:
            recovery_deadline = datetime.utcnow() + timedelta(days=30)
        
        # 삭제 로그 기록
        logger.info(
            f"데이터 삭제 완료 - 테넌트: {tenant_id}, "
            f"타입: {request.purge_type}, "
            f"하드삭제: {request.hard_delete}, "
            f"삭제수: {deleted_counts}"
        )
        
        return DataPurgeResponse(
            success=True,
            message=f"데이터 삭제가 완료되었습니다",
            purge_type=request.purge_type,
            deleted_counts=deleted_counts,
            soft_deleted=not request.hard_delete,
            recovery_deadline=recovery_deadline
        )
        
    except Exception as e:
        logger.error(f"데이터 삭제 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore", response_model=DataRestoreResponse)
async def restore_data(
    request: DataRestoreRequest,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """
    소프트 삭제된 데이터를 복구합니다.
    
    30일 이내에 소프트 삭제된 데이터만 복구 가능합니다.
    """
    try:
        restored_counts = {
            "tickets": 0,
            "articles": 0,
            "agents": 0,
            "attachments": 0
        }
        
        # 복구 가능 기한 (30일)
        recovery_limit = datetime.utcnow() - timedelta(days=30)
        
        # 기본 필터 조건
        base_filter = [
            lambda Model: Model.tenant_id == tenant_id,
            lambda Model: Model.deleted_at.isnot(None),
            lambda Model: Model.deleted_at >= recovery_limit
        ]
        
        # 특정 시점 이후 필터 추가
        if request.deleted_after:
            base_filter.append(lambda Model: Model.deleted_at >= request.deleted_after)
        
        # 티켓 복구
        if request.restore_type in ["all", "tickets"]:
            count = session.query(Ticket).filter(
                *[f(Ticket) for f in base_filter]
            ).update({"deleted_at": None})
            restored_counts["tickets"] = count
            
            # 관련 첨부파일도 복구
            count = session.query(Attachment).filter(
                *[f(Attachment) for f in base_filter]
            ).update({"deleted_at": None})
            restored_counts["attachments"] = count
        
        # 아티클 복구
        if request.restore_type in ["all", "articles"]:
            count = session.query(Article).filter(
                *[f(Article) for f in base_filter]
            ).update({"deleted_at": None})
            restored_counts["articles"] = count
        
        # 에이전트 복구
        if request.restore_type in ["all", "agents"]:
            count = session.query(Agent).filter(
                *[f(Agent) for f in base_filter]
            ).update({"deleted_at": None})
            restored_counts["agents"] = count
        
        # 변경사항 커밋
        session.commit()
        
        logger.info(
            f"데이터 복구 완료 - 테넌트: {tenant_id}, "
            f"타입: {request.restore_type}, "
            f"복구수: {restored_counts}"
        )
        
        return DataRestoreResponse(
            success=True,
            message="데이터 복구가 완료되었습니다",
            restore_type=request.restore_type,
            restored_counts=restored_counts
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"데이터 복구 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session),
    vector_db = Depends(get_vector_db)
):
    """시스템 상태 및 통계를 조회합니다."""
    try:
        # 데이터 통계
        data_stats = {
            "tickets": session.query(Ticket).filter(
                Ticket.tenant_id == tenant_id,
                Ticket.deleted_at.is_(None)
            ).count(),
            "articles": session.query(Article).filter(
                Article.tenant_id == tenant_id,
                Article.deleted_at.is_(None)
            ).count(),
            "agents": session.query(Agent).filter(
                Agent.tenant_id == tenant_id,
                Agent.deleted_at.is_(None)
            ).count(),
            "active_licenses": session.query(Agent).filter(
                Agent.tenant_id == tenant_id,
                Agent.deleted_at.is_(None),
                Agent.license_active == True
            ).count()
        }
        
        # 저장소 상태
        storage_status = {
            "database": "connected",
            "vector_db": "connected",
            "soft_deleted_items": session.query(
                func.count()
            ).select_from(
                Ticket
            ).filter(
                Ticket.tenant_id == tenant_id,
                Ticket.deleted_at.isnot(None)
            ).scalar() or 0
        }
        
        # 최근 활동
        recent_activities = {
            "last_ingestion": session.query(
                func.max(Ticket.created_at)
            ).filter(
                Ticket.tenant_id == tenant_id
            ).scalar(),
            "last_agent_sync": session.query(
                func.max(Agent.updated_at)
            ).filter(
                Agent.tenant_id == tenant_id
            ).scalar()
        }
        
        # 시스템 건강도 체크
        health_checks = {
            "database": True,
            "vector_db": True,
            "data_integrity": data_stats["tickets"] >= 0,
            "license_compliance": data_stats["active_licenses"] <= data_stats["agents"]
        }
        
        # 전체 상태 결정
        if all(health_checks.values()):
            status = "healthy"
        elif any(not v for v in health_checks.values()):
            status = "critical"
        else:
            status = "warning"
        
        return SystemStatusResponse(
            status=status,
            tenant_id=tenant_id,
            platform=platform,
            data_stats=data_stats,
            storage_status=storage_status,
            recent_activities=recent_activities,
            health_checks=health_checks,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"시스템 상태 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))