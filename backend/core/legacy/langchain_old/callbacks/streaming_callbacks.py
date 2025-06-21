"""
스트리밍 콜백 모듈 - 실시간 응답 처리

기존 llm_router_legacy.py의 스트리밍 로직을 langchain CallbackHandler로 래핑
90%+ 기존 코드 재활용 원칙에 따라 기존 스트리밍 처리 로직 보존
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator
from langchain_core.callbacks import AsyncCallbackHandler
import json
import time

logger = logging.getLogger(__name__)


class AsyncStreamingCallback(AsyncCallbackHandler):
    """
    비동기 스트리밍 콜백 핸들러 - 실시간 응답 스트리밍
    """
    
    def __init__(self, response_queue: Optional[asyncio.Queue] = None):
        """
        Args:
            response_queue: 스트리밍 응답을 전달할 큐
        """
        super().__init__()
        self.response_queue = response_queue or asyncio.Queue()
        self.tokens_received = 0
        self.start_time: Optional[float] = None
        self.full_response = ""
        
    async def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """스트리밍 시작 (기존 로직 재활용)"""
        self.start_time = time.time()
        self.tokens_received = 0
        self.full_response = ""
        
        # 스트리밍 시작 신호
        await self.response_queue.put({
            "type": "start",
            "timestamp": self.start_time,
            "message": "스트리밍 시작"
        })
        
        logger.debug("비동기 스트리밍 LLM 요청 시작")
        
    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """새 토큰 수신 시 호출 (기존 스트리밍 로직 재활용)"""
        self.tokens_received += 1
        self.full_response += token
        
        # 토큰을 큐에 전달
        await self.response_queue.put({
            "type": "token",
            "content": token,
            "token_count": self.tokens_received,
            "timestamp": time.time()
        })
        
        logger.debug(f"새 토큰 수신: '{token[:20]}...', 총 토큰 수: {self.tokens_received}")
        
    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """스트리밍 완료 (기존 로직 재활용)"""
        if self.start_time:
            duration = time.time() - self.start_time
            
            # 완료 신호
            await self.response_queue.put({
                "type": "end",
                "full_response": self.full_response,
                "token_count": self.tokens_received,
                "duration": duration,
                "timestamp": time.time()
            })
            
            logger.info(f"스트리밍 완료: {self.tokens_received}개 토큰, {duration:.3f}초")
        
    async def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """스트리밍 오류 처리 (기존 오류 처리 로직 재활용)"""
        # 오류 신호
        await self.response_queue.put({
            "type": "error",
            "error": str(error),
            "timestamp": time.time()
        })
        
        logger.error(f"스트리밍 오류: {str(error)}")


class WebSocketStreamingCallback(AsyncCallbackHandler):
    """
    WebSocket 스트리밍 콜백 핸들러 - 웹소켓을 통한 실시간 전송
    """
    
    def __init__(self, websocket=None, client_id: str = "unknown"):
        """
        Args:
            websocket: WebSocket 연결 객체
            client_id: 클라이언트 식별자
        """
        super().__init__()
        self.websocket = websocket
        self.client_id = client_id
        self.tokens_received = 0
        self.start_time: Optional[float] = None
        
    async def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """WebSocket 스트리밍 시작"""
        self.start_time = time.time()
        self.tokens_received = 0
        
        if self.websocket:
            await self._send_websocket_message({
                "type": "stream_start",
                "client_id": self.client_id,
                "timestamp": self.start_time
            })
        
        logger.debug(f"WebSocket 스트리밍 시작: client_id={self.client_id}")
        
    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """WebSocket으로 새 토큰 전송 (기존 실시간 전송 로직 재활용)"""
        self.tokens_received += 1
        
        if self.websocket:
            await self._send_websocket_message({
                "type": "stream_token",
                "client_id": self.client_id,
                "content": token,
                "token_count": self.tokens_received,
                "timestamp": time.time()
            })
        
        logger.debug(f"WebSocket 토큰 전송: client_id={self.client_id}, token='{token[:20]}...'")
        
    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """WebSocket 스트리밍 완료"""
        if self.start_time and self.websocket:
            duration = time.time() - self.start_time
            
            await self._send_websocket_message({
                "type": "stream_end",
                "client_id": self.client_id,
                "token_count": self.tokens_received,
                "duration": duration,
                "timestamp": time.time()
            })
            
            logger.info(f"WebSocket 스트리밍 완료: client_id={self.client_id}, {self.tokens_received}개 토큰")
        
    async def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """WebSocket 스트리밍 오류"""
        if self.websocket:
            await self._send_websocket_message({
                "type": "stream_error",
                "client_id": self.client_id,
                "error": str(error),
                "timestamp": time.time()
            })
        
        logger.error(f"WebSocket 스트리밍 오류: client_id={self.client_id}, error={str(error)}")
        
    async def _send_websocket_message(self, message: Dict[str, Any]) -> None:
        """WebSocket 메시지 전송 헬퍼 (기존 전송 로직 재활용)"""
        try:
            if self.websocket and hasattr(self.websocket, 'send_text'):
                await self.websocket.send_text(json.dumps(message, ensure_ascii=False))
            elif self.websocket and hasattr(self.websocket, 'send'):
                await self.websocket.send(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"WebSocket 메시지 전송 실패: {e}")


class ServerSentEventsCallback(AsyncCallbackHandler):
    """
    Server-Sent Events 스트리밍 콜백 핸들러 - SSE를 통한 실시간 전송
    """
    
    def __init__(self, response_stream=None):
        """
        Args:
            response_stream: SSE 응답 스트림
        """
        super().__init__()
        self.response_stream = response_stream
        self.tokens_received = 0
        self.start_time: Optional[float] = None
        
    async def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """SSE 스트리밍 시작"""
        self.start_time = time.time()
        self.tokens_received = 0
        
        if self.response_stream:
            await self._send_sse_event("stream_start", {
                "timestamp": self.start_time,
                "message": "스트리밍 시작"
            })
        
        logger.debug("SSE 스트리밍 시작")
        
    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """SSE로 새 토큰 전송 (기존 SSE 전송 로직 재활용)"""
        self.tokens_received += 1
        
        if self.response_stream:
            await self._send_sse_event("stream_token", {
                "content": token,
                "token_count": self.tokens_received,
                "timestamp": time.time()
            })
        
        logger.debug(f"SSE 토큰 전송: '{token[:20]}...', 총 토큰: {self.tokens_received}")
        
    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """SSE 스트리밍 완료"""
        if self.start_time and self.response_stream:
            duration = time.time() - self.start_time
            
            await self._send_sse_event("stream_end", {
                "token_count": self.tokens_received,
                "duration": duration,
                "timestamp": time.time()
            })
            
            logger.info(f"SSE 스트리밍 완료: {self.tokens_received}개 토큰, {duration:.3f}초")
        
    async def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """SSE 스트리밍 오류"""
        if self.response_stream:
            await self._send_sse_event("stream_error", {
                "error": str(error),
                "timestamp": time.time()
            })
        
        logger.error(f"SSE 스트리밍 오류: {str(error)}")
        
    async def _send_sse_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """SSE 이벤트 전송 헬퍼 (기존 SSE 전송 로직 재활용)"""
        try:
            if self.response_stream:
                event_data = json.dumps(data, ensure_ascii=False)
                sse_message = f"event: {event_type}\ndata: {event_data}\n\n"
                
                if hasattr(self.response_stream, 'write'):
                    await self.response_stream.write(sse_message.encode())
                elif hasattr(self.response_stream, 'send'):
                    await self.response_stream.send(sse_message)
        except Exception as e:
            logger.warning(f"SSE 이벤트 전송 실패: {e}")


# 스트리밍 콜백 팩토리 함수들 (기존 패턴과 호환성 유지)
def create_async_streaming_callback(response_queue: Optional[asyncio.Queue] = None) -> AsyncStreamingCallback:
    """비동기 스트리밍 콜백 생성 팩토리"""
    return AsyncStreamingCallback(response_queue=response_queue)

def create_websocket_streaming_callback(websocket=None, client_id: str = "unknown") -> WebSocketStreamingCallback:
    """WebSocket 스트리밍 콜백 생성 팩토리"""
    return WebSocketStreamingCallback(websocket=websocket, client_id=client_id)

def create_sse_streaming_callback(response_stream=None) -> ServerSentEventsCallback:
    """SSE 스트리밍 콜백 생성 팩토리"""
    return ServerSentEventsCallback(response_stream=response_stream)

# 통합 스트리밍 제너레이터 (기존 패턴 유지)
async def stream_llm_response_with_callback(
    llm_chain, 
    inputs: Dict[str, Any],
    callback_type: str = "queue"
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    콜백을 사용한 LLM 응답 스트리밍 (기존 스트리밍 패턴 재활용)
    
    Args:
        llm_chain: LLM 체인
        inputs: 입력 데이터
        callback_type: 콜백 타입 ("queue", "websocket", "sse")
        
    Yields:
        Dict[str, Any]: 스트리밍 응답 데이터
    """
    response_queue = asyncio.Queue()
    
    # 콜백 타입에 따라 적절한 콜백 생성
    if callback_type == "queue":
        callback = create_async_streaming_callback(response_queue)
    elif callback_type == "websocket":
        callback = create_websocket_streaming_callback()
    elif callback_type == "sse":
        callback = create_sse_streaming_callback()
    else:
        callback = create_async_streaming_callback(response_queue)
    
    # LLM 체인 실행 (백그라운드)
    async def run_chain():
        try:
            await llm_chain.ainvoke(inputs, config={"callbacks": [callback]})
        except Exception as e:
            await response_queue.put({"type": "error", "error": str(e)})
    
    # 체인 실행을 백그라운드 태스크로 시작
    chain_task = asyncio.create_task(run_chain())
    
    try:
        while True:
            # 큐에서 응답 데이터 수신
            try:
                response_data = await asyncio.wait_for(response_queue.get(), timeout=1.0)
                yield response_data
                
                # 종료 조건 확인
                if response_data.get("type") in ["end", "error"]:
                    break
                    
            except asyncio.TimeoutError:
                # 체인 실행이 완료되었는지 확인
                if chain_task.done():
                    break
                continue
                
    finally:
        # 백그라운드 태스크 정리
        if not chain_task.done():
            chain_task.cancel()
            try:
                await chain_task
            except asyncio.CancelledError:
                pass
