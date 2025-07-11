"""
스트리밍 이벤트 표준 모델 정의

모든 스트리밍 응답에서 일관된 구조를 사용하도록 하는 표준 이벤트 모델들입니다.
"""

import time
import json
from typing import Any, Dict, Optional, List, Union
from pydantic import BaseModel, Field
from enum import Enum


class StreamEventType(str, Enum):
    """스트리밍 이벤트 타입 정의"""
    INIT = "init"           # 스트리밍 시작
    PROGRESS = "progress"   # 진행률 업데이트
    STAGE = "stage"         # 단계 완료
    RESULT = "result"       # 결과 데이터
    PARTIAL = "partial"     # 부분 결과 (토큰 단위 등)
    COMPLETE = "complete"   # 완전 완료
    ERROR = "error"         # 오류 발생
    HEARTBEAT = "heartbeat" # 연결 유지용


class StreamStage(str, Enum):
    """처리 단계 정의"""
    INIT = "init"
    EMBEDDING = "embedding"
    SEARCH = "search"
    TICKET_SEARCH = "ticket_search"
    KB_SEARCH = "kb_search"
    LLM_PROCESSING = "llm_processing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"


class ResultType(str, Enum):
    """결과 타입 정의"""
    TICKET = "ticket"
    KB = "kb"
    DOCUMENT = "document"
    IMAGE = "image"
    ATTACHMENT = "attachment"
    TOKEN = "token"
    SUMMARY = "summary"


class StreamEvent(BaseModel):
    """표준 스트리밍 이벤트 모델"""
    
    # 필수 필드
    type: StreamEventType = Field(description="이벤트 타입")
    timestamp: float = Field(default_factory=time.time, description="이벤트 발생 시간")
    
    # 선택적 필드
    stage: Optional[StreamStage] = Field(default=None, description="현재 처리 단계")
    message: Optional[str] = Field(default=None, description="사용자 표시용 메시지")
    progress: Optional[int] = Field(default=None, ge=0, le=100, description="진행률 (0-100)")
    
    # 결과 데이터
    result_type: Optional[ResultType] = Field(default=None, description="결과 타입")
    data: Optional[Dict[str, Any]] = Field(default=None, description="결과 데이터")
    
    # 오류 정보
    error: Optional[str] = Field(default=None, description="오류 메시지")
    error_code: Optional[str] = Field(default=None, description="오류 코드")
    
    # 메타데이터
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="추가 메타데이터")


class StreamEventBuilder:
    """스트리밍 이벤트 생성 헬퍼 클래스"""
    
    @staticmethod
    def create_init_event(message: str = "스트리밍을 시작합니다", **kwargs) -> StreamEvent:
        """초기화 이벤트 생성"""
        return StreamEvent(
            type=StreamEventType.INIT,
            stage=StreamStage.INIT,
            message=message,
            progress=0,
            **kwargs
        )
    
    @staticmethod
    def create_progress_event(
        stage: StreamStage,
        message: str,
        progress: int,
        **kwargs
    ) -> StreamEvent:
        """진행률 이벤트 생성"""
        return StreamEvent(
            type=StreamEventType.PROGRESS,
            stage=stage,
            message=message,
            progress=progress,
            **kwargs
        )
    
    @staticmethod
    def create_stage_complete_event(
        stage: StreamStage,
        message: str = None,
        **kwargs
    ) -> StreamEvent:
        """단계 완료 이벤트 생성"""
        if message is None:
            message = f"{stage.value} 단계 완료"
        
        return StreamEvent(
            type=StreamEventType.STAGE,
            stage=stage,
            message=message,
            progress=100,  # 해당 단계는 100% 완료
            **kwargs
        )
    
    @staticmethod
    def create_result_event(
        result_type: ResultType,
        data: Dict[str, Any],
        progress: int = None,
        **kwargs
    ) -> StreamEvent:
        """결과 이벤트 생성"""
        return StreamEvent(
            type=StreamEventType.RESULT,
            result_type=result_type,
            data=data,
            progress=progress,
            **kwargs
        )
    
    @staticmethod
    def create_partial_event(
        content: str,
        result_type: ResultType = ResultType.TOKEN,
        **kwargs
    ) -> StreamEvent:
        """부분 결과 이벤트 생성 (토큰 스트리밍 등)"""
        return StreamEvent(
            type=StreamEventType.PARTIAL,
            result_type=result_type,
            data={"content": content},
            **kwargs
        )
    
    @staticmethod
    def create_complete_event(
        final_data: Dict[str, Any] = None,
        **kwargs
    ) -> StreamEvent:
        """완료 이벤트 생성"""
        return StreamEvent(
            type=StreamEventType.COMPLETE,
            stage=StreamStage.COMPLETE,
            progress=100,
            data=final_data,
            **kwargs
        )
    
    @staticmethod
    def create_error_event(
        error: str,
        error_code: str = None,
        stage: StreamStage = None,
        **kwargs
    ) -> StreamEvent:
        """오류 이벤트 생성"""
        return StreamEvent(
            type=StreamEventType.ERROR,
            stage=stage,
            error=error,
            error_code=error_code,
            message=f"오류가 발생했습니다: {error}",
            **kwargs
        )
    
    @staticmethod
    def create_heartbeat_event(**kwargs) -> StreamEvent:
        """하트비트 이벤트 생성"""
        return StreamEvent(
            type=StreamEventType.HEARTBEAT,
            message="연결 유지",
            **kwargs
        )


def format_sse_event(event: StreamEvent) -> str:
    """
    StreamEvent를 Server-Sent Events 형식으로 포맷팅
    
    Args:
        event: 스트리밍 이벤트
        
    Returns:
        SSE 형식 문자열
    """
    event_data = json.dumps(event.dict(), ensure_ascii=False)
    return f"data: {event_data}\n\n"


def format_sse_done() -> str:
    """SSE 완료 이벤트 포맷팅"""
    return "data: [DONE]\n\n"


# 편의 함수들
def create_ticket_result_event(
    ticket_id: str,
    title: str,
    content: str,
    score: float = None,
    progress: int = None,
    **kwargs
) -> StreamEvent:
    """티켓 결과 이벤트 생성 편의 함수"""
    return StreamEventBuilder.create_result_event(
        result_type=ResultType.TICKET,
        data={
            "id": ticket_id,
            "title": title,
            "content": content,
            "score": score
        },
        progress=progress,
        **kwargs
    )


def create_kb_result_event(
    doc_id: str,
    title: str,
    content: str,
    score: float = None,
    progress: int = None,
    **kwargs
) -> StreamEvent:
    """KB 문서 결과 이벤트 생성 편의 함수"""
    return StreamEventBuilder.create_result_event(
        result_type=ResultType.KB,
        data={
            "id": doc_id,
            "title": title,
            "content": content,
            "score": score
        },
        progress=progress,
        **kwargs
    )