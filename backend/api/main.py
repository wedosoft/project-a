"""
Multi-Platform Custom App 백엔드 서비스

이 프로젝트는 Multi-Platform Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 멀티플랫폼(Freshdesk, Zendesk 등)
티켓과 지식베이스를 기반으로 AI 기반 응답 생성 기능을 제공합니다.
"""

import logging
from cachetools import TTLCache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 환경변수 로드 (애플리케이션 시작 시 최우선 로드)
load_dotenv()

# 새로운 모듈화된 LLM 매니저 사용
from core.llm import LLMManager
from core.database.vectordb import vector_db
from core.search.hybrid import HybridSearchManager  # 하이브리드 검색 매니저 추가
from core.platforms.freshdesk import fetcher  # 하위 호환성을 위해 유지

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

# 공통 의존성 함수들 import
from .dependencies import set_global_dependencies

# 하위 호환성을 위한 기존 라우터 유지 (추후 제거 예정)
from .multi_platform_attachments import router as legacy_attachments_router

# FastAPI 앱 생성
app = FastAPI(
    title="Multi-Platform Custom App 백엔드",
    description="RAG 기반 멀티플랫폼 고객 지원 AI 서비스",
    version="1.0.0"
)

# CORS 미들웨어 설정 - Freshdesk FDK 환경에서의 크로스 도메인 요청 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용: 모든 도메인 허용 (운영시에는 특정 도메인으로 제한)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],  # 모든 헤더 허용
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
app.include_router(legacy_attachments_router)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 캐시 설정
ticket_context_cache = TTLCache(maxsize=1000, ttl=3600)  # 1시간 유효
ticket_summary_cache = TTLCache(maxsize=500, ttl=1800)  # 30분 유효

# LLMManager 인스턴스 생성 (새로운 모듈화된 구조)
llm_manager = LLMManager()

# 하이브리드 검색 매니저 초기화
hybrid_search_manager = HybridSearchManager(
    vector_db=vector_db,
    llm_router=llm_manager,  # llm_router -> llm_manager로 변경
    fetcher=fetcher
)

# 전역 의존성 설정 (라우터에서 사용하기 위해)
set_global_dependencies(
    vector_db=vector_db,
    fetcher=fetcher,
    llm_manager=llm_manager,  # 새로운 LLMManager 사용
    ticket_context_cache=ticket_context_cache,
    ticket_summary_cache=ticket_summary_cache,
    hybrid_search_manager=hybrid_search_manager  # 하이브리드 검색 매니저 추가
)

# 애플리케이션 시작 로그
logger.info("FastAPI 백엔드 서버 초기화 완료")

# 모든 엔드포인트는 routes/ 디렉터리로 분리되었습니다.
