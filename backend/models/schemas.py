"""
Pydantic models for AI Contact Center OS

This module contains all Pydantic schemas matching the Supabase database schema.
Includes comprehensive validation, type hints, and documentation.

Updated based on peer review feedback:
- Block-type specific validation for content length
- Enhanced SearchResult with source_type, confidence, excerpt
- Improved naming (constraints, proposed_field_updates)
- Additional models for feedback, metrics, compliance
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID, uuid4
import re

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class BlockType(str, Enum):
    """Issue block types for ticket knowledge extraction"""
    SYMPTOM = "symptom"
    CAUSE = "cause"
    RESOLUTION = "resolution"


class ApprovalStatus(str, Enum):
    """Approval status for AI proposals"""
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


class SourceType(str, Enum):
    """Source type for search results"""
    ISSUE_CASE = "case"
    KB_ARTICLE = "kb"


class TicketStatus(str, Enum):
    """Valid ticket statuses"""
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    """Valid ticket priorities"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ============================================================================
# Database Models (matching Supabase tables)
# ============================================================================

class IssueBlock(BaseModel):
    """
    Issue block model representing symptom/cause/resolution extracted from tickets.

    This model matches the `issue_blocks` table in Supabase.
    Used for storing ticket knowledge that can be retrieved for similar cases.

    Attributes:
        id: Unique identifier (UUID)
        tenant_id: Tenant identifier for multi-tenancy (alphanumeric, dash, underscore)
        ticket_id: Source ticket ID from Freshdesk
        block_type: Type of block (symptom, cause, or resolution)
        product: Product name (optional)
        component: Component name (optional)
        error_code: Error code if applicable (optional)
        content: Extracted core content (length varies by block_type)
        meta: Additional metadata as JSON (language, tags, etc.)
        embedding_id: Reference to Qdrant vector ID (optional)
        created_at: Creation timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID (alphanumeric, dash, underscore)"
    )
    ticket_id: str = Field(..., min_length=1, max_length=255, description="Ticket ID")
    block_type: BlockType = Field(..., description="Block type (symptom/cause/resolution)")
    product: Optional[str] = Field(None, max_length=255, description="Product name")
    component: Optional[str] = Field(None, max_length=255, description="Component name")
    error_code: Optional[str] = Field(None, max_length=255, description="Error code")
    content: str = Field(..., min_length=1, max_length=2048, description="Extracted content")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (JSONB)")
    embedding_id: Optional[str] = Field(None, max_length=255, description="Qdrant vector ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    @field_validator('content')
    @classmethod
    def validate_content_length(cls, v: str, info) -> str:
        """
        Validate content length based on block_type.
        - symptom: min 10 chars (can be brief)
        - cause: min 20 chars (needs context)
        - resolution: min 30 chars (requires detail)
        """
        if len(v) > 2048:
            raise ValueError("Content must be 2048 characters or less")

        # Block-type specific minimum lengths
        block_type = info.data.get('block_type')
        if block_type:
            min_lengths = {
                BlockType.SYMPTOM: 10,
                BlockType.CAUSE: 20,
                BlockType.RESOLUTION: 30
            }
            min_len = min_lengths.get(block_type, 10)
            if len(v) < min_len:
                raise ValueError(f"{block_type.value} content must be at least {min_len} characters")

        return v

    @field_validator('meta')
    @classmethod
    def validate_meta(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate meta is a valid JSON object with expected structure"""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("Meta must be a dictionary")
            # Validate expected keys if present
            if 'lang' in v and not isinstance(v['lang'], str):
                raise ValueError("Meta 'lang' must be a string")
            if 'tags' in v and not isinstance(v['tags'], list):
                raise ValueError("Meta 'tags' must be a list")
        return v


