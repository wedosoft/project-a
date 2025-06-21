# -*- coding: utf-8 -*-
"""
Freshdesk 플랫폼 모듈

Freshdesk 플랫폼을 위한 어댑터, 클라이언트, 데이터 수집기 등을 포함합니다.
"""
from .adapter import FreshdeskAdapter
from .collector import FreshdeskCollector

__all__ = ['FreshdeskAdapter', 'FreshdeskCollector']
