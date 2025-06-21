"""
콜백 모듈 - Langchain Callback 기반 메트릭 수집

기존 llm_router_legacy.py의 메트릭 수집 로직을 langchain CallbackHandler로 래핑
90%+ 기존 코드 재활용 원칙에 따라 기존 Prometheus 메트릭 로직 보존
"""

import time
import logging
from typing import Any, Dict, List, Optional, Union
from langchain_core.callbacks import BaseCallbackHandler

# Langchain 전용 Prometheus 메트릭 정의 (기존 메트릭과 분리)
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, REGISTRY

logger = logging.getLogger(__name__)

# 메트릭 중복 등록 방지를 위한 헬퍼 함수
def get_or_create_metric(metric_class, name, description, labelnames=None, registry=REGISTRY):
    """
    메트릭이 이미 등록되어 있으면 기존 메트릭을 반환하고, 
    없으면 새로 생성합니다.
    """
    try:
        # 기존 메트릭이 있는지 확인
        for collector in list(registry._collector_to_names.keys()):
            if hasattr(collector, '_name') and collector._name == name:
                logger.debug(f"기존 메트릭 재사용: {name}")
                return collector
        
        # 새 메트릭 생성
        if labelnames:
            metric = metric_class(name, description, labelnames, registry=registry)
        else:
            metric = metric_class(name, description, registry=registry)
        logger.debug(f"새 메트릭 생성: {name}")
        return metric
        
    except Exception as e:
        logger.warning(f"메트릭 생성/재사용 실패 ({name}): {e}")
        # 기본 메트릭 반환 (메트릭 없이 동작)
        return None

# Langchain 전용 메트릭들 (중복 등록 방지)
langchain_llm_requests_total = get_or_create_metric(
    Counter,
    "langchain_llm_requests_total",
    "Langchain LLM 요청 총 수",
    ["provider", "status"]
)

langchain_llm_request_duration_seconds = get_or_create_metric(
    Histogram,
    "langchain_llm_request_duration_seconds", 
    "Langchain LLM 요청 처리 시간 (초)",
    ["provider"]
)

langchain_llm_tokens_used_total = get_or_create_metric(
    Counter,
    "langchain_llm_tokens_used_total",
    "Langchain LLM에서 사용된 총 토큰 수",
    ["provider", "model"]
)

langchain_llm_provider_health_status = get_or_create_metric(
    Gauge,
    "langchain_llm_provider_health_status",
    "Langchain LLM 제공자 건강 상태 (1: 건강, 0: 비건강)",
    ["provider"]
)

langchain_llm_provider_consecutive_failures = get_or_create_metric(
    Gauge,
    "langchain_llm_provider_consecutive_failures",
    "Langchain LLM 제공자 연속 실패 횟수",
    ["provider"]
)

langchain_llm_provider_success_rate = get_or_create_metric(
    Gauge,
    "langchain_llm_provider_success_rate",
    "Langchain LLM 제공자 성공률",
    ["provider"]
)

# 기존 호환성을 위한 별칭 (기존 코드에서 참조할 수 있도록)
llm_requests_total = langchain_llm_requests_total
llm_request_duration_seconds = langchain_llm_request_duration_seconds  
llm_tokens_used_total = langchain_llm_tokens_used_total
llm_provider_health_status = langchain_llm_provider_health_status
llm_provider_consecutive_failures = langchain_llm_provider_consecutive_failures
llm_provider_success_rate = langchain_llm_provider_success_rate

logger = logging.getLogger(__name__)


class MetricsCallback(BaseCallbackHandler):
    """
    메트릭 수집 콜백 핸들러 - 기존 Prometheus 메트릭 로직 재활용
    """
    
    def __init__(self, provider_name: str = "unknown"):
        """
        Args:
            provider_name: LLM 제공자 이름 (anthropic, openai, gemini 등)
        """
        super().__init__()
        self.provider_name = provider_name
        self.start_time: Optional[float] = None
        self.run_id: Optional[str] = None
        
    def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """LLM 실행 시작 시 호출 (기존 메트릭 시작 로직 재활용)"""
        self.start_time = time.time()
        logger.debug(f"LLM 요청 시작: provider={self.provider_name}")
        
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """LLM 실행 완료 시 호출 (기존 메트릭 성공 로직 재활용)"""
        if self.start_time is None:
            return
            
        # 실행 시간 계산
        duration = time.time() - self.start_time
        
        # 기존 Prometheus 메트릭 업데이트 로직 재활용 (안전성 검사 추가)
        try:
            if langchain_llm_requests_total:
                langchain_llm_requests_total.labels(provider=self.provider_name, status="success").inc()
            if langchain_llm_request_duration_seconds:
                langchain_llm_request_duration_seconds.labels(provider=self.provider_name).observe(duration)
            
            # 토큰 사용량 업데이트 (가능한 경우)
            if hasattr(response, 'llm_output') and response.llm_output:
                token_usage = response.llm_output.get('token_usage', {})
                total_tokens = token_usage.get('total_tokens', 0)
                if total_tokens > 0 and langchain_llm_tokens_used_total:
                    model_name = response.llm_output.get('model_name', 'unknown')
                    langchain_llm_tokens_used_total.labels(provider=self.provider_name, model=model_name).inc(total_tokens)
            
            # 제공자 건강 상태 업데이트 (성공)
            if langchain_llm_provider_health_status:
                langchain_llm_provider_health_status.labels(provider=self.provider_name).set(1)
            if langchain_llm_provider_consecutive_failures:
                langchain_llm_provider_consecutive_failures.labels(provider=self.provider_name).set(0)
                
        except Exception as e:
            logger.warning(f"메트릭 업데이트 실패: {e}")
        
        logger.debug(f"LLM 요청 완료: provider={self.provider_name}, duration={duration:.3f}s")
        
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """LLM 실행 오류 시 호출 (기존 메트릭 실패 로직 재활용)"""
        if self.start_time is None:
            return
            
        # 실행 시간 계산
        duration = time.time() - self.start_time
        
        # 기존 Prometheus 메트릭 업데이트 로직 재활용 (안전성 검사 추가)
        try:
            if langchain_llm_requests_total:
                langchain_llm_requests_total.labels(provider=self.provider_name, status="error").inc()
            if langchain_llm_request_duration_seconds:
                langchain_llm_request_duration_seconds.labels(provider=self.provider_name).observe(duration)
            
            # 제공자 건강 상태 업데이트 (실패)
            if langchain_llm_provider_health_status:
                langchain_llm_provider_health_status.labels(provider=self.provider_name).set(0)
            
            # 연속 실패 횟수 증가
            if langchain_llm_provider_consecutive_failures:
                langchain_llm_provider_consecutive_failures.labels(provider=self.provider_name).inc()
                
        except Exception as e:
            logger.warning(f"메트릭 업데이트 실패: {e}")
        
        logger.warning(f"LLM 요청 실패: provider={self.provider_name}, duration={duration:.3f}s, error={str(error)}")


