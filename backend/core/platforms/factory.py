# -*- coding: utf-8 -*-
"""
Freshdesk 플랫폼 팩토리 (Freshdesk Platform Factory)

Freshdesk 전용 어댑터를 생성하고 관리하는 팩토리 클래스입니다.
점진적 단순화를 통해 멀티플랫폼 지원에서 Freshdesk 전용으로 변경되었습니다.
"""
from typing import Dict, Type, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class PlatformAdapter(ABC):
    """Freshdesk 플랫폼 어댑터 추상 클래스"""
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환 (항상 'freshdesk')"""
        pass
    
    @abstractmethod
    def fetch_tickets(self, since_date: str = None, include_attachments: bool = True) -> list:
        """Freshdesk 티켓 데이터 수집"""
        pass
    
    @abstractmethod
    def fetch_kb_articles(self, since_date: str = None) -> list:
        """Freshdesk KB 아티클 수집"""
        pass
    
    @abstractmethod
    def get_attachment_url(self, attachment_id: str, **kwargs) -> str:
        """Freshdesk 첨부파일 다운로드 URL 생성"""
        pass


class PlatformFactory:
    """Freshdesk 전용 플랫폼 어댑터 팩토리"""
    
    _adapters: Dict[str, Type[PlatformAdapter]] = {}
    
    @classmethod
    def register_adapter(cls, platform_name: str, adapter_class: Type[PlatformAdapter]):
        """Freshdesk 어댑터 등록"""
        if platform_name.lower() != "freshdesk":
            logger.warning(f"Freshdesk 전용 팩토리입니다. '{platform_name}' 등록 무시됨")
            return
        cls._adapters[platform_name.lower()] = adapter_class
        logger.info(f"Freshdesk 어댑터 등록 완료: {platform_name}")
    
    @classmethod
    def create_adapter(cls, platform: str, config: dict) -> PlatformAdapter:
        """Freshdesk 어댑터 생성 (다른 플랫폼은 지원하지 않음)"""
        platform_key = platform.lower()
        
        if platform_key != "freshdesk":
            raise ValueError(f"Freshdesk만 지원됩니다. 요청된 플랫폼: {platform}")
        
        if platform_key not in cls._adapters:
            raise ValueError(f"Freshdesk 어댑터가 등록되지 않았습니다")
        
        adapter_class = cls._adapters[platform_key]
        return adapter_class(config)
    
    @classmethod
    def get_supported_platforms(cls) -> list:
        """지원하는 플랫폼 목록 반환 (Freshdesk만)"""
        return ["freshdesk"]  # 항상 Freshdesk만 반환


# Freshdesk 어댑터 자동 등록
def _register_freshdesk_adapter():
    """Freshdesk 어댑터 자동 등록"""
    try:
        from .freshdesk.adapter import FreshdeskAdapter
        PlatformFactory.register_adapter('freshdesk', FreshdeskAdapter)
        logger.info("Freshdesk 어댑터 등록 완료")
    except ImportError as e:
        logger.error(f"Freshdesk 어댑터 로드 실패: {e}")
        raise ImportError(f"Freshdesk 어댑터를 로드할 수 없습니다: {e}")


# 모듈 로드 시 Freshdesk 어댑터 자동 등록
_register_freshdesk_adapter()
