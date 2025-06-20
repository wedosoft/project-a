"""
메트릭스 라우터

이 모듈은 애플리케이션의 성능 지표와 사용량 통계를 제공하는 엔드포인트를 담당합니다.
기존 main.py의 /metrics 엔드포인트 로직을 재활용하여 구현되었습니다.
"""

from fastapi import APIRouter, Depends, Header
from typing import Dict, Any, Optional
import logging
import psutil
import time

from ..models.responses import MetricsResponse
from ..dependencies import get_platform, get_vector_db

# 라우터 생성
router = APIRouter(prefix="/metrics", tags=["메트릭스"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.get("", response_model=MetricsResponse)
async def get_metrics(
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain")
):
    """
    애플리케이션 메트릭스 조회 엔드포인트
    
    시스템 리소스 사용량, 벡터 DB 통계, 애플리케이션 성능 지표 등을 제공합니다.
    
    Args:
        platform: 플랫폼 정보 (헤더에서 자동 추출)
        vector_db: 벡터 데이터베이스 클라이언트
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달, 선택사항)
        
    Returns:
        MetricsResponse: 메트릭스 정보
    """
    start_time = time.time()
    
    try:
        metrics_data = {
            "timestamp": time.time(),
            "platform": platform,
            "system": {},
            "database": {},
            "application": {}
        }
        
        # 1. 시스템 메트릭스
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            
            metrics_data["system"] = {
                "cpu_percent": cpu_percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_percent": round((disk.used / disk.total) * 100, 2)
            }
            
        except Exception as e:
            logger.warning(f"시스템 메트릭스 수집 실패: {e}")
            metrics_data["system"] = {"error": str(e)}
        
        # 2. 벡터 데이터베이스 메트릭스
        try:
            collections = await vector_db.list_collections()
            db_metrics = {
                "total_collections": len(collections),
                "collections": []
            }
            
            total_vectors = 0
            for collection in collections:
                try:
                    # 컬렉션 정보 조회
                    info = await vector_db.get_collection_info(collection.name)
                    collection_metrics = {
                        "name": collection.name,
                        "vectors_count": info.vectors_count if hasattr(info, 'vectors_count') else 0,
                        "status": "active"
                    }
                    total_vectors += collection_metrics["vectors_count"]
                    db_metrics["collections"].append(collection_metrics)
                except Exception as e:
                    logger.warning(f"컬렉션 {collection.name} 메트릭스 수집 실패: {e}")
                    db_metrics["collections"].append({
                        "name": collection.name,
                        "status": "error",
                        "error": str(e)
                    })
            
            db_metrics["total_vectors"] = total_vectors
            metrics_data["database"] = db_metrics
            
        except Exception as e:
            logger.warning(f"벡터 DB 메트릭스 수집 실패: {e}")
            metrics_data["database"] = {"error": str(e)}
        
        # 3. 애플리케이션 메트릭스
        try:
            # 프로세스 정보
            process = psutil.Process()
            
            app_metrics = {
                "uptime_seconds": round(time.time() - process.create_time(), 2),
                "memory_usage_mb": round(process.memory_info().rss / (1024**2), 2),
                "cpu_percent": process.cpu_percent(),
                "threads_count": process.num_threads(),
                "open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0
            }
            
            # Freshdesk 연결 정보 (헤더에서 제공된 경우)
            if x_freshdesk_domain:
                app_metrics["freshdesk_domain"] = x_freshdesk_domain
                app_metrics["freshdesk_configured"] = True
            else:
                app_metrics["freshdesk_configured"] = False
            
            metrics_data["application"] = app_metrics
            
        except Exception as e:
            logger.warning(f"애플리케이션 메트릭스 수집 실패: {e}")
            metrics_data["application"] = {"error": str(e)}
        
        # 응답 시간 측정
        metrics_data["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        logger.info(f"메트릭스 수집 완료 - Platform: {platform}")
        
        return MetricsResponse(**metrics_data)
        
    except Exception as e:
        logger.error(f"메트릭스 수집 중 오류 발생: {e}", exc_info=True)
        
        return MetricsResponse(
            timestamp=time.time(),
            platform=platform,
            error=str(e),
            response_time_ms=round((time.time() - start_time) * 1000, 2),
            system={},
            database={},
            application={}
        )
