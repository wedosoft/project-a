"""
API Request 모델 정의

모든 API 엔드포인트의 Request 모델들을 정의합니다.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Platform-Neutral 쿼리 요청 모델"""
    
    query: str
    top_k: int = 3
    answer_instructions: Optional[str] = None  # 사용자가 제공하는 답변 지침
    
    # Platform-Neutral 3-Tuple 필수 필드 (헤더에서 추출되므로 선택적)
    tenant_id: Optional[str] = Field(default=None, description="테넌트 ID (헤더에서 자동 추출)")
    platform: Optional[str] = Field(default=None, description="플랫폼 ID (헤더에서 자동 추출)")
    
    # 대화 히스토리 (대화 맥락 유지용)
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None, 
        description="이전 대화 내용 [{role: 'user'|'assistant', content: '...'}]"
    )
    
    # 현재 처리 중인 티켓 ID (platform-neutral original_id)
    ticket_id: Optional[str] = Field(default=None, description="플랫폼 원본 티켓 ID")
    
    # 검색할 콘텐츠 타입
    type: List[str] = Field(
        default_factory=lambda: ["tickets", "solutions", "images", "attachments"]
    )
    # 검색 의도 (예: "search", "recommend", "answer")
    intent: Optional[str] = "search"
    
    # Platform-Neutral 검색 타입
    search_types: Optional[List[str]] = Field(
        default_factory=lambda: ["ticket", "kb"],
        description="Platform-neutral 문서 타입 (ticket, kb, attachment 등)"
    )
    min_similarity: float = 0.5  # 최소 유사도 임계값
    
    # Platform-Neutral 하이브리드 검색 필드들
    use_hybrid_search: bool = False  # 하이브리드 검색 활성화 여부
    custom_fields: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Platform-neutral 커스텀 필드 검색 조건"
    )
    search_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Platform-neutral 검색 필터 (우선순위, 상태, 날짜 등)"
    )
    enable_intent_analysis: bool = True  # 의도 분석 활성화 여부
    enable_llm_enrichment: bool = True  # LLM 컨텍스트 강화 활성화 여부
    rerank_results: bool = True  # 결과 재순위 활성화 여부
    
    # 상담원 채팅 관련 필드들
    agent_mode: bool = Field(default=False, description="상담원 모드 활성화 (Constitutional AI 적용)")
    agent_context: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="상담원 컨텍스트 정보 (현재 티켓, 고객 정보 등)"
    )
    force_intent: Optional[str] = Field(
        default=None,
        description="강제 의도 설정 (problem_solving, info_gathering, learning, analysis)"
    )
    urgency_override: Optional[str] = Field(
        default=None,
        description="우선순위 강제 설정 (immediate, today, general, reference)"
    )
    enable_constitutional_ai: bool = Field(
        default=False,
        description="Constitutional AI 응답 생성 활성화"
    )
    safety_level: str = Field(
        default="standard",
        description="안전 수준 (strict, standard, relaxed)"
    )
    stream_response: bool = Field(
        default=False,
        description="스트리밍 응답 여부 (상담원 모드에서 사용)"
    )
    
    # 고급 자연어 검색 기능 (새로운 기능)
    enhanced_search: bool = Field(
        default=False,
        description="고급 자연어 검색 활성화 (첨부파일/카테고리/해결책 전문 검색)"
    )
    enhanced_search_type: Optional[str] = Field(
        default=None,
        description="고급 검색 타입 (auto, attachment, category, solution, general)"
    )
    
    # 첨부파일 검색 옵션
    file_types: Optional[List[str]] = Field(
        default=None,
        description="찾을 파일 타입 (pdf, excel, image, word, text 등)"
    )
    max_file_size_mb: Optional[float] = Field(
        default=None,
        description="최대 파일 크기 (MB)"
    )
    min_file_size_mb: Optional[float] = Field(
        default=None,
        description="최소 파일 크기 (MB)"
    )
    
    # 카테고리 검색 옵션
    categories: Optional[List[str]] = Field(
        default=None,
        description="검색할 카테고리 목록 (결제, 로그인, API, 기술지원 등)"
    )
    
    # 문제 해결 검색 옵션
    solution_type: Optional[str] = Field(
        default=None,
        description="해결책 타입 (quick_fix, step_by_step, similar_case)"
    )
    include_resolved_only: bool = Field(
        default=False,
        description="해결된 케이스만 포함"
    )
    
    # /init 엔드포인트에서 사용되는 추가 필드들
    include_summary: bool = True  # 티켓 요약 생성 여부
    include_kb_docs: bool = True  # 관련 지식베이스 문서 포함 여부
    include_similar_tickets: bool = True  # 유사 티켓 포함 여부
    top_k_tickets: int = 5  # 유사 티켓 검색 결과 수
    top_k_kb: int = 5  # 지식베이스 문서 검색 결과 수


