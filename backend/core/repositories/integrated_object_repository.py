"""
통합 객체 Repository
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..database.models.integrated_object import IntegratedObject


class IntegratedObjectRepository:
    """통합 객체 리포지토리"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_company(
        self, 
        tenant_id: str, 
        object_type: Optional[str] = None, 
        platform: str = 'freshdesk'
    ) -> List[IntegratedObject]:
        """회사별 통합 객체 조회"""
        query = self.session.query(IntegratedObject).filter_by(
            tenant_id=tenant_id,
            platform=platform
        )
        
        if object_type:
            query = query.filter_by(object_type=object_type)
        
        return query.order_by(IntegratedObject.created_at.desc()).all()
    
    def get_by_original_id(
        self, 
        tenant_id: str, 
        original_id: str,
        object_type: str = 'integrated_ticket',
        platform: str = 'freshdesk'
    ) -> Optional[IntegratedObject]:
        """원본 ID로 통합 객체 조회"""
        return self.session.query(IntegratedObject).filter_by(
            tenant_id=tenant_id,
            platform=platform,
            object_type=object_type,
            original_id=original_id
        ).first()
    
    def create(self, data: Dict[str, Any]) -> IntegratedObject:
        """통합 객체 생성"""
        obj = IntegratedObject(**data)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def update_summary(
        self, 
        obj_id: int, 
        summary: str,
        summary_generated_at: Optional[datetime] = None
    ) -> bool:
        """요약 업데이트"""
        obj = self.session.query(IntegratedObject).filter_by(id=obj_id).first()
        if obj:
            obj.summary = summary
            obj.summary_generated_at = summary_generated_at or datetime.utcnow()
            self.session.commit()
            return True
        return False
    
    def get_unsummarized(
        self,
        tenant_id: str,
        object_type: str = 'integrated_ticket',
        platform: str = 'freshdesk',
        limit: int = 100
    ) -> List[IntegratedObject]:
        """요약되지 않은 객체들 조회"""
        return self.session.query(IntegratedObject).filter_by(
            tenant_id=tenant_id,
            platform=platform,
            object_type=object_type
        ).filter(
            IntegratedObject.summary.is_(None)
        ).limit(limit).all()
    
    def delete_by_original_id(
        self,
        tenant_id: str,
        original_id: str,
        object_type: str = 'integrated_ticket',
        platform: str = 'freshdesk'
    ) -> bool:
        """원본 ID로 객체 삭제"""
        obj = self.get_by_original_id(tenant_id, original_id, object_type, platform)
        if obj:
            self.session.delete(obj)
            self.session.commit()
            return True
        return False