class IssueBlockCreate(BaseModel):
    """Schema for creating a new issue block (without generated fields)"""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    ticket_id: str = Field(..., min_length=1, max_length=255)
    block_type: BlockType
    product: Optional[str] = Field(None, max_length=255)
    component: Optional[str] = Field(None, max_length=255)
    error_code: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1, max_length=2048)  # min_length=1, specific validation in validator
    meta: Optional[Dict[str, Any]] = None

    @field_validator('content')
    @classmethod
    def validate_content_length(cls, v: str, info) -> str:
        """
        Validate content length based on block_type.
        - symptom: min 10 chars (can be brief)
        - cause: min 20 chars (needs context)
        - resolution: min 30 chars (requires detail)
        """
        if len(v) > 2048:
            raise ValueError("Content must be 2048 characters or less")

        # Block-type specific minimum lengths
        block_type = info.data.get('block_type')
        if block_type:
            min_lengths = {
                BlockType.SYMPTOM: 10,
                BlockType.CAUSE: 20,
                BlockType.RESOLUTION: 30
            }
            min_len = min_lengths.get(block_type, 10)
            if len(v) < min_len:
                raise ValueError(f"{block_type.value} content must be at least {min_len} characters")

        return v

    @field_validator('meta')
    @classmethod
    def validate_meta(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate meta is a valid JSON object with expected structure"""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("Meta must be a dictionary")
            # Validate expected keys if present
            if 'lang' in v and not isinstance(v['lang'], str):
                raise ValueError("Meta 'lang' must be a string")
            if 'tags' in v and not isinstance(v['tags'], list):
                raise ValueError("Meta 'tags' must be a list")
        return v


class KBBlock(BaseModel):
    """
    Knowledge base block model for standard procedures and policies.

    This model matches the `kb_blocks` table in Supabase.
    Used for storing organizational knowledge and best practices.

    Attributes:
        id: Unique identifier (UUID)
        tenant_id: Tenant identifier for multi-tenancy
        article_id: Source KB article ID (optional)
        intent: Intent or purpose description (optional)
        step: Procedure steps (optional)
        constraints: Constraints and warnings (renamed from constraint_text)
        example: Example usage (optional)
        meta: Additional metadata as JSON
        embedding_id: Reference to Qdrant vector ID (optional)
        created_at: Creation timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID"
    )
    article_id: Optional[str] = Field(None, max_length=255, description="KB article ID")
    intent: Optional[str] = Field(None, max_length=1024, description="Intent/purpose")
    step: Optional[str] = Field(None, max_length=2048, description="Procedure steps")
    constraint: Optional[str] = Field(None, max_length=1024, description="Constraints and warnings")
    example: Optional[str] = Field(None, max_length=1024, description="Example usage")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (JSONB)")
    embedding_id: Optional[str] = Field(None, max_length=255, description="Qdrant vector ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    @field_validator('meta')
    @classmethod
    def validate_meta(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate meta is a valid JSON object"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Meta must be a dictionary")
        return v


class KBBlockCreate(BaseModel):
    """Schema for creating a new KB block (without generated fields)"""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")
    article_id: Optional[str] = Field(None, max_length=255)
    intent: Optional[str] = Field(None, max_length=1024)
    step: Optional[str] = Field(None, max_length=2048)
    constraint: Optional[str] = Field(None, max_length=1024, alias="constraints")
    example: Optional[str] = Field(None, max_length=1024)
    meta: Optional[Dict[str, Any]] = None


class ApprovalLog(BaseModel):
    """
    Approval log model for tracking AI proposals and agent feedback.

    This model matches the `approval_logs` table in Supabase.
    Used for logging agent approval/modification/rejection of AI suggestions.

    Attributes:
        id: Unique identifier (UUID)
        tenant_id: Tenant identifier for multi-tenancy
        ticket_id: Related ticket ID
        draft_response: AI-generated draft response (optional)
        final_response: Agent's final approved/modified response (optional)
        proposed_field_updates: Suggested ticket field updates (renamed from field_updates)
        approval_status: Status (approved/modified/rejected)
        agent_id: Agent who made the decision (optional)
        feedback_notes: Additional feedback notes (optional)
        created_at: Creation timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID"
    )
    ticket_id: str = Field(..., min_length=1, max_length=255, description="Ticket ID")
    draft_response: Optional[str] = Field(None, max_length=4096, description="AI draft response")
    final_response: Optional[str] = Field(None, max_length=4096, description="Final response")
    proposed_field_updates: Optional[Dict[str, Any]] = Field(
        None,
        description="Suggested field updates (JSONB)"
    )
    approval_status: ApprovalStatus = Field(..., description="Approval status")
    agent_id: Optional[str] = Field(None, max_length=255, description="Agent ID")
    feedback_notes: Optional[str] = Field(None, max_length=2048, description="Feedback notes")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    @field_validator('proposed_field_updates')
    @classmethod
    def validate_field_updates(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate proposed_field_updates is a valid JSON object"""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Proposed field updates must be a dictionary")
        return v


class ApprovalLogCreate(BaseModel):
    """Schema for creating a new approval log (without generated fields)"""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")
    ticket_id: str = Field(..., min_length=1, max_length=255)
    draft_response: Optional[str] = Field(None, max_length=4096)
    final_response: Optional[str] = Field(None, max_length=4096)
    proposed_field_updates: Optional[Dict[str, Any]] = None
    approval_status: ApprovalStatus
    agent_id: Optional[str] = Field(None, max_length=255)
    feedback_notes: Optional[str] = Field(None, max_length=2048)


# ============================================================================
# API Request/Response Models
# ============================================================================

class TicketContext(BaseModel):
    """
    Ticket context for AI processing.

    This is the input model for AI assist endpoints.
    Contains all necessary information about a ticket for AI analysis.

    Attributes:
        ticket_id: Freshdesk ticket ID
        tenant_id: Tenant identifier
        subject: Ticket subject
        description: Ticket description/content
        status: Current ticket status (validated enum)
        priority: Ticket priority (validated enum)
        product: Product name (optional)
        component: Component name (optional)
        tags: Ticket tags (optional)
        custom_fields: Additional custom fields (optional)
    """
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str = Field(..., min_length=1, max_length=255, description="Ticket ID")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID"
    )
    subject: str = Field(..., min_length=1, max_length=512, description="Ticket subject")
    description: str = Field(..., min_length=1, max_length=8192, description="Ticket description")
    status: TicketStatus = Field(..., description="Ticket status (enum validated)")
    priority: Priority = Field(..., description="Ticket priority (enum validated)")
    product: Optional[str] = Field(None, max_length=255, description="Product name")
    component: Optional[str] = Field(None, max_length=255, description="Component name")
    tags: List[str] = Field(default_factory=list, description="Ticket tags")
    custom_fields: Optional[Dict[str, Any]] = Field(None, description="Custom fields")

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate tags is a list of non-empty strings"""
        if not isinstance(v, list):
            raise ValueError("Tags must be a list")
        if not all(isinstance(tag, str) and len(tag) > 0 for tag in v):
            raise ValueError("All tags must be non-empty strings")
        return v


class SearchResult(BaseModel):
    """
    Enhanced search result from vector/hybrid search.

    Represents a single search result (issue block or KB block)
    with relevance score, metadata, and source information.

    New fields based on review:
        - source_type: Distinguish between case and KB
        - confidence: AI confidence score (0.0-1.0)
        - excerpt: Short snippet for UI display
        - created_at: Creation timestamp for sorting
        - last_updated_at: Last update timestamp

    Attributes:
        id: Result ID
        content: Matched content
        block_type: Type of block (for issue blocks)
        score: Relevance score (0.0-1.0)
        source_type: Source type (case or kb)
        confidence: AI confidence score (optional)
        excerpt: Short snippet for display (optional)
        ticket_id: Source ticket ID (for issue blocks, optional)
        article_id: Source article ID (for KB blocks, optional)
        product: Product name (optional)
        component: Component name (optional)
        created_at: Creation timestamp (optional)
        last_updated_at: Last update timestamp (optional)
        meta: Additional metadata
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Result ID")
    content: str = Field(..., description="Matched content")
    block_type: Optional[BlockType] = Field(None, description="Block type (for issue blocks)")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    source_type: SourceType = Field(..., description="Source type (case or kb)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")
    excerpt: Optional[str] = Field(None, max_length=256, description="Short snippet for display")
    ticket_id: Optional[str] = Field(None, description="Source ticket ID")
    article_id: Optional[str] = Field(None, description="Source article ID")
    product: Optional[str] = Field(None, description="Product name")
    component: Optional[str] = Field(None, description="Component name")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ProposedAction(BaseModel):
    """
    AI-proposed action for a ticket.

    Contains the AI's suggestions for response and field updates.
    This is the output model for AI assist endpoints.

    Attributes:
        ticket_id: Related ticket ID
        draft_response: AI-generated response draft
        similar_cases: List of similar cases found
        kb_procedures: List of relevant KB procedures
        proposed_field_updates: Suggested ticket field updates (renamed)
        confidence: Confidence score (0.0-1.0)
        justification: Explanation for the suggestions
    """
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str = Field(..., min_length=1, max_length=255, description="Ticket ID")
    draft_response: str = Field(..., min_length=1, max_length=4096, description="Draft response")
    similar_cases: List[SearchResult] = Field(
        default_factory=list,
        max_length=10,
        description="Similar cases (max 10)"
    )
    kb_procedures: List[SearchResult] = Field(
        default_factory=list,
        max_length=5,
        description="Relevant KB procedures (max 5)"
    )
    proposed_field_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Suggested field updates"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score"
    )
    justification: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Justification for suggestions"
    )

    @field_validator('similar_cases')
    @classmethod
    def validate_similar_cases(cls, v: List[SearchResult]) -> List[SearchResult]:
        """Validate similar cases list is not too long"""
        if len(v) > 10:
            raise ValueError("Maximum 10 similar cases allowed")
        return v

    @field_validator('kb_procedures')
    @classmethod
    def validate_kb_procedures(cls, v: List[SearchResult]) -> List[SearchResult]:
        """Validate KB procedures list is not too long"""
        if len(v) > 5:
            raise ValueError("Maximum 5 KB procedures allowed")
        return v


