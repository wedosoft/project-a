"""
멀티플랫폼 데이터 수집 라우터 (통합 모듈)

이 모듈은 데이터 수집 관련 모든 엔드포인트를 통합합니다.
기능별로 분할된 서브 모듈들을 하나로 결합하여 제공합니다.

분할된 모듈들:
- ingest_progress: 진행 상황 모니터링 관련
- ingest_jobs: 작업 관리 관련  
- ingest_core: 핵심 수집 기능
"""

from fastapi import APIRouter

# 분할된 서브 라우터들 임포트
from .ingest_progress import router as progress_router
from .ingest_jobs import router as jobs_router
from .ingest_core import router as core_router

# 메인 라우터 생성
router = APIRouter(prefix="/ingest", tags=["데이터 수집"])

# 서브 라우터들을 메인 라우터에 포함
router.include_router(progress_router)
router.include_router(jobs_router) 
router.include_router(core_router)
