# -*- coding: utf-8 -*-
"""
멀티플랫폼 어댑터 모듈

플랫폼별 데이터 수집 및 정규화를 담당하는 어댑터들을 포함합니다.
현재 지원 플랫폼: Freshdesk
향후 확장 예정: Zendesk, ServiceNow 등
"""
from .factory import PlatformFactory

__all__ = ['PlatformFactory']
