"""
콜백 모듈 - Langchain Callback 기반

기존 llm_router.py의 메트릭 및 스트리밍 로직을 langchain 구조로 분리
"""

from .metrics_callbacks import (
    MetricsCallback,
    StreamingCallback,
    ChainMetricsCallback,
    create_metrics_callback,
    create_streaming_callback,
    create_chain_metrics_callback,
    get_default_callbacks,
    # Prometheus 메트릭
    llm_requests_total,
    llm_request_duration_seconds,
    llm_tokens_used_total,
    llm_provider_health_status,
    llm_provider_consecutive_failures,
    llm_provider_success_rate
)

from .streaming_callbacks import (
    AsyncStreamingCallback,
    WebSocketStreamingCallback,
    ServerSentEventsCallback,
    create_async_streaming_callback,
    create_websocket_streaming_callback,
    create_sse_streaming_callback,
    stream_llm_response_with_callback
)

__all__ = [
    # 메트릭 콜백
    "MetricsCallback",
    "StreamingCallback", 
    "ChainMetricsCallback",
    "create_metrics_callback",
    "create_streaming_callback",
    "create_chain_metrics_callback",
    "get_default_callbacks",
    # Prometheus 메트릭
    "llm_requests_total",
    "llm_request_duration_seconds",
    "llm_tokens_used_total",
    "llm_provider_health_status",
    "llm_provider_consecutive_failures",
    "llm_provider_success_rate",
    # 스트리밍 콜백
    "AsyncStreamingCallback",
    "WebSocketStreamingCallback",
    "ServerSentEventsCallback",
    "create_async_streaming_callback",
    "create_websocket_streaming_callback",
    "create_sse_streaming_callback",
    "stream_llm_response_with_callback"
]