class StreamingCallback(BaseCallbackHandler):
    """
    스트리밍 콜백 핸들러 - 실시간 응답 처리
    """
    
    def __init__(self, stream_handler=None):
        """
        Args:
            stream_handler: 스트리밍 데이터를 처리할 함수 또는 객체
        """
        super().__init__()
        self.stream_handler = stream_handler
        self.tokens_received = 0
        self.start_time: Optional[float] = None
        
    def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """스트리밍 시작"""
        self.start_time = time.time()
        self.tokens_received = 0
        logger.debug("스트리밍 LLM 요청 시작")
        
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """새 토큰 수신 시 호출 (기존 스트리밍 로직 재활용)"""
        self.tokens_received += 1
        
        # 스트림 핸들러가 있으면 토큰 전달
        if self.stream_handler:
            try:
                if callable(self.stream_handler):
                    self.stream_handler(token)
                elif hasattr(self.stream_handler, 'handle_token'):
                    self.stream_handler.handle_token(token)
            except Exception as e:
                logger.warning(f"스트림 핸들러 처리 중 오류: {e}")
        
        logger.debug(f"새 토큰 수신: '{token[:20]}...', 총 토큰 수: {self.tokens_received}")
        
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """스트리밍 완료"""
        if self.start_time:
            duration = time.time() - self.start_time
            logger.info(f"스트리밍 완료: {self.tokens_received}개 토큰, {duration:.3f}초")


class ChainMetricsCallback(BaseCallbackHandler):
    """
    체인 실행 메트릭 콜백 - 체인별 성능 추적
    """
    
    def __init__(self, chain_name: str = "unknown"):
        """
        Args:
            chain_name: 체인 이름 (init_chain, summarization_chain 등)
        """
        super().__init__()
        self.chain_name = chain_name
        self.start_time: Optional[float] = None
        
    def on_chain_start(
        self, 
        serialized: Dict[str, Any], 
        inputs: Dict[str, Any], 
        **kwargs: Any
    ) -> None:
        """체인 실행 시작"""
        self.start_time = time.time()
        logger.debug(f"체인 실행 시작: {self.chain_name}")
        
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """체인 실행 완료"""
        if self.start_time:
            duration = time.time() - self.start_time
            logger.info(f"체인 실행 완료: {self.chain_name}, 실행시간: {duration:.3f}초")
            
    def on_chain_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """체인 실행 오류"""
        if self.start_time:
            duration = time.time() - self.start_time
            logger.error(f"체인 실행 실패: {self.chain_name}, 실행시간: {duration:.3f}초, 오류: {str(error)}")


# 콜백 팩토리 함수들 (기존 패턴과 호환성 유지)
def create_metrics_callback(provider_name: str) -> MetricsCallback:
    """메트릭 콜백 생성 팩토리"""
    return MetricsCallback(provider_name=provider_name)

def create_streaming_callback(stream_handler=None) -> StreamingCallback:
    """스트리밍 콜백 생성 팩토리"""
    return StreamingCallback(stream_handler=stream_handler)

def create_chain_metrics_callback(chain_name: str) -> ChainMetricsCallback:
    """체인 메트릭 콜백 생성 팩토리"""
    return ChainMetricsCallback(chain_name=chain_name)

# 기본 콜백 리스트 생성 함수
def get_default_callbacks(provider_name: str, include_streaming: bool = False) -> List[BaseCallbackHandler]:
    """
    기본 콜백 리스트 생성 (기존 메트릭 패턴 유지)
    
    Args:
        provider_name: LLM 제공자 이름
        include_streaming: 스트리밍 콜백 포함 여부
        
    Returns:
        List[BaseCallbackHandler]: 콜백 리스트
    """
    callbacks = [create_metrics_callback(provider_name)]
    
    if include_streaming:
        callbacks.append(create_streaming_callback())
        
    return callbacks
