"""
API Response 모델 정의

모든 API 엔드포인트의 Response 모델들을 정의합니다.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from .shared import DocumentInfo, TicketSummaryContent, SimilarTicketItem


class HealthCheckResponse(BaseModel):
    """헬스 체크 응답 모델"""
    
    status: str = Field(description="전체 상태 ('healthy', 'degraded', 'unhealthy')")
    timestamp: float = Field(description="헬스 체크 실행 시각 (Unix timestamp)")
    platform: str = Field(description="플랫폼 정보")
    version: str = Field(description="애플리케이션 버전")
    response_time_ms: Optional[float] = Field(default=None, description="응답 시간 (밀리초)")
    error: Optional[str] = Field(default=None, description="오류 메시지")
    checks: Dict[str, Any] = Field(default_factory=dict, description="세부 체크 결과")


class MetricsResponse(BaseModel):
    """메트릭스 응답 모델"""
    
    timestamp: float = Field(description="메트릭스 수집 시각 (Unix timestamp)")
    platform: str = Field(description="플랫폼 정보")
    response_time_ms: Optional[float] = Field(default=None, description="응답 시간 (밀리초)")
    error: Optional[str] = Field(default=None, description="오류 메시지")
    system: Dict[str, Any] = Field(default_factory=dict, description="시스템 메트릭스")
    database: Dict[str, Any] = Field(default_factory=dict, description="데이터베이스 메트릭스")
    application: Dict[str, Any] = Field(default_factory=dict, description="애플리케이션 메트릭스")


class QueryResponse(BaseModel):
    """쿼리 응답 모델"""
    
    answer: str
    context_docs: List[DocumentInfo]
    context_images: List[dict] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """데이터 수집 응답 모델"""
    
    success: bool
    message: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    documents_processed: Optional[int] = None
    error: Optional[str] = None


class IngestJobResponse(BaseModel):
    """데이터 수집 작업 응답 모델 (비동기)"""
    
    job_id: str = Field(description="작업 ID")
    status: str = Field(description="작업 상태")
    created_at: str = Field(description="생성 시각")
    started_at: Optional[str] = Field(default=None, description="시작 시각")
    message: str = Field(description="응답 메시지")
    progress: Dict[str, Any] = Field(default_factory=dict, description="진행상황")
    can_control: bool = Field(default=True, description="제어 가능 여부")


class JobControlResponse(BaseModel):
    """작업 제어 응답 모델"""
    
    success: bool = Field(description="제어 성공 여부")
    message: str = Field(description="응답 메시지")
    job_id: str = Field(description="작업 ID")
    action: str = Field(description="수행된 액션")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="실행 시각")


class InitResponse(BaseModel):
    """통합된 티켓 초기화 응답 모델"""

    ticket_id: str = Field(description="처리 대상 티켓의 ID")
    # 티켓 원본 데이터
    ticket_data: Dict[str, Any] = Field(
        default_factory=dict, description="티켓 원본 데이터"
    )
    # 티켓 요약 정보
    ticket_summary: Optional[TicketSummaryContent] = Field(
        default=None, description="티켓 요약 정보"
    )
    # 유사 티켓 정보
    similar_tickets: List[SimilarTicketItem] = Field(
        default_factory=list, description="유사 티켓 목록"
    )
    # 관련 지식베이스 문서
    kb_documents: List[DocumentInfo] = Field(
        default_factory=list, description="지식베이스 문서 목록"
    )
    # 향후 요청을 위한 컨텍스트 ID
    context_id: str = Field(description="컨텍스트 ID")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="메타데이터"
    )


class GenerateReplyResponse(BaseModel):
    """응답 생성 응답 모델"""
    
    reply_text: str  # 생성된 응답 텍스트
    context_docs: List[DocumentInfo]  # 참조된 문서 목록
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 메타데이터


class AttachmentUploadResponse(BaseModel):
    """첨부파일 업로드 응답 모델"""
    
    success: bool = Field(description="업로드 성공 여부")
    message: str = Field(description="응답 메시지")
    attachment_id: Optional[str] = Field(default=None, description="업로드된 첨부파일 ID")
    filename: Optional[str] = Field(default=None, description="파일명")
    size: Optional[int] = Field(default=None, description="파일 크기 (바이트)")
    vectors_created: Optional[int] = Field(default=None, description="생성된 벡터 수")
    error: Optional[str] = Field(default=None, description="오류 메시지")


class AttachmentListResponse(BaseModel):
    """첨부파일 목록 응답 모델"""
    
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="첨부파일 목록")
    total: int = Field(description="전체 첨부파일 수")
    page: int = Field(description="현재 페이지")
    per_page: int = Field(description="페이지당 항목 수")


class SimilarTicketsResponse(BaseModel):
    """유사 티켓 검색 응답 모델"""
    
    ticket_id: str = Field(description="원본 티켓의 ID")
    similar_tickets: List[SimilarTicketItem] = Field(description="검색된 유사 티켓 목록")
