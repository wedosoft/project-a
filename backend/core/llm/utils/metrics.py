"""
메트릭 수집 모듈
"""

import time
import logging
from typing import Dict, Any
from collections import defaultdict, deque
from ..models.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class MetricsCollector:
    """LLM 메트릭 수집기"""
    
    def __init__(self):
        # 기본 통계
        self.request_counts = defaultdict(int)
        self.success_counts = defaultdict(int)
        self.failure_counts = defaultdict(int)
        self.total_latencies = defaultdict(float)
        self.total_tokens = defaultdict(int)
        
        # 최근 응답 시간 (최근 100개 유지)
        self.recent_latencies = defaultdict(lambda: deque(maxlen=100))
        
        # 최근 오류들 (최근 50개 유지)
        self.recent_errors = defaultdict(lambda: deque(maxlen=50))
        
        # 시작 시간
        self.start_time = time.time()
    
    def record_request(self, provider: LLMProvider, response: LLMResponse):
        """요청 결과 기록"""
        provider_name = provider.value
        
        # 기본 카운트
        self.request_counts[provider_name] += 1
        
        if response.success:
            self.success_counts[provider_name] += 1
        else:
            self.failure_counts[provider_name] += 1
            self.recent_errors[provider_name].append({
                "timestamp": time.time(),
                "error": response.error,
                "model": response.model
            })
        
        # 응답 시간 기록
        self.total_latencies[provider_name] += response.latency_ms
        self.recent_latencies[provider_name].append(response.latency_ms)
        
        # 토큰 사용량 기록
        if response.usage and "total_tokens" in response.usage:
            self.total_tokens[provider_name] += response.usage["total_tokens"]
        
        logger.debug(f"메트릭 기록: {provider_name} - 성공: {response.success}, 지연: {response.latency_ms:.2f}ms")
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        stats = {
            "uptime_seconds": time.time() - self.start_time,
            "providers": {}
        }
        
        for provider_name in self.request_counts.keys():
            total_requests = self.request_counts[provider_name]
            successful_requests = self.success_counts[provider_name]
            failed_requests = self.failure_counts[provider_name]
            
            # 성공률 계산
            success_rate = successful_requests / total_requests if total_requests > 0 else 0.0
            
            # 평균 응답 시간 계산
            avg_latency = (
                self.total_latencies[provider_name] / successful_requests 
                if successful_requests > 0 else 0.0
            )
            
            # 최근 평균 응답 시간
            recent_latencies = list(self.recent_latencies[provider_name])
            recent_avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0.0
            
            # 최근 오류들
            recent_errors = list(self.recent_errors[provider_name])
            
            stats["providers"][provider_name] = {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": round(success_rate, 4),
                "avg_latency_ms": round(avg_latency, 2),
                "recent_avg_latency_ms": round(recent_avg_latency, 2),
                "total_tokens": self.total_tokens[provider_name],
                "recent_errors_count": len(recent_errors),
                "recent_errors": recent_errors[-5:] if recent_errors else []  # 최근 5개만
            }
        
        return stats
    
    def get_provider_health(self, provider: LLMProvider) -> Dict[str, Any]:
        """특정 제공자의 건강 상태 반환"""
        provider_name = provider.value
        
        total_requests = self.request_counts[provider_name]
        successful_requests = self.success_counts[provider_name]
        failed_requests = self.failure_counts[provider_name]
        
        if total_requests == 0:
            return {
                "is_healthy": True,
                "success_rate": 1.0,
                "recent_avg_latency_ms": 0.0,
                "consecutive_failures": 0
            }
        
        success_rate = successful_requests / total_requests
        
        # 최근 응답 시간
        recent_latencies = list(self.recent_latencies[provider_name])
        recent_avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0.0
        
        # 연속 실패 계산 (최근 10개 요청 기준)
        consecutive_failures = 0
        recent_errors = list(self.recent_errors[provider_name])
        if recent_errors:
            latest_error_time = recent_errors[-1]["timestamp"]
            # 최근 5분 내의 오류들만 고려
            current_time = time.time()
            for error in reversed(recent_errors):
                if current_time - error["timestamp"] < 300:  # 5분
                    consecutive_failures += 1
                else:
                    break
        
        # 건강 상태 판단
        is_healthy = (
            success_rate >= 0.5 and  # 성공률 50% 이상
            consecutive_failures < 5 and  # 연속 실패 5회 미만
            recent_avg_latency < 30000  # 평균 응답 시간 30초 미만
        )
        
        return {
            "is_healthy": is_healthy,
            "success_rate": round(success_rate, 4),
            "recent_avg_latency_ms": round(recent_avg_latency, 2),
            "consecutive_failures": consecutive_failures
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.request_counts.clear()
        self.success_counts.clear()
        self.failure_counts.clear()
        self.total_latencies.clear()
        self.total_tokens.clear()
        self.recent_latencies.clear()
        self.recent_errors.clear()
        self.start_time = time.time()
        
        logger.info("메트릭 통계가 초기화되었습니다.")
