"""
API Request 모델 정의

모든 API 엔드포인트의 Request 모델들을 정의합니다.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """쿼리 요청 모델"""
    
    query: str
    top_k: int = 3
    answer_instructions: Optional[str] = None  # 사용자가 제공하는 답변 지침
    # 현재 처리 중인 티켓 ID (선택 사항)
    ticket_id: Optional[str] = None
    # 검색할 콘텐츠 타입
    type: List[str] = Field(
        default_factory=lambda: ["tickets", "solutions", "images", "attachments"]
    )
    # 검색 의도 (예: "search", "recommend", "answer")
    intent: Optional[str] = "search"
    company_id: Optional[str] = None  # 회사 ID (헤더에서 가져오는 경우 선택 사항)
    platform: Optional[str] = None  # 플랫폼 필터링 (헤더에서 가져오는 경우 선택 사항)
    # 검색할 데이터 타입
    search_types: Optional[List[str]] = Field(
        default_factory=lambda: ["ticket", "kb"]
    )
    min_similarity: float = 0.5  # 최소 유사도 임계값
    
    # /init 엔드포인트에서 사용되는 추가 필드들
    include_summary: bool = True  # 티켓 요약 생성 여부
    include_kb_docs: bool = True  # 관련 지식베이스 문서 포함 여부
    include_similar_tickets: bool = True  # 유사 티켓 포함 여부
    top_k_tickets: int = 5  # 유사 티켓 검색 결과 수
    top_k_kb: int = 5  # 지식베이스 문서 검색 결과 수


class IngestRequest(BaseModel):
    """데이터 수집 요청 모델"""
    
    incremental: bool = True  # 증분 업데이트 모드 여부
    purge: bool = False  # 기존 데이터 삭제 여부
    process_attachments: bool = True  # 첨부파일 처리 여부
    force_rebuild: bool = False  # 데이터베이스 강제 재구축 여부
    include_kb: bool = True  # 지식베이스 데이터 포함 여부


class IngestJobCreateRequest(BaseModel):
    """데이터 수집 작업 생성 요청 모델 (비동기)"""
    
    incremental: bool = True  # 증분 업데이트 모드 여부
    purge: bool = False  # 기존 데이터 삭제 여부
    process_attachments: bool = True  # 첨부파일 처리 여부
    force_rebuild: bool = False  # 데이터베이스 강제 재구축 여부
    include_kb: bool = True  # 지식베이스 데이터 포함 여부
    
    # 고급 옵션
    batch_size: int = Field(default=50, ge=1, le=200, description="배치 크기")
    max_retries: int = Field(default=3, ge=0, le=10, description="최대 재시도 횟수")
    parallel_workers: int = Field(default=4, ge=1, le=8, description="병렬 작업자 수")
    
    # 자동 시작 여부
    auto_start: bool = Field(default=True, description="생성 후 자동 시작 여부")


class TicketInitRequest(BaseModel):
    """티켓 초기화 요청 모델"""
    
    ticket_id: str
    company_id: str
    include_summary: bool = True  # 티켓 요약 생성 여부
    include_kb_docs: bool = True  # 관련 지식베이스 문서 포함 여부
    include_similar_tickets: bool = True  # 유사 티켓 포함 여부


class AttachmentProcessRequest(BaseModel):
    """첨부파일 처리 요청 모델"""
    
    attachment_id: str = Field(description="처리할 첨부파일 ID")
    force_reprocess: bool = Field(default=False, description="강제 재처리 여부")


class GenerateReplyRequest(BaseModel):
    """응답 생성 요청 모델"""
    
    context_id: str  # 초기화에서 생성된 컨텍스트 ID
    query: str  # 고객 질문/요청 내용
    style: Optional[str] = "professional"  # 응답 스타일 (professional, friendly, technical)
    tone: Optional[str] = "helpful"  # 응답 톤 (helpful, empathetic, direct)
    instructions: Optional[str] = None  # 추가 응답 생성 지침
    include_greeting: bool = True  # 인사말 포함 여부
    include_signature: bool = True  # 서명 포함 여부
    company_id: Optional[str] = None  # 회사 ID (선택사항)
