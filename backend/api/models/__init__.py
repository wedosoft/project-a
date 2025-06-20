"""
API 모델 패키지

Request 및 Response 모델들을 정의합니다.
"""

from .requests import (
    QueryRequest,
    IngestRequest,
    TicketInitRequest,
    GenerateReplyRequest
)

from .responses import (
    QueryResponse,
    IngestResponse,
    InitResponse,
    GenerateReplyResponse,
    SimilarTicketsResponse
)

from .shared import (
    DocumentInfo,
    Source,
    TicketSummaryContent,
    SimilarTicketItem
)

__all__ = [
    # Request models
    "QueryRequest",
    "IngestRequest", 
    "TicketInitRequest",
    "GenerateReplyRequest",
    
    # Response models
    "QueryResponse",
    "IngestResponse",
    "InitResponse",
    "GenerateReplyResponse",
    "SimilarTicketsResponse",
    
    # Shared models
    "DocumentInfo",
    "Source",
    "TicketSummaryContent",
    "SimilarTicketItem"
]
