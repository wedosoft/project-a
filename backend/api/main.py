"""
Freshdesk AI Assistant 백엔드 서비스

🎯 Anthropic 프롬프트 엔지니어링 시스템을 포함한 고품질 AI 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술과 Constitutional AI를 활용하여 
Freshdesk 티켓과 지식베이스를 기반으로 AI 기반 응답 생성 기능을 제공합니다.

주요 기능:
- 🧠 Constitutional AI (Helpful, Harmless, Honest)
- 📝 XML 구조화된 일관된 응답
- 🛡️ 다차원 품질 검증 시스템
- ⚡ 실시간 고성능 처리
- 🎨 관리자 친화적 프롬프트 관리

아키텍처 개선사항:
- IoC (Inversion of Control) 컨테이너 패턴 적용
- 의존성 주입 개선
- 성능 최적화된 캐싱 전략
- Anthropic 프롬프트 엔지니어링 통합
"""

import sys
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 🚀 uvicorn 호환성을 위한 Python 경로 설정
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
    
# 환경변수 설정
os.environ['PYTHONPATH'] = str(backend_dir)

# 환경변수 로드 (애플리케이션 시작 시 최우선 로드)
load_dotenv()

# 🧠 Anthropic 시스템 상태 확인
anthropic_enabled = os.getenv('ENABLE_ANTHROPIC_PROMPTS', 'false').lower() == 'true'
print(f"🧠 Anthropic 프롬프트 엔지니어링: {'✅ 활성화' if anthropic_enabled else '❌ 비활성화'}")
print(f"📁 Backend 경로: {backend_dir}")
print(f"🐍 Python 경로 설정 완료")

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
from .routes.agents import router as agents_router
from .routes.licenses import router as licenses_router
from .routes.admin_system import router as admin_system_router

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
app.include_router(agents_router)
app.include_router(licenses_router)
app.include_router(admin_system_router)

# 하위 호환성을 위한 기존 라우터 유지 (추후 제거 예정)
app.include_router(freshdesk_attachments_router)
