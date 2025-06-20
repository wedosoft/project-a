"""
API 라우트 모듈 초기화

모든 라우트 모듈을 중앙에서 관리합니다.
"""

from .init import router as init_router
from .query import router as query_router
from .reply import router as reply_router
from .ingest import router as ingest_router
from .health import router as health_router
from .metrics import router as metrics_router
from .attachments import router as attachments_router

__all__ = [
    "init_router", 
    "query_router", 
    "reply_router", 
    "ingest_router",
    "health_router",
    "metrics_router", 
    "attachments_router"
]
