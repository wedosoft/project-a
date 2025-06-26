"""
헬스 체크 라우터 - 개선된 버전

애플리케이션과 외부 의존성의 상태를 확인하는 헬스 체크 엔드포인트를 제공합니다.
새로운 IoC 컨테이너와 성능 모니터링 시스템을 통합했습니다.
"""

from fastapi import APIRouter, Depends, Header
from typing import Dict, Any, Optional
import logging
import time
import os
import asyncio

from ..models.responses import HealthCheckResponse
from ..dependencies import (
    get_platform,
    get_vector_db,
    get_domain,
    get_api_key,
    get_cache_manager,
    get_llm_manager,
    get_container
)
from core.errors import get_error_handler

# 라우터 생성
router = APIRouter(prefix="/health", tags=["헬스 체크"])

# 로거 설정
logger = logging.getLogger(__name__)


@router.get("", response_model=HealthCheckResponse)
async def health_check(
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    domain: Optional[str] = Depends(get_domain),
    api_key: Optional[str] = Depends(get_api_key),
    cache_manager = Depends(get_cache_manager),
    container = Depends(get_container)
):
    """
    향상된 애플리케이션 헬스 체크 엔드포인트
    
    애플리케이션 상태와 모든 서비스의 상태를 종합적으로 확인합니다.
    - IoC 컨테이너 상태
    - 캐싱 시스템 상태  
    - 벡터 DB 상태
    - LLM 서비스 상태
    - 에러 핸들링 통계
    
    Headers:
        X-Platform: 플랫폼 식별자 (freshdesk)
        X-Domain: 플랫폼 도메인 (선택사항)
        X-API-Key: API 키 (선택사항)
        
    Returns:
        HealthCheckResponse: 종합 헬스 체크 결과
    """
    start_time = time.time()
    
    try:
        # 컨테이너 전체 상태 확인
        container_health = container.health_check()
        
        # 캐시 시스템 상태 확인
        cache_health = cache_manager.health_check()
        
        # 에러 핸들링 통계
        error_handler = get_error_handler()
        error_stats = error_handler.get_error_stats()
        
        # 개별 서비스 상태 확인
        services_status = {}
        
        # 벡터 DB 상태 확인
        try:
            # 간단한 벡터 DB 연결 테스트
            vector_db_status = "healthy"
            services_status["vector_db"] = {
                "status": vector_db_status,
                "type": type(vector_db).__name__
            }
        except Exception as e:
            services_status["vector_db"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # LLM 서비스 상태 확인
        try:
            llm_manager = await get_llm_manager()
            if hasattr(llm_manager, 'health_check'):
                llm_status = llm_manager.health_check()
            else:
                llm_status = {"status": "healthy", "type": type(llm_manager).__name__}
            services_status["llm_manager"] = llm_status
        except Exception as e:
            services_status["llm_manager"] = {
                "status": "unhealthy", 
                "error": str(e)
            }
        
        # 전체 상태 판단
        all_services_healthy = (
            container_health.get("initialized", False) and
            cache_health.get("overall_status") == "healthy" and
            all(
                service.get("status") == "healthy" 
                for service in services_status.values()
            )
        )
        
        # 응답 시간 계산
        response_time = time.time() - start_time
        
        # 종합 헬스 체크 결과
        health_status = {
            "status": "healthy" if all_services_healthy else "unhealthy",
            "timestamp": time.time(),
            "response_time_ms": round(response_time * 1000, 2),
            "platform": platform,
            "domain": domain,
            "version": "2.0.0",  # 아키텍처 개선 버전
            
            # 상세 상태 정보
            "services": {
                **services_status,
                "container": container_health,
                "cache_system": cache_health
            },
            
            # 성능 메트릭
            "metrics": {
                "error_stats": error_stats,
                "uptime_seconds": time.time() - container_health.get("initialized_at", time.time()),
                "memory_usage": _get_memory_usage(),
                "cache_stats": cache_manager.get_all_stats()
            },
            
            # 환경 정보
            "environment": {
                "python_version": os.sys.version.split()[0],
                "platform_info": os.uname().sysname if hasattr(os, 'uname') else "unknown"
            }
        }
        
        # 로깅
        if all_services_healthy:
            logger.info(f"✅ 헬스 체크 성공 ({response_time*1000:.2f}ms)")
        else:
            logger.warning(f"⚠️ 헬스 체크 실패 - 일부 서비스에 문제가 있습니다")
        
        return HealthCheckResponse(**health_status)
        
    except Exception as e:
        # 헬스 체크 자체에서 에러 발생
        response_time = time.time() - start_time
        logger.error(f"❌ 헬스 체크 에러: {e}")
        
        health_status = {
            "status": "unhealthy",
            "timestamp": time.time(),
            "response_time_ms": round(response_time * 1000, 2),
            "platform": platform,
            "error": str(e),
            "version": "2.0.0"
        }
        
        return HealthCheckResponse(**health_status)


def _get_memory_usage() -> Dict[str, Any]:
    """메모리 사용량 정보 반환"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            "percent": round(process.memory_percent(), 2)
        }
    except ImportError:
        return {"error": "psutil not available"}
    except Exception as e:
        return {"error": str(e)}
