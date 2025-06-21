"""
Core 패키지

정리된 구조로 Freshdesk RAG 백엔드의 핵심 기능을 제공합니다.

구조:
- 전역: config, exceptions, logger, settings, utils 등
- database/: 데이터베이스 및 벡터DB 관련  
- data/: 데이터 처리, 검증, 병합 등
- search/: 검색, 임베딩, 최적화 등
- processing/: 컨텍스트 구성, 필터링 등
- llm/: 통합된 LLM 관리 (기존 llm + langchain 통합)
- platforms/: 플랫폼 통합 (Freshdesk 등)
- ingest/: 데이터 수집
- legacy/: 레거시 코드
"""

# 설정을 가장 먼저 로드
from .config import Settings

# 정리된 주요 모듈들
from . import database
from . import data
from . import search
from . import processing  
from . import llm
from . import platforms
from . import ingest

# 기존 전역 유틸리티들 (위치 유지)
from . import exceptions
from . import logger
from . import settings
from . import utils
from . import constants
from . import dependencies
from . import middleware
