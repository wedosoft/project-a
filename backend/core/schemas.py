"""
공통 스키마 정의 모듈

이 모듈은 애플리케이션 전체에서 사용되는 공통 Pydantic 모델을 정의합니다.
API 요청/응답 형식을 표준화하고 검증하는 역할을 합니다.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field, root_validator, validator


# 응답 메타데이터를 위한 모델
class ResponseMetadata(BaseModel):
    """
    API 응답에 포함되는 메타데이터 모델입니다.
    """
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    process_time_ms: Optional[float] = None


# 페이지네이션을 위한 모델
class PaginationMetadata(BaseModel):
    """
    페이지네이션 정보를 위한 모델입니다.
    """
    page: int = Field(..., description="현재 페이지 번호")
    per_page: int = Field(..., description="페이지당 항목 수")
    total: int = Field(..., description="전체 항목 수")
    total_pages: int = Field(..., description="전체 페이지 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_prev: bool = Field(..., description="이전 페이지 존재 여부")


# 제네릭 응답 모델을 위한 타입 변수
T = TypeVar('T')


# 표준 API 응답 모델 (제네릭)
class StandardResponse(BaseModel, Generic[T]):
    """
    모든 API 응답에 사용되는 표준 형식입니다.
    제네릭 타입 T를 통해 다양한 응답 데이터 타입을 지원합니다.
    """
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)
    pagination: Optional[PaginationMetadata] = None


# 오류 응답 모델
class ErrorResponse(BaseModel):
    """
    API 오류 응답을 위한 모델입니다.
    """
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


# 회사 ID 관련 모델
class CompanyIdentifier(BaseModel):
    """
    회사 식별 정보를 포함하는 기본 모델입니다.
    대부분의 요청 모델에서 상속받아 사용합니다.
    """
    company_id: str = Field(..., description="회사 식별자")


# 블록 타입 열거형
class BlockType(str, Enum):
    """
    지원되는 블록 타입을 정의합니다.
    """
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "listItem"
    TODO_ITEM = "todoItem"
    CODE = "code"
    QUOTE = "quote"
    IMAGE = "image"
    DIVIDER = "divider"
    TABLE = "table"


# 블록 콘텐츠 모델
class BlockContent(BaseModel):
    """
    블록의 내용을 나타내는 모델입니다.
    다양한 타입의 콘텐츠를 포함할 수 있습니다.
    """
    text: Optional[str] = None
    level: Optional[int] = None  # heading level
    checked: Optional[bool] = None  # for todoItem
    language: Optional[str] = None  # for code blocks
    url: Optional[str] = None  # for images
    alt: Optional[str] = None  # for images
    caption: Optional[str] = None  # for images, tables
    
    # 블록 타입에 따른 유효성 검증
    @root_validator
    def validate_block_content(cls, values):
        # TODO: 블록 타입에 따라 필요한 필드 검증 로직 구현
        return values


# 블록 모델
class Block(BaseModel):
    """
    에디터에서 사용되는 블록 모델입니다.
    각 블록은 고유 ID, 타입, 콘텐츠를 가지고 있습니다.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: BlockType
    content: BlockContent


# 티켓 메타데이터 모델
class TicketMetadata(BaseModel):
    """
    티켓의 메타데이터를 나타내는 모델입니다.
    """
    ticket_id: int
    created_at: datetime
    updated_at: datetime
    status: str
    priority: Optional[str] = None
    tags: List[str] = []
    source: Optional[str] = None
    category: Optional[str] = None


# 지식베이스 문서 메타데이터 모델
class KBArticleMetadata(BaseModel):
    """
    지식베이스 문서의 메타데이터를 나타내는 모델입니다.
    """
    article_id: int
    created_at: datetime
    updated_at: datetime
    status: str
    category_id: Optional[int] = None
    folder_id: Optional[int] = None
    tags: List[str] = []
    author_id: Optional[int] = None


# 검색 필터 모델
class SearchFilter(BaseModel):
    """
    검색 필터링을 위한 모델입니다.
    """
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    categories: Optional[List[str]] = None
    priorities: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    keywords: Optional[str] = None


# 검색 결과 항목 모델
class SearchResultItem(BaseModel):
    """
    검색 결과의 개별 항목을 나타내는 모델입니다.
    """
    id: str
    title: str
    content: str
    score: float
    type: str  # "ticket" 또는 "kb_article"
    metadata: Dict[str, Any]
    highlights: List[str] = []


# LLM 응답 형식 열거형
class ResponseFormat(str, Enum):
    """
    LLM 응답 형식을 정의합니다.
    """
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    BLOCKS = "blocks"


# LLM 스타일 열거형
class ResponseStyle(str, Enum):
    """
    응답 생성 스타일을 정의합니다.
    """
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    SIMPLE = "simple"
    DETAILED = "detailed"


# LLM 톤 열거형
class ResponseTone(str, Enum):
    """
    응답 생성 톤을 정의합니다.
    """
    HELPFUL = "helpful"
    EMPATHETIC = "empathetic"
    DIRECT = "direct"
    FORMAL = "formal"
    CASUAL = "casual"
