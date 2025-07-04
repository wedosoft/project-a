"""
메트릭스 라우터 - 개선된 버전

애플리케이션의 성능 지표와 사용량 통계를 제공하는 엔드포인트입니다.
새로운 캐싱 시스템과 에러 핸들링 통계를 포함합니다.
"""

from fastapi import APIRouter, Depends, Header
from typing import Dict, Any, Optional
import logging
import time

from ..models.responses import MetricsResponse
from ..dependencies import (
    get_platform,
    get_vector_db,
    get_domain,
    get_cache_manager,
    get_container
)
from core.errors import get_error_handler

# 라우터 생성
router = APIRouter(prefix="/metrics", tags=["메트릭스"])

# 로거 설정
logger = logging.getLogger(__name__)


@router.get("", response_model=MetricsResponse)
async def get_metrics(
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    domain: Optional[str] = Depends(get_domain),
    cache_manager = Depends(get_cache_manager),
    container = Depends(get_container)
):
    """
    향상된 애플리케이션 메트릭스 조회 엔드포인트
    
    포함되는 메트릭스:
    - 시스템 리소스 사용량
    - 캐시 성능 통계
    - 에러 발생 통계
    - 서비스별 성능 지표
    - 컨테이너 상태 정보
    
    Headers:
        X-Platform: 플랫폼 식별자 (freshdesk)
        X-Domain: 플랫폼 도메인 (선택사항)
        
    Returns:
        MetricsResponse: 종합 메트릭스 정보
    """
    start_time = time.time()
    
    try:
        # 에러 핸들링 통계
        error_handler = get_error_handler()
        error_stats = error_handler.get_error_stats()
        
        # 캐시 성능 통계
        cache_stats = cache_manager.get_all_stats()
        
        # 컨테이너 상태
        container_health = container.health_check()
        
        # 시스템 메트릭스
        system_metrics = _get_system_metrics()
        
        # 벡터 DB 메트릭스
        vector_db_metrics = _get_vector_db_metrics(vector_db)
        
        # 종합 메트릭스 데이터
        metrics_data = {
            "timestamp": time.time(),
            "platform": platform,
            "domain": domain,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "version": "2.0.0",
            
            # 시스템 메트릭스
            "system": system_metrics,
            
            # 데이터베이스 메트릭스
            "database": {
                "vector_db": vector_db_metrics
            },
            
            # 애플리케이션 메트릭스
            "application": {
                "container_status": container_health,
                "cache_performance": cache_stats,
                "error_statistics": error_stats,
                "service_health": _get_service_health_summary(container_health)
            },
            
            # 성능 메트릭스
            "performance": {
                "cache_hit_rates": _calculate_cache_hit_rates(cache_stats),
                "error_rate": _calculate_error_rate(error_stats),
                "healthy_services_count": _count_healthy_services(container_health)
            }
        }
        
        logger.info(f"📊 메트릭스 조회 완료 ({(time.time() - start_time)*1000:.2f}ms)")
        return MetricsResponse(**metrics_data)
        
    except Exception as e:
        logger.error(f"❌ 메트릭스 조회 실패: {e}")
        
        # 최소한의 메트릭스 반환
        minimal_metrics = {
            "timestamp": time.time(),
            "platform": platform,
            "domain": domain,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "version": "2.0.0",
            "error": str(e),
            "system": {},
            "database": {},
            "application": {}
        }
        
        return MetricsResponse(**minimal_metrics)


def _get_system_metrics() -> Dict[str, Any]:
    """시스템 메트릭스 수집"""
    try:
        import psutil
        
        # CPU 정보
        cpu_info = {
            "usage_percent": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count(),
            "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
        }
        
        # 메모리 정보
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent": memory.percent
        }
        
        # 디스크 정보
        disk = psutil.disk_usage('/')
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": round((disk.used / disk.total) * 100, 2)
        }
        
        return {
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info
        }
        
    except ImportError:
        return {"error": "psutil not available"}
    except Exception as e:
        return {"error": str(e)}


def _get_vector_db_metrics(vector_db) -> Dict[str, Any]:
    """벡터 DB 메트릭스 수집"""
    try:
        # 벡터 DB 타입과 기본 정보
        metrics = {
            "type": type(vector_db).__name__,
            "status": "connected"
        }
        
        # 추가 메트릭스가 있다면 수집
        if hasattr(vector_db, 'get_metrics'):
            metrics.update(vector_db.get_metrics())
        
        return metrics
        
    except Exception as e:
        return {
            "type": type(vector_db).__name__ if vector_db else "unknown",
            "status": "error",
            "error": str(e)
        }


def _get_service_health_summary(container_health: Dict[str, Any]) -> Dict[str, Any]:
    """서비스 헬스 요약 정보"""
    services = container_health.get("services", {})
    
    healthy_count = sum(
        1 for service in services.values() 
        if isinstance(service, dict) and service.get("status") == "healthy"
    )
    
    total_count = len(services)
    
    return {
        "total_services": total_count,
        "healthy_services": healthy_count,
        "unhealthy_services": total_count - healthy_count,
        "health_rate": round((healthy_count / total_count * 100), 2) if total_count > 0 else 0
    }


def _calculate_cache_hit_rates(cache_stats: Dict[str, Any]) -> Dict[str, float]:
    """캐시 히트율 계산"""
    hit_rates = {}
    
    for cache_name, stats in cache_stats.items():
        if isinstance(stats, dict) and "stats" in stats:
            cache_data = stats["stats"]
            if isinstance(cache_data, dict):
                hit_rate = cache_data.get("hit_rate", 0)
                hit_rates[cache_name] = round(hit_rate, 2)
    
    return hit_rates


def _calculate_error_rate(error_stats: Dict[str, Any]) -> float:
    """에러율 계산 (임시 - 전체 요청 수 대비)"""
    total_errors = error_stats.get("total_errors", 0)
    # 실제로는 전체 요청 수를 추적해야 하지만, 현재는 에러 수만 반환
    return total_errors


def _count_healthy_services(container_health: Dict[str, Any]) -> int:
    """정상 서비스 개수 계산"""
    services = container_health.get("services", {})
    
    healthy_count = sum(
        1 for service in services.values()
        if isinstance(service, dict) and service.get("status") == "healthy"
    )
    
    return healthy_count