# ============================================================================
# Additional Models (based on review feedback)
# ============================================================================

class FeedbackLog(BaseModel):
    """
    Agent feedback log for UI events and approval loop tracking.

    Used to track detailed agent interactions with AI suggestions
    beyond the approval_logs table.

    Attributes:
        id: Unique identifier
        tenant_id: Tenant identifier
        ticket_id: Related ticket ID
        agent_id: Agent who provided feedback
        event_type: Type of UI event (view, edit, approve, reject, etc.)
        feedback_text: Free-form feedback text
        rating: Optional rating (1-5 stars)
        timestamp: Event timestamp
        meta: Additional event metadata
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID"
    )
    ticket_id: str = Field(..., min_length=1, max_length=255, description="Ticket ID")
    agent_id: str = Field(..., min_length=1, max_length=255, description="Agent ID")
    event_type: str = Field(
        ...,
        pattern=r"^(view|edit|approve|reject|modify|request_changes)$",
        description="UI event type"
    )
    feedback_text: Optional[str] = Field(None, max_length=2048, description="Feedback text")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating (1-5 stars)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class MetricsPayload(BaseModel):
    """
    Performance metrics for monitoring search quality.

    Used for tracking Recall, nDCG, and other retrieval metrics.

    Attributes:
        query_id: Unique query identifier
        tenant_id: Tenant identifier
        ticket_id: Related ticket ID (optional)
        metric_type: Type of metric (recall, ndcg, precision, etc.)
        score: Metric score (0.0-1.0)
        k: Top-K value (for Recall@K, nDCG@K)
        total_results: Total number of results returned
        relevant_results: Number of relevant results
        latency_ms: Query latency in milliseconds
        timestamp: Measurement timestamp
        meta: Additional metric metadata
    """
    model_config = ConfigDict(from_attributes=True)

    query_id: UUID = Field(default_factory=uuid4, description="Query identifier")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID"
    )
    ticket_id: Optional[str] = Field(None, max_length=255, description="Ticket ID")
    metric_type: str = Field(
        ...,
        pattern=r"^(recall|ndcg|precision|f1|mrr|map)$",
        description="Metric type"
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Metric score")
    k: int = Field(..., ge=1, le=100, description="Top-K value")
    total_results: int = Field(..., ge=0, description="Total results")
    relevant_results: int = Field(..., ge=0, description="Relevant results")
    latency_ms: float = Field(..., ge=0.0, description="Latency in ms")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ComplianceCheckResult(BaseModel):
    """
    Compliance check result for Phase 2 preparation.

    Used for PII detection, DLP, and policy compliance checks.

    Attributes:
        check_id: Unique check identifier
        tenant_id: Tenant identifier
        ticket_id: Related ticket ID
        check_type: Type of compliance check (pii, dlp, policy, etc.)
        passed: Whether the check passed
        violations: List of violations found
        severity: Severity level (low, medium, high, critical)
        recommendations: Recommended actions
        timestamp: Check timestamp
    """
    model_config = ConfigDict(from_attributes=True)

    check_id: UUID = Field(default_factory=uuid4, description="Check identifier")
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Tenant ID"
    )
    ticket_id: str = Field(..., min_length=1, max_length=255, description="Ticket ID")
    check_type: str = Field(
        ...,
        pattern=r"^(pii|dlp|policy|security|gdpr|hipaa)$",
        description="Compliance check type"
    )
    passed: bool = Field(..., description="Whether check passed")
    violations: List[str] = Field(default_factory=list, description="Violations found")
    severity: str = Field(
        ...,
        pattern=r"^(low|medium|high|critical)$",
        description="Severity level"
    )
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")


# ============================================================================
# Pagination Models
# ============================================================================

class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    model_config = ConfigDict(from_attributes=True)

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page (max 100)")
    sort_by: str = Field("created_at", description="Sort field")
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort order")


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper"""
    model_config = ConfigDict(from_attributes=True)

    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    model_config = ConfigDict(from_attributes=True)

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
