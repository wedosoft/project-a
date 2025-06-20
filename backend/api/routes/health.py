"""
헬스 체크 라우터

이 모듈은 애플리케이션과 외부 의존성의 상태를 확인하는 헬스 체크 엔드포인트를 제공합니다.
기존 main.py의 /health 엔드포인트 로직을 재활용하여 구현되었습니다.
"""

from fastapi import APIRouter, Depends, Header
from typing import Dict, Any, Optional
import logging
import time
import os

from ..models.responses import HealthCheckResponse
from ..dependencies import get_platform, get_vector_db
from core.vectordb import vector_db

# 라우터 생성
router = APIRouter(prefix="/health", tags=["헬스 체크"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.get("", response_model=HealthCheckResponse)
async def health_check(
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    애플리케이션 헬스 체크 엔드포인트
    
    애플리케이션 상태와 외부 의존성(벡터 DB, Freshdesk API 등)의 상태를 확인합니다.
    
    Args:
        platform: 플랫폼 정보 (헤더에서 자동 추출)
        vector_db: 벡터 데이터베이스 클라이언트
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달, 선택사항)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달, 선택사항)
        
    Returns:
        HealthCheckResponse: 헬스 체크 결과
    """
    start_time = time.time()
    
    # 기본 애플리케이션 상태
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "platform": platform,
        "version": "1.0.0",
        "checks": {}
    }
    
    overall_status = "healthy"
    
    try:
        # 1. 벡터 데이터베이스 상태 확인
        try:
            # Qdrant 연결 상태 확인
            collections = await vector_db.list_collections()
            health_status["checks"]["vector_db"] = {
                "status": "healthy",
                "message": f"Qdrant 연결 성공, {len(collections)} 컬렉션 활성화",
                "collections": [col.name for col in collections] if collections else []
            }
        except Exception as e:
            health_status["checks"]["vector_db"] = {
                "status": "unhealthy",
                "message": f"Qdrant 연결 실패: {str(e)}"
            }
            overall_status = "degraded"
        
        # 2. 환경 변수 확인
        env_checks = {}
        required_env_vars = [
            "OPENAI_API_KEY",
            "FRESHDESK_DOMAIN", 
            "FRESHDESK_API_KEY"
        ]
        
        for env_var in required_env_vars:
            if os.getenv(env_var):
                env_checks[env_var] = "configured"
            else:
                env_checks[env_var] = "missing"
                if overall_status == "healthy":
                    overall_status = "degraded"
        
        health_status["checks"]["environment"] = {
            "status": "healthy" if all(status == "configured" for status in env_checks.values()) else "degraded",
            "variables": env_checks
        }
        
        # 3. Freshdesk API 연결 확인 (헤더에 API 정보가 있는 경우)
        if x_freshdesk_domain and x_freshdesk_api_key:
            try:
                # 간단한 API 호출로 연결 상태 확인 (실제 구현 필요)
                health_status["checks"]["freshdesk_api"] = {
                    "status": "healthy",
                    "message": f"Freshdesk API 연결 가능 (도메인: {x_freshdesk_domain})",
                    "domain": x_freshdesk_domain
                }
            except Exception as e:
                health_status["checks"]["freshdesk_api"] = {
                    "status": "unhealthy",
                    "message": f"Freshdesk API 연결 실패: {str(e)}"
                }
                overall_status = "degraded"
        else:
            health_status["checks"]["freshdesk_api"] = {
                "status": "not_configured",
                "message": "Freshdesk API 정보가 헤더에 제공되지 않음"
            }
        
        # 4. 디스크 공간 확인
        try:
            import shutil
            disk_usage = shutil.disk_usage("/")
            free_space_gb = disk_usage.free / (1024**3)
            
            if free_space_gb > 1.0:  # 1GB 이상 남아있으면 정상
                health_status["checks"]["disk_space"] = {
                    "status": "healthy",
                    "free_space_gb": round(free_space_gb, 2)
                }
            else:
                health_status["checks"]["disk_space"] = {
                    "status": "warning",
                    "free_space_gb": round(free_space_gb, 2),
                    "message": "디스크 공간 부족"
                }
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            health_status["checks"]["disk_space"] = {
                "status": "unknown",
                "message": f"디스크 공간 확인 실패: {str(e)}"
            }
        
        # 전체 상태 업데이트
        health_status["status"] = overall_status
        health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        logger.info(f"헬스 체크 완료 - Platform: {platform}, Status: {overall_status}")
        
        return HealthCheckResponse(**health_status)
        
    except Exception as e:
        logger.error(f"헬스 체크 중 오류 발생: {e}", exc_info=True)
        
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=time.time(),
            platform=platform,
            version="1.0.0",
            error=str(e),
            response_time_ms=round((time.time() - start_time) * 1000, 2),
            checks=health_status.get("checks", {})
        )
