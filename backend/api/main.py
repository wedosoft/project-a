"""
Copilot Canvas 백엔드 서비스

Copilot Canvas를 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 
기반으로 AI 기반 응답 생성 기능을 제공합니다.

아키텍처 개선사항:
- IoC (Inversion of Control) 컨테이너 패턴 적용
- 의존성 주입 개선
- 성능 최적화된 캐싱 전략
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 환경변수 로드 (애플리케이션 시작 시 최우선 로드)
load_dotenv()

# 새로운 IoC 컨테이너 사용
from core.container import get_container
from core.errors import ErrorHandlingMiddleware, get_error_handler
from core.middleware import PerformanceMiddleware

# 분리된 라우터들 import
from .routes import (
    init_router,
    query_router,
    reply_router,
    ingest_router,
    health_router,
    metrics_router,
    attachments_router
)

# 하위 호환성을 위한 기존 라우터 유지 (추후 제거 예정)
from .freshdesk_attachments import router as freshdesk_attachments_router

# 환경변수에서 로그 레벨 읽기 (기본값: INFO)
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level_mapping = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# 로깅 설정
logging.basicConfig(
    level=log_level_mapping.get(log_level, logging.INFO),
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리
    
    FastAPI 앱 시작과 종료 시 필요한 작업들을 수행합니다.
    """
    # 시작 시 실행
    logger.info("🚀 Copilot Canvas 백엔드 서버 시작...")
    
    try:
        # IoC 컨테이너 초기화
        container = await get_container()
        await container.initialize()
        
        # 건강 상태 확인
        health_status = container.health_check()
        logger.debug(f"📊 서비스 상태: {health_status}")
        
        logger.info("✅ 백엔드 서버 초기화 완료")
        
        yield  # 앱 실행
        
    except Exception as e:
        logger.error(f"❌ 서버 초기화 실패: {e}")
        raise
    
    finally:
        # 종료 시 실행
        logger.info("🛑 백엔드 서버 종료 중...")
        try:
            container = await get_container()
            await container.shutdown()
            logger.info("✅ 백엔드 서버 종료 완료")
        except Exception as e:
            logger.error(f"❌ 서버 종료 중 오류: {e}")


# FastAPI 앱 생성 - 새로운 생명주기 관리 적용
app = FastAPI(
    title="Copilot Canvas 백엔드",
    description="RAG 기반 Freshdesk 고객 지원 AI 서비스 (아키텍처 개선 버전)",
    version="2.0.0",
    lifespan=lifespan
)

# 성능 최적화 미들웨어 추가 (가장 먼저)
app.add_middleware(PerformanceMiddleware, enable_detailed_logging=True)

# 에러 핸들링 미들웨어 추가
app.add_middleware(ErrorHandlingMiddleware, error_handler=get_error_handler())

# CORS 미들웨어 설정 - Freshdesk FDK 환경에서의 크로스 도메인 요청 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용: 모든 도메인 허용 (운영시에는 Freshdesk 도메인으로 제한)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 분리된 라우터들 등록
app.include_router(init_router)
app.include_router(query_router)
app.include_router(reply_router)
app.include_router(ingest_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(attachments_router)

# 하위 호환성을 위한 기존 라우터 유지 (추후 제거 예정)
app.include_router(freshdesk_attachments_router)
