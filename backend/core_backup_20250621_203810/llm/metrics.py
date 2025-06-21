"""
Prometheus 메트릭 설정

LLM 모니터링을 위한 Prometheus 메트릭들을 정의합니다.
"""

import logging
from prometheus_client import Counter, Histogram, Gauge, REGISTRY

logger = logging.getLogger(__name__)

# Prometheus 메트릭 정의 (LLM Router 전용) - 중복 등록 방지
try:
    # 이미 등록된 메트릭이 있는지 확인하고 재사용
    llm_requests_total = REGISTRY._names_to_collectors.get("llm_requests_total")
    if llm_requests_total is None:
        llm_requests_total = Counter(
            "llm_requests_total",
            "LLM 요청 총 수",
            ["provider", "status"] # 레이블: 제공자 이름, 성공/실패 상태
        )
    
    llm_request_duration_seconds = REGISTRY._names_to_collectors.get("llm_request_duration_seconds")
    if llm_request_duration_seconds is None:
        llm_request_duration_seconds = Histogram(
            "llm_request_duration_seconds",
            "LLM 요청 처리 시간 (초)",
            ["provider"] # 레이블: 제공자 이름
        )
    
    llm_tokens_used_total = REGISTRY._names_to_collectors.get("llm_tokens_used_total")
    if llm_tokens_used_total is None:
        llm_tokens_used_total = Counter(
            "llm_tokens_used_total",
            "LLM에서 사용된 총 토큰 수 (응답 기준)",
            ["provider", "model"] # 레이블: 제공자 이름, 사용된 모델
        )
    
    llm_provider_health_status = REGISTRY._names_to_collectors.get("llm_provider_health_status")
    if llm_provider_health_status is None:
        llm_provider_health_status = Gauge(
            "llm_provider_health_status",
            "LLM 제공자 건강 상태 (1: 건강, 0: 비건강)",
            ["provider"]
        )
    
    llm_provider_consecutive_failures = REGISTRY._names_to_collectors.get("llm_provider_consecutive_failures")
    if llm_provider_consecutive_failures is None:
        llm_provider_consecutive_failures = Gauge(
            "llm_provider_consecutive_failures",
            "LLM 제공자 연속 실패 횟수",
            ["provider"]
        )
    
    llm_provider_success_rate = REGISTRY._names_to_collectors.get("llm_provider_success_rate")
    if llm_provider_success_rate is None:
        llm_provider_success_rate = Gauge(
            "llm_provider_success_rate",
            "LLM 제공자 성공률",
            ["provider"]
        )

except Exception as e:
    # fallback: 기본 메트릭 생성 (오류 발생 시)
    logger.warning(f"Prometheus 메트릭 초기화 중 오류 발생, 기본 메트릭 사용: {e}")
    llm_requests_total = Counter(
        "llm_requests_total_fallback",
        "LLM 요청 총 수 (fallback)",
        ["provider", "status"]
    )
    llm_request_duration_seconds = Histogram(
        "llm_request_duration_seconds_fallback", 
        "LLM 요청 처리 시간 (초) (fallback)",
        ["provider"]
    )
    llm_tokens_used_total = Counter(
        "llm_tokens_used_total_fallback",
        "LLM에서 사용된 총 토큰 수 (fallback)",
        ["provider", "model"]
    )
    llm_provider_health_status = Gauge(
        "llm_provider_health_status_fallback",
        "LLM 제공자 건강 상태 (fallback)",
        ["provider"]
    )
    llm_provider_consecutive_failures = Gauge(
        "llm_provider_consecutive_failures_fallback",
        "LLM 제공자 연속 실패 횟수 (fallback)",
        ["provider"]
    )
    llm_provider_success_rate = Gauge(
        "llm_provider_success_rate_fallback",
        "LLM 제공자 성공률 (fallback)",
        ["provider"]
    )


# 메트릭 객체들을 내보내기
__all__ = [
    "llm_requests_total",
    "llm_request_duration_seconds", 
    "llm_tokens_used_total",
    "llm_provider_health_status",
    "llm_provider_consecutive_failures",
    "llm_provider_success_rate"
]