class IngestRequest(BaseModel):
    """Platform-Neutral 데이터 수집 요청 모델"""
    
    # Platform-Neutral 3-Tuple 필수 필드 (헤더에서 추출되지만 명시적 검증)
    tenant_id: Optional[str] = Field(
        default=None, 
        description="테넌트 ID (헤더에서 자동 추출, 테넌트 격리)"
    )
    platform: Optional[str] = Field(
        default=None,
        description="플랫폼 ID (헤더에서 자동 추출, 멀티플랫폼 지원)"
    )
    
    incremental: bool = True  # 증분 업데이트 모드 여부
    purge: bool = False  # 기존 데이터 삭제 여부
    process_attachments: bool = True  # 첨부파일 처리 여부
    force_rebuild: bool = False  # 데이터베이스 강제 재구축 여부
    include_kb: bool = True  # 지식베이스 데이터 포함 여부
    max_tickets: Optional[int] = None  # 최대 수집 티켓 수 (None=무제한, 테스트용으로 100 지정 가능)


    max_articles: Optional[int] = None  # 최대 수집 KB 문서 수 (None=무제한, 테스트용으로 100 지정 가능)
    start_date: Optional[str] = Field(
        default=None,
        description="티켓 수집 시작 날짜 (YYYY-MM-DD 형식, None이면 현재부터 10년 전)"
    )
    force_update: bool = Field(
        default=False,
        description="기존 요약이 있어도 강제로 재생성 여부 (기본값: False)"
    )


class IngestJobCreateRequest(BaseModel):
    """데이터 수집 작업 생성 요청 모델 (비동기)"""
    
    incremental: bool = True  # 증분 업데이트 모드 여부
    purge: bool = False  # 기존 데이터 삭제 여부
    process_attachments: bool = True  # 첨부파일 처리 여부
    force_rebuild: bool = False  # 데이터베이스 강제 재구축 여부
    include_kb: bool = True  # 지식베이스 데이터 포함 여부
    start_date: Optional[str] = Field(
        default=None,
        description="티켓 수집 시작 날짜 (YYYY-MM-DD 형식, None이면 현재부터 10년 전)"
    )
    
    # 고급 옵션
    batch_size: int = Field(default=50, ge=1, le=200, description="배치 크기")
    max_retries: int = Field(default=3, ge=0, le=10, description="최대 재시도 횟수")
    parallel_workers: int = Field(default=4, ge=1, le=8, description="병렬 작업자 수")
    
    # 자동 시작 여부
    auto_start: bool = Field(default=True, description="생성 후 자동 시작 여부")


