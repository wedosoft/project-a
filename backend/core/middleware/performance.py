"""
성능 최적화 미들웨어

요청 처리 성능 모니터링, 응답 시간 추적, 처리량 최적화를 제공합니다.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """요청 메트릭스"""
    path: str
    method: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    status_code: Optional[int] = None
    content_length: Optional[int] = None
    
    def __post_init__(self):
        if self.end_time and self.duration is None:
            self.duration = self.end_time - self.start_time


@dataclass
class PerformanceStats:
    """성능 통계"""
    total_requests: int = 0
    total_response_time: float = 0.0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    requests_per_second: float = 0.0
    error_count: int = 0
    success_count: int = 0
    recent_requests: deque = field(default_factory=lambda: deque(maxlen=100))
    endpoint_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def update(self, metrics: RequestMetrics):
        """메트릭스 업데이트"""
        self.total_requests += 1
        
        if metrics.duration:
            self.total_response_time += metrics.duration
            self.avg_response_time = self.total_response_time / self.total_requests
            self.min_response_time = min(self.min_response_time, metrics.duration)
            self.max_response_time = max(self.max_response_time, metrics.duration)
        
        # 성공/에러 카운트
        if metrics.status_code and metrics.status_code >= 400:
            self.error_count += 1
        else:
            self.success_count += 1
        
        # 최근 요청 추가
        self.recent_requests.append(metrics)
        
        # 엔드포인트별 통계 업데이트
        endpoint_key = f"{metrics.method} {metrics.path}"
        if endpoint_key not in self.endpoint_stats:
            self.endpoint_stats[endpoint_key] = {
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "errors": 0
            }
        
        endpoint_stat = self.endpoint_stats[endpoint_key]
        endpoint_stat["count"] += 1
        
        if metrics.duration:
            endpoint_stat["total_time"] += metrics.duration
            endpoint_stat["avg_time"] = endpoint_stat["total_time"] / endpoint_stat["count"]
        
        if metrics.status_code and metrics.status_code >= 400:
            endpoint_stat["errors"] += 1
        
        # RPS 계산 (최근 60초 기준)
        self._calculate_rps()
    
    def _calculate_rps(self):
        """최근 60초 기준 RPS 계산"""
        current_time = time.time()
        recent_count = sum(
            1 for req in self.recent_requests
            if current_time - req.start_time <= 60
        )
        self.requests_per_second = recent_count / 60


class PerformanceMiddleware(BaseHTTPMiddleware):
    """성능 최적화 미들웨어"""
    
    def __init__(self, app, enable_detailed_logging: bool = True):
        super().__init__(app)
        self.enable_detailed_logging = enable_detailed_logging
        self.stats = PerformanceStats()
        self.slow_request_threshold = 2.0  # 2초 이상은 느린 요청으로 간주
        
        # 긴 처리 시간이 예상되는 경로들 (데이터 수집, 요약 생성 등)
        self.long_running_paths = {
            '/ingest': 300.0,  # 5분
            '/ingest/': 300.0,  # 5분
            '/sync-summaries': 180.0,  # 3분
            '/summarize': 120.0,  # 2분
        }
        
        # 패턴 매칭을 위한 경로 프리픽스들
        self.long_running_prefixes = [
            '/ingest',  # /ingest 로 시작하는 모든 경로
            '/sync-summaries',
            '/summarize',
        ]
        
        logger.info("🚀 성능 최적화 미들웨어 초기화 완료")
    
    async def dispatch(self, request: Request, call_next):
        """요청 처리 및 성능 모니터링"""
        start_time = time.time()
        
        # 요청 메트릭스 초기화
        metrics = RequestMetrics(
            path=request.url.path,
            method=request.method,
            start_time=start_time
        )
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 응답 메트릭스 완성
            end_time = time.time()
            metrics.end_time = end_time
            metrics.duration = end_time - start_time
            metrics.status_code = response.status_code
            
            # Content-Length 헤더 확인
            if hasattr(response, 'headers') and 'content-length' in response.headers:
                metrics.content_length = int(response.headers['content-length'])
            
            # 통계 업데이트
            self.stats.update(metrics)
            
            # 상세 로깅
            if self.enable_detailed_logging:
                self._log_request(metrics)
            
            # 느린 요청 경고 (경로별 임계값 적용)
            current_threshold = self.slow_request_threshold
            
            # 정확한 경로 매칭 먼저 시도
            if metrics.path in self.long_running_paths:
                current_threshold = self.long_running_paths[metrics.path]
            else:
                # 프리픽스 매칭으로 긴 처리 시간 경로 확인
                for prefix in self.long_running_prefixes:
                    if metrics.path.startswith(prefix):
                        current_threshold = 300.0  # 기본 5분
                        break
            
            if metrics.duration > current_threshold:
                # 데이터 수집 작업의 경우 더 관대한 로깅
                if any(metrics.path.startswith(prefix) for prefix in self.long_running_prefixes):
                    logger.info(
                        f"🐌 긴 작업 완료: {metrics.method} {metrics.path} - "
                        f"{metrics.duration:.3f}s (데이터 처리 작업)"
                    )
                else:
                    logger.warning(
                        f"🐌 느린 요청 감지: {metrics.method} {metrics.path} - "
                        f"{metrics.duration:.3f}s (임계값: {current_threshold}s)",
                        extra={
                            "slow_request": True,
                            "duration": metrics.duration,
                            "threshold": current_threshold
                        }
                    )
            
            # 성능 헤더 추가
            response.headers["X-Response-Time"] = f"{metrics.duration:.3f}s"
            response.headers["X-Request-ID"] = f"req_{int(start_time * 1000000)}"
            
            return response
            
        except Exception as error:
            # 에러 메트릭스 완성
            end_time = time.time()
            metrics.end_time = end_time
            metrics.duration = end_time - start_time
            metrics.status_code = 500  # 에러 추정
            
            # 통계 업데이트
            self.stats.update(metrics)
            
            # 에러 로깅
            logger.error(
                f"❌ 요청 처리 중 에러: {metrics.method} {metrics.path} - "
                f"{type(error).__name__} ({metrics.duration:.3f}s)",
                extra={
                    "error_type": type(error).__name__,
                    "duration": metrics.duration
                }
            )
            
            raise error
    
    def _log_request(self, metrics: RequestMetrics):
        """요청 로깅"""
        if metrics.status_code >= 400:
            log_level = logging.WARNING
            emoji = "⚠️"
        elif metrics.duration > 1.0:  # 1초 이상
            log_level = logging.INFO
            emoji = "🐌"
        else:
            log_level = logging.INFO
            emoji = "✅"
        
        logger.log(
            log_level,
            f"{emoji} {metrics.method} {metrics.path} - "
            f"{metrics.status_code} ({metrics.duration:.3f}s)",
            extra={
                "method": metrics.method,
                "path": metrics.path,
                "status_code": metrics.status_code,
                "duration": metrics.duration,
                "content_length": metrics.content_length
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        return {
            "overview": {
                "total_requests": self.stats.total_requests,
                "avg_response_time": round(self.stats.avg_response_time, 3),
                "min_response_time": round(self.stats.min_response_time, 3) if self.stats.min_response_time != float('inf') else 0,
                "max_response_time": round(self.stats.max_response_time, 3),
                "requests_per_second": round(self.stats.requests_per_second, 2),
                "error_rate": round((self.stats.error_count / max(self.stats.total_requests, 1)) * 100, 2),
                "success_rate": round((self.stats.success_count / max(self.stats.total_requests, 1)) * 100, 2)
            },
            "endpoint_stats": self.stats.endpoint_stats,
            "recent_requests_count": len(self.stats.recent_requests),
            "slow_request_threshold": self.slow_request_threshold
        }
    
    def get_top_slow_endpoints(self, limit: int = 5) -> list:
        """가장 느린 엔드포인트 반환"""
        sorted_endpoints = sorted(
            self.stats.endpoint_stats.items(),
            key=lambda x: x[1].get("avg_time", 0),
            reverse=True
        )
        
        return [
            {
                "endpoint": endpoint,
                "avg_time": round(stats["avg_time"], 3),
                "count": stats["count"],
                "errors": stats["errors"]
            }
            for endpoint, stats in sorted_endpoints[:limit]
        ]
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = PerformanceStats()
        logger.info("📊 성능 통계가 초기화되었습니다")
    
    def health_check(self) -> Dict[str, Any]:
        """미들웨어 건강 상태 확인"""
        return {
            "status": "healthy",
            "stats": self.get_stats(),
            "middleware": "PerformanceMiddleware",
            "detailed_logging": self.enable_detailed_logging
        }
