# -*- coding: utf-8 -*-
"""
Zendesk 플랫폼 어댑터 구현 (향후 구현용)

현재는 PlatformAdapter 인터페이스를 구현하지만 NotImplementedError를 반환합니다.
향후 Zendesk API 연동 시 실제 구현이 필요합니다.
"""

from typing import Dict, List, Optional, Any
from ..factory import PlatformAdapter


class ZendeskAdapter(PlatformAdapter):
    """
    Zendesk API를 위한 플랫폼 어댑터 (향후 구현용)
    현재는 인터페이스만 구현되어 있으며, 실제 로직은 NotImplementedError 반환
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.platform = "zendesk"
        # Zendesk 관련 설정 값들은 향후 구현
    
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환"""
        return "zendesk"
    
    async def fetch_tickets(self, since_date: str = None, include_attachments: bool = True) -> list:
        """티켓 데이터 수집 (향후 구현)"""
        raise NotImplementedError("Zendesk 티켓 수집은 아직 구현되지 않았습니다")
    
    async def fetch_kb_articles(self, since_date: str = None) -> list:
        """KB 아티클 수집 (향후 구현)"""
        raise NotImplementedError("Zendesk KB 수집은 아직 구현되지 않았습니다")
    
    async def get_attachment_url(self, attachment_id: str, **kwargs) -> str:
        """첨부파일 다운로드 URL 생성 (향후 구현)"""
        raise NotImplementedError("Zendesk 첨부파일 URL 생성은 아직 구현되지 않았습니다")
