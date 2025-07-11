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
    """Platform-Neutral 쿼리 응답 모델"""
    
    answer: str
    context_docs: List[DocumentInfo]
    context_images: List[dict] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Platform-Neutral 하이브리드 검색 결과 필드들
    search_analysis: Optional[Dict[str, Any]] = None  # 검색 분석 결과 (의도, 엔티티 등)
    platform_neutral_matches: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Platform-Neutral 3-Tuple 기반 매칭 결과"
    )
    llm_insights: Optional[Dict[str, Any]] = None  # LLM 기반 인사이트 및 추천
    search_quality_score: Optional[float] = None  # 검색 품질 점수 (0-1)
    
    # Platform-Neutral 요약 정보
    platform_neutral_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Platform-Neutral 검색 요약 (플랫폼별 결과 통계 등)"
    )


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
    """Freshdesk 전용 티켓 초기화 응답 모델"""

    # 티켓 식별자 (Freshdesk 전용)
    ticket_id: str = Field(description="Freshdesk 티켓 ID")
    tenant_id: str = Field(description="테넌트 ID (멀티테넌트 지원)")
    platform: str = Field(default="freshdesk", description="플랫폼 (Freshdesk 고정)")
    
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


class AgentChatResponse(BaseModel):
    """상담원 채팅 검색 응답 모델"""
    
    # 검색 컨텍스트 정보
    search_context: Dict[str, Any] = Field(
        description="분석된 검색 컨텍스트 (의도, 우선순위, 키워드, 필터)"
    )
    
    # 검색 결과
    search_results: List[DocumentInfo] = Field(
        default_factory=list,
        description="검색된 문서 목록"
    )
    
    # Constitutional AI 응답
    structured_response: Optional[str] = Field(
        default=None,
        description="Constitutional AI가 생성한 구조화된 응답"
    )
    
    # 액션 아이템
    action_items: List[str] = Field(
        default_factory=list,
        description="상담원을 위한 액션 아이템 목록"
    )
    
    # 관련 제안
    related_suggestions: List[str] = Field(
        default_factory=list,
        description="관련 검색 제안"
    )
    
    # 메타데이터
    total_results: int = Field(default=0, description="총 검색 결과 수")
    quality_score: float = Field(default=0.0, description="검색 품질 점수 (0.0-1.0)")
    response_time_ms: Optional[float] = Field(default=None, description="응답 시간 (밀리초)")
    
    # 스트리밍을 위한 청크 정보
    chunk_type: Optional[str] = Field(
        default=None,
        description="청크 타입 (analysis, search, processing, response, final, error)"
    )
    is_final: bool = Field(default=True, description="최종 응답 여부")


class AgentChatSuggestionResponse(BaseModel):
    """상담원 채팅 검색 제안 응답 모델"""
    
    quick_searches: List[str] = Field(
        description="빠른 검색 제안"
    )
    role_based: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="역할별 검색 제안"
    )
    category_based: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="카테고리별 검색 제안"
    )


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


class AgentResponse(BaseModel):
    """에이전트 정보 응답 모델"""
    
    id: int = Field(description="에이전트 ID")
    tenant_id: str = Field(description="테넌트 ID")
    platform: str = Field(description="플랫폼")
    name: str = Field(description="에이전트 이름")
    email: str = Field(description="에이전트 이메일")
    job_title: Optional[str] = Field(default=None, description="직책")
    active: bool = Field(description="활성화 상태")
    available: bool = Field(description="가용 상태")
    license_active: bool = Field(description="라이선스 활성화 상태")
    type: Optional[str] = Field(default=None, description="에이전트 타입")
    language: Optional[str] = Field(default=None, description="언어")
    time_zone: Optional[str] = Field(default=None, description="시간대")
    last_login_at: Optional[str] = Field(default=None, description="마지막 로그인 시간")
    created_at: datetime = Field(description="생성 시간")
    updated_at: datetime = Field(description="수정 시간")
    
    class Config:
        from_attributes = True  # Pydantic V2 스타일


class AgentListResponse(BaseModel):
    """에이전트 목록 응답 모델"""
    
    agents: List[AgentResponse] = Field(description="에이전트 목록")
    total_count: int = Field(description="전체 개수")
    page: int = Field(description="현재 페이지")
    page_size: int = Field(description="페이지 크기")
    total_pages: int = Field(description="전체 페이지 수")
    license_stats: Dict[str, int] = Field(
        description="라이선스 통계 (total_licenses, active_licenses)"
    )


class LicenseUpdateResponse(BaseModel):
    """라이선스 업데이트 응답 모델"""
    
    agent_id: int = Field(description="에이전트 ID")
    license_active: bool = Field(description="라이선스 활성화 상태")
    updated_at: datetime = Field(description="업데이트 시간")
    agent_name: str = Field(description="에이전트 이름")
    agent_email: str = Field(description="에이전트 이메일")
    active_licenses_count: int = Field(description="활성 라이선스 수")


class BulkLicenseUpdateRequest(BaseModel):
    """일괄 라이선스 업데이트 요청 모델"""
    
    agent_ids: List[int] = Field(description="에이전트 ID 목록")
    license_active: bool = Field(description="라이선스 활성화 상태")


class BulkLicenseUpdateResponse(BaseModel):
    """일괄 라이선스 업데이트 응답 모델"""
    
    total_requested: int = Field(description="요청된 전체 수")
    success_count: int = Field(description="성공 수")
    failed_count: int = Field(description="실패 수")
    failed_agent_ids: List[int] = Field(default_factory=list, description="실패한 에이전트 ID 목록")
    active_licenses_count: int = Field(description="활성 라이선스 수")
