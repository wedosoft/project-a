"""
LLM 모델 정의 - Pydantic 기반 구조화된 모델

지침서 준수: 구조화된 요약 및 멀티테넌트 지원
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum

class LLMProvider(str, Enum):
    """LLM 제공자 열거형"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    OPENROUTER = "openrouter"

class TaskType(str, Enum):
    """작업 유형 (지침서 기반)"""
    LIGHT = "light"  # 요약, 분류 작업
    HEAVY = "heavy"  # 채팅, 복잡한 작업

class LLMRequest(BaseModel):
    """LLM 요청 모델"""
    prompt: str = Field(..., description="입력 프롬프트")
    system_prompt: Optional[str] = Field(None, description="시스템 프롬프트")
    model: Optional[str] = Field(None, description="사용할 모델")
    max_tokens: Optional[int] = Field(4096, description="최대 토큰 수")
    temperature: Optional[float] = Field(0.7, description="창의성 수준")
    company_id: str = Field(..., description="회사 ID (멀티테넌트)")
    task_type: TaskType = Field(TaskType.LIGHT, description="작업 유형")

class LLMResponse(BaseModel):
    """LLM 응답 모델"""
    content: str = Field(..., description="생성된 내용")
    provider: str = Field(..., description="사용된 제공자")
    model: str = Field(..., description="사용된 모델")
    response_time: float = Field(0.0, description="응답 시간(초)")
    tokens_used: int = Field(0, description="사용된 토큰 수")
    success: bool = Field(True, description="성공 여부")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    usage: Optional[Dict[str, Any]] = Field(None, description="토큰 사용량")
    cached: bool = Field(False, description="캐시에서 가져온 결과인지 여부")
    
    # 폴백 관련 메타데이터
    attempt_count: Optional[int] = Field(None, description="시도 횟수")
    is_fallback: Optional[bool] = Field(None, description="폴백 사용 여부")
    previous_provider_error: Optional[str] = Field(
        None, description="이전 제공자 오류"
    )
    
    # 하위 호환성을 위해 text 속성 추가
    @property
    def text(self) -> str:
        """하위 호환성을 위한 text 속성"""
        return self.content
    
    @property
    def model_used(self) -> str:
        """하위 호환성을 위한 model_used 속성"""
        return self.model

class TicketSummary(BaseModel):
    """티켓 요약 모델 (지침서 기반 구조화된 요약)"""
    problem: str = Field(..., description="고객이 겪고 있는 주요 문제")
    cause: str = Field(..., description="문제의 근본 원인 (파악된 경우)")
    solution: str = Field(..., description="제시된 해결 방법")
    result: str = Field(..., description="최종 해결 여부 및 결과")
    tags: List[str] = Field(default_factory=list, description="관련 키워드 (최대 5개)")
    company_id: str = Field(..., description="회사 ID")
    platform: str = Field("freshdesk", description="플랫폼")

class BatchRequest(BaseModel):
    """배치 요청 모델 (지침서 비용 최적화)"""
    items: List[LLMRequest] = Field(..., description="배치 처리할 요청 목록")
    batch_size: int = Field(10, description="배치 크기")
    company_id: str = Field(..., description="회사 ID")

class LLMProviderStats(BaseModel):
    """LLM 제공자 통계 모델"""
    total_requests: int = Field(0, description="총 요청 수")
    successful_requests: int = Field(0, description="성공한 요청 수")
    failed_requests: int = Field(0, description="실패한 요청 수")
    average_latency_ms: float = Field(0.0, description="평균 지연 시간(ms)")
    consecutive_failures: int = Field(0, description="연속 실패 횟수")
    total_tokens_used: int = Field(0, description="총 사용 토큰 수")
    last_error_timestamp: Optional[float] = Field(
        None, description="마지막 오류 시간(timestamp)"
    )
    
    @property
    def success_rate(self) -> float:
        """성공률 계산 (0.0 ~ 1.0)"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_response_time(self) -> float:
        """평균 응답 시간 (초 단위)"""
        return self.average_latency_ms / 1000.0

class EmbeddingResponse(BaseModel):
    """임베딩 응답 모델"""
    embedding: List[float] = Field(..., description="임베딩 벡터")
    model: str = Field(..., description="사용된 임베딩 모델")
    response_time: float = Field(0.0, description="응답 시간(초)")
    tokens_used: int = Field(0, description="사용된 토큰 수")
    cached: bool = Field(False, description="캐시에서 가져온 결과인지 여부")
    provider: str = Field("openai", description="임베딩 제공자")
    dimensions: int = Field(0, description="임베딩 차원 수")
