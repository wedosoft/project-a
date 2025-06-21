# -*- coding: utf-8 -*-
"""
플랫폼 팩토리 (Platform Factory)

멀티플랫폼 어댑터를 생성하고 관리하는 팩토리 클래스입니다.
Freshdesk, Zendesk 등 다양한 플랫폼 지원을 위한 확장 가능한 구조입니다.
"""
from typing import Dict, Type, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class PlatformAdapter(ABC):
    """플랫폼 어댑터 추상 클래스"""
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환"""
        pass
    
    @abstractmethod
    def fetch_tickets(self, since_date: str = None, include_attachments: bool = True) -> list:
        """티켓 데이터 수집"""
        pass
    
    @abstractmethod
    def fetch_kb_articles(self, since_date: str = None) -> list:
        """KB 아티클 수집"""
        pass
    
    @abstractmethod
    def get_attachment_url(self, attachment_id: str, **kwargs) -> str:
        """첨부파일 다운로드 URL 생성"""
        pass


class PlatformFactory:
    """플랫폼 어댑터 팩토리"""
    
    _adapters: Dict[str, Type[PlatformAdapter]] = {}
    
    @classmethod
    def register_adapter(cls, platform_name: str, adapter_class: Type[PlatformAdapter]):
        """어댑터 등록"""
        cls._adapters[platform_name.lower()] = adapter_class
        logger.info(f"플랫폼 어댑터 등록: {platform_name}")
    
    @classmethod
    def create_adapter(cls, platform: str, config: dict) -> PlatformAdapter:
        """플랫폼별 어댑터 생성"""
        platform_key = platform.lower()
        
        if platform_key not in cls._adapters:
            raise ValueError(f"지원하지 않는 플랫폼: {platform}")
        
        adapter_class = cls._adapters[platform_key]
        return adapter_class(config)
    
    @classmethod
    def get_supported_platforms(cls) -> list:
        """지원하는 플랫폼 목록 반환"""
        return list(cls._adapters.keys())


# 플랫폼별 어댑터 자동 등록
def _register_adapters():
    """지원 플랫폼 어댑터 자동 등록"""
    try:
        from .freshdesk.adapter import FreshdeskAdapter
        PlatformFactory.register_adapter('freshdesk', FreshdeskAdapter)
    except ImportError as e:
        logger.warning(f"Freshdesk 어댑터 로드 실패: {e}")
    
    try:
        from .zendesk.adapter import ZendeskAdapter
        PlatformFactory.register_adapter('zendesk', ZendeskAdapter)
    except ImportError as e:
        logger.debug(f"Zendesk 어댑터 로드 실패 (정상): {e}")


# 모듈 로드 시 어댑터 자동 등록
_register_adapters()