class TicketInitRequest(BaseModel):
    """Platform-Neutral 티켓 초기화 요청 모델"""
    
    # Platform-Neutral 원본 티켓 ID (접두어 없는 플랫폼 원본 ID)
    ticket_id: str = Field(description="플랫폼 원본 티켓 ID (예: '12345', 'ticket-' 접두어 제외)")
    
    # Platform-Neutral 3-Tuple 필수 필드
    tenant_id: str = Field(description="테넌트 ID (테넌트 격리 필수)")
    platform: str = Field(default="freshdesk", description="플랫폼 ID (멀티플랫폼 지원)")
    
    include_summary: bool = True  # 티켓 요약 생성 여부
    include_kb_docs: bool = True  # 관련 지식베이스 문서 포함 여부
    include_similar_tickets: bool = True  # 유사 티켓 포함 여부


class AttachmentProcessRequest(BaseModel):
    """첨부파일 처리 요청 모델"""
    
    attachment_id: str = Field(description="처리할 첨부파일 ID")
    force_reprocess: bool = Field(default=False, description="강제 재처리 여부")


class GenerateReplyRequest(BaseModel):
    """Platform-Neutral 응답 생성 요청 모델"""
    
    context_id: str  # 초기화에서 생성된 컨텍스트 ID
    query: str  # 고객 질문/요청 내용
    
    # Platform-Neutral 3-Tuple 필수 필드
    tenant_id: str = Field(description="테넌트 ID (테넌트 격리 필수)")
    platform: str = Field(default="freshdesk", description="플랫폼 ID (멀티플랫폼 지원)")
    
    style: Optional[str] = "professional"  # 응답 스타일 (professional, friendly, technical)
    tone: Optional[str] = "helpful"  # 응답 톤 (helpful, empathetic, direct)
    instructions: Optional[str] = None  # 추가 응답 생성 지침
    include_greeting: bool = True  # 인사말 포함 여부
    include_signature: bool = True  # 서명 포함 여부


class DataSecurityRequest(BaseModel):
    """데이터 보안 관리 요청 모델 (GDPR/완전 삭제)"""
    
    action: str = Field(description="수행할 작업 (purge_all, reset_company, delete_platform)")
    confirmation_token: str = Field(description="보안 확인 토큰 (안전장치)")
    reason: Optional[str] = Field(default=None, description="삭제/초기화 사유")
    
    # 범위 지정
    tenant_id: Optional[str] = Field(default=None, description="특정 회사 데이터만 삭제 (None=전체)")
    platform: Optional[str] = Field(default=None, description="특정 플랫폼 데이터만 삭제 (None=전체)")
    
    # 백업 옵션
    create_backup: bool = Field(default=True, description="삭제 전 백업 생성 여부")
    backup_location: Optional[str] = Field(default=None, description="백업 저장 위치")
    
    # 안전장치 옵션
    force_delete: bool = Field(default=False, description="강제 삭제 모드 (위험)")
    include_vectors: bool = Field(default=True, description="벡터 DB 데이터도 삭제")
    include_cache: bool = Field(default=True, description="캐시 데이터도 삭제")
    include_logs: bool = Field(default=False, description="로그 데이터도 삭제 (감사용)")
    include_secrets: bool = Field(default=True, description="AWS Secrets Manager 비밀키도 삭제")
    
    # AWS Secrets Manager 설정
    aws_region: Optional[str] = Field(default=None, description="AWS 리전 (기본값: 환경변수에서 추출)")
    secret_name_pattern: Optional[str] = Field(default=None, description="삭제할 시크릿 이름 패턴")


class SecurityActionRequest(BaseModel):
    """보안 액션 확인 요청 모델"""
    
    action_type: str = Field(description="액션 타입 (data_purge, company_reset, platform_cleanup)")
    security_code: str = Field(description="보안 코드 (2FA/SMS 등)")
    user_confirmation: str = Field(description="사용자 확인 문구 ('DELETE_ALL_DATA' 등)")
    
    # 추가 보안 검증
    admin_approval: Optional[str] = Field(default=None, description="관리자 승인 토큰")
    audit_trail: bool = Field(default=True, description="감사 로그 기록 여부")
