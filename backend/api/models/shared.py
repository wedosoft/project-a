"""
Platform-Neutral 공유 모델 정의

Request와 Response 모델에서 공통으로 사용되는 Platform-Neutral 모델들을 정의합니다.
모든 모델이 3-Tuple (tenant_id, platform, original_id) 구조를 지원합니다.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class DocumentInfo(BaseModel):
    """Platform-Neutral 검색 문서 정보 모델"""

    title: str
    content: Optional[str] = ""  # Optional로 변경하고 기본값 설정
    
    # Platform-Neutral 3-Tuple 기반 식별자
    source_id: str = Field(description="플랫폼 원본 문서 ID (original_id)")
    tenant_id: Optional[str] = Field(default=None, description="테넌트 ID (테넌트 격리)")
    platform: Optional[str] = Field(default=None, description="플랫폼 ID (멀티플랫폼 지원)")
    platform_neutral_key: Optional[str] = Field(
        default=None, 
        description="Platform-Neutral 3-Tuple 키 (tenant_id:platform:original_id)"
    )
    
    source_url: str = ""  # 빈 문자열을 기본값으로 설정
    relevance_score: float = 0.0
    
    # Platform-Neutral 문서 타입 (예: "ticket", "kb", "faq")
    doc_type: Optional[str] = Field(default=None, description="Platform-neutral 문서 타입")
    
    # Platform-Neutral 메타데이터
    platform_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="플랫폼별 추가 메타데이터 (상태, 우선순위 등)"
    )
    
    # 프론트엔드 호환성을 위한 metadata 필드
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="프론트엔드 호환성을 위한 메타데이터 (platform_metadata와 동일한 내용)"
    )
    
    def model_post_init(self, __context):
        """모델 초기화 후 metadata 필드에 platform_metadata 복사"""
        if self.platform_metadata and not self.metadata:
            self.metadata = self.platform_metadata.copy()

    @field_validator('source_url')
    def ensure_source_url_is_str(cls, v):
        """URL이 None이면 빈 문자열로 변환"""
        return v or ""


class Source(BaseModel):
    """출처 정보"""

    title: str = ""
    url: str = ""


class TicketSummaryContent(BaseModel):
    """티켓 요약을 위한 통합 모델"""
    
    # summary → ticket_summary로 필드명 변경 (일관성)
    ticket_summary: str = Field(description="티켓의 전체 요약")
    key_points: List[str] = Field(
        default_factory=list, description="주요 포인트 목록"
    )
    sentiment: str = Field(
        default="중립적", description="감정 분석 결과 (긍정적, 중립적, 부정적)"
    )
    priority_recommendation: Optional[str] = Field(
        default=None, description="권장 우선순위"
    )
    category_suggestion: Optional[List[str]] = Field(
        default=None, description="추천 카테고리"
    )
    customer_summary: Optional[str] = Field(
        default=None, description="고객 관련 주요 내용 요약"
    )
    request_summary: Optional[str] = Field(
        default=None, description="고객의 주요 요청 사항 요약"
    )
    urgency_level: Optional[str] = Field(
        default=None, description="티켓의 긴급도 (예: 높음, 보통, 낮음)"
    )


class SimilarTicketItem(BaseModel):
    """Platform-Neutral 유사 티켓 정보 모델"""
    
    # Platform-Neutral 원본 티켓 ID
    id: str = Field(description="플랫폼 원본 티켓 ID (original_id)")
    
    # Platform-Neutral 3-Tuple 정보
    tenant_id: Optional[str] = Field(default=None, description="테넌트 ID")
    platform: Optional[str] = Field(default=None, description="플랫폼 ID") 
    platform_neutral_key: Optional[str] = Field(
        default=None,
        description="Platform-Neutral 3-Tuple 키 (tenant_id:platform:original_id)"
    )
    
    # 티켓 제목 (프레시데스크 원본 필드명)
    subject: Optional[str] = Field(default=None, description="유사 티켓의 제목")
    
    # 티켓 내용
    content: Optional[str] = Field(default=None, description="유사 티켓의 내용")
    issue: Optional[str] = Field(default=None, description="문제 상황 요약")
    solution: Optional[str] = Field(default=None, description="해결책 요약")
    
    # 유사도 점수 (백엔드 응답 필드명과 일치)
    score: Optional[float] = Field(default=None, description="유사도 점수 (0.0 ~ 1.0)")
    similarity_score: Optional[float] = Field(default=None, description="유사도 점수 (하위호환성)")
    
    # 첨부파일 및 이미지 정보 (최적화된 구조)
    has_attachments: Optional[bool] = Field(default=False, description="첨부파일 존재 여부")
    has_inline_images: Optional[bool] = Field(default=False, description="인라인 이미지 존재 여부")
    attachment_count: Optional[int] = Field(default=0, description="첨부파일 수")
    
    # 기타 필드
    ticket_url: Optional[str] = Field(default=None, description="원본 티켓 링크")
    
    # Platform-Neutral 메타데이터
    platform_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="플랫폼별 추가 메타데이터 (상태, 우선순위 등)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="확장 메타데이터 (백엔드 응답과 일치)"
    )

    # 기존 호환성을 위한 필드 (deprecated)
    ticket_summary: Optional[str] = Field(
        default=None, description="유사 티켓의 내용 요약 (deprecated)"
    )
