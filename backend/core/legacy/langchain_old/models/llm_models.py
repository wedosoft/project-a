"""
LLM 응답 및 통계 모델 정의

기존 llm_manager.py에서 분리한 모델 클래스들
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# 메트릭 임포트
try:
    from prometheus_client import REGISTRY
    llm_provider_consecutive_failures = REGISTRY._names_to_collectors.get("llm_provider_consecutive_failures")
    llm_provider_success_rate = REGISTRY._names_to_collectors.get("llm_provider_success_rate")
except (ImportError, AttributeError):
    llm_provider_consecutive_failures = None
    llm_provider_success_rate = None


class LLMResponse(BaseModel):
    """LLM 응답 모델 - 기존과 동일"""
    text: str
    model_used: str
    duration_ms: float
    tokens_used: Optional[int] = None
    tokens_total: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = 1 
    is_fallback: bool = False
    previous_provider_error: Optional[str] = None

    model_config = {
        "protected_namespaces": ()
    }


class LLMProviderStats(BaseModel):
    """LLM 제공자별 통계 데이터 모델 - 기존과 동일"""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    total_tokens_used: int = 0
    total_latency_ms: float = 0.0
    last_error_timestamp: Optional[float] = None
    error_details: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """성공률 계산 - 기존과 동일"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property 
    def average_latency_ms(self) -> float:
        """평균 지연 시간 계산 - 기존과 동일"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def add_request_stats(self, duration_ms: float, tokens_used: Optional[int], success: bool, error_info: Optional[Dict[str, Any]] = None):
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        if tokens_used is not None:
            self.total_tokens_used += tokens_used

        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            if error_info:
                self.error_details.append(error_info)

    def record_success(self, duration_ms: float = 0.0):
        """성공 기록 - 기존과 동일"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.total_latency_ms += duration_ms
        
        # 메트릭 업데이트 (안전하게 처리)
        if llm_provider_consecutive_failures:
            llm_provider_consecutive_failures.labels(provider=self.provider_name).set(self.consecutive_failures)
        if llm_provider_success_rate:
            llm_provider_success_rate.labels(provider=self.provider_name).set(self.success_rate)

    def record_failure(self, duration_ms: float = 0.0, error_detail: str = None):
        """실패 기록 - 기존과 동일"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_error_timestamp = time.time()
        if error_detail:
            self.error_details.append({
                "timestamp": self.last_error_timestamp,
                "error": error_detail
            })
            # 최근 10개 오류만 유지
            if len(self.error_details) > 10:
                self.error_details = self.error_details[-10:]

        # 메트릭 업데이트 (안전하게 처리)
        if llm_provider_consecutive_failures:
            llm_provider_consecutive_failures.labels(provider=self.provider_name).set(self.consecutive_failures)
        if llm_provider_success_rate:
            llm_provider_success_rate.labels(provider=self.provider_name).set(self.success_rate)
