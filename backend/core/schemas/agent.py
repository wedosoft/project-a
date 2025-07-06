"""
에이전트 데이터 정규화 스키마

Freshdesk API 응답을 데이터베이스 모델로 변환하는 정규화 함수를 제공합니다.
"""

from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def normalize_agent_data(agent_data: Dict[str, Any], tenant_id: str, platform: str) -> Dict[str, Any]:
    """
    Freshdesk API 응답을 Agent 모델에 맞게 정규화합니다.
    
    Args:
        agent_data: Freshdesk API에서 받은 원본 에이전트 데이터
        tenant_id: 테넌트 ID
        platform: 플랫폼 (freshdesk)
        
    Returns:
        정규화된 에이전트 데이터 딕셔너리
    """
    try:
        # contact 정보 추출
        contact = agent_data.get("contact", {})
        
        # 기본값 설정
        normalized = {
            # 멀티테넌트 필드
            "tenant_id": tenant_id,
            "platform": platform,
            
            # Freshdesk 에이전트 ID
            "id": agent_data["id"],
            
            # 에이전트 기본 정보
            "available": agent_data.get("available", True),
            "occasional": agent_data.get("occasional", False),
            "signature": agent_data.get("signature"),
            "ticket_scope": agent_data.get("ticket_scope", 1),
            "available_since": agent_data.get("available_since"),
            "type": agent_data.get("type", "support_agent"),
            "focus_mode": agent_data.get("focus_mode", True),
            
            # contact 정보 평면화
            "active": contact.get("active", True),
            "email": contact.get("email", ""),
            "job_title": contact.get("job_title"),
            "language": contact.get("language", "en"),
            "last_login_at": contact.get("last_login_at"),
            "mobile": contact.get("mobile"),
            "name": contact.get("name", "Unknown"),
            "phone": contact.get("phone"),
            "time_zone": contact.get("time_zone", "UTC"),
            "contact_created_at": contact.get("created_at"),
            "contact_updated_at": contact.get("updated_at"),
            
            # 라이선스 상태 (기본값: True)
            "license_active": True,
            
            # 타임스탬프
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # None 값 제거
        normalized = {k: v for k, v in normalized.items() if v is not None}
        
        logger.debug(f"에이전트 데이터 정규화 완료: {normalized['email']} (ID: {normalized['id']})")
        return normalized
        
    except Exception as e:
        logger.error(f"에이전트 데이터 정규화 중 오류: {e}")
        logger.error(f"원본 데이터: {agent_data}")
        raise