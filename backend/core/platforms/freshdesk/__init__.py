# -*- coding: utf-8 -*-
"""
Freshdesk 플랫폼 모듈

Freshdesk API 연동, 데이터 수집, 최적화된 페처 등을 통합 관리합니다.

통합된 기능들:
- adapter.py, collector.py: 기존 플랫폼 어댑터
- fetcher.py: 기본 Freshdesk 데이터 페처
- optimized_fetcher.py: 최적화된 데이터 페처  
- config.py: 대규모 컬렉션 설정 (구 large_scale_config.py)
- run_collection.py: 컬렉션 실행
- scripts/: 유틸리티 스크립트들
"""

from .adapter import FreshdeskAdapter
from .collector import FreshdeskCollector

# 새롭게 통합된 모듈들
try:
    from .fetcher import *
    from .optimized_fetcher import *
    from .config import *
except ImportError:
    # 아직 임포트가 수정되지 않은 경우 무시
    pass

__all__ = ['FreshdeskAdapter', 'FreshdeskCollector']
