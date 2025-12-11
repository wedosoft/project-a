"""
AI Assistant API Routes

Handles ticket analysis, proposal approval, and refinement with
Server-Sent Events (SSE) streaming for real-time progress updates.

Author: AI Assistant POC
Date: 2025-11-05
"""

from fastapi import APIRouter, HTTPException, Header, status, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, AsyncGenerator
import asyncio
import json
import logging
import time

from backend.repositories.tenant_repository import TenantRepository
from backend.repositories.proposal_repository import ProposalRepository
from backend.services.orchestrator import OrchestratorService
from backend.utils.pii_masker import mask_pii_in_dict
from backend.utils.token_counter import get_token_counter
from backend.utils.chunking import TicketChunker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assist", tags=["assist"])

# Initialize services and repositories
tenant_repo = TenantRepository()
proposal_repo = ProposalRepository()
orchestrator = OrchestratorService()


# Request/Response Models

class AnalyzeRequest(BaseModel):
    """Request model for ticket analysis."""
    ticket_id: str
    subject: Optional[str] = None
    description: Optional[str] = None
    stream_progress: bool = True
    async_mode: bool = False


class AnalyzeResponse(BaseModel):
    """Response when async_mode is enabled"""
    proposal: Dict[str, Any]
    status_url: str


class ApproveRequest(BaseModel):
    """Request model for proposal approval."""
    ticket_id: str
    proposal_id: str
    action: str  # approve | reject
    final_response: Optional[str] = None
    rejection_reason: Optional[str] = None
    agent_email: Optional[str] = None


class RefineRequest(BaseModel):
    """Request model for proposal refinement."""
    ticket_id: str
    proposal_id: str
    refinement_request: str
    agent_email: Optional[str] = None


class ProposalStatusResponse(BaseModel):
    """Response schema for proposal status polling."""
    id: str
    status: str
    tenant_id: str
    ticket_id: str
    proposal_version: int
    draft_response: Optional[str] = None
    field_updates: Dict[str, Any] = Field(default_factory=dict)
    field_reasons: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[str] = None
    mode: Optional[str] = None
    similar_cases: Optional[Any] = None
    kb_references: Optional[Any] = None
    analysis_time_ms: Optional[int] = None


# SSE Streaming Helper

async def sse_generator(
    events: AsyncGenerator[Dict[str, Any], None]
) -> AsyncGenerator[str, None]:
    """
    Convert event stream to SSE format.

    Args:
        events: Async generator of event dictionaries

    Yields:
        SSE-formatted strings

    Format:
        data: {"type": "event_name", "data": {...}}\\n\\n
    """
    last_heartbeat = time.time()

    try:
        async for event in events:
            # Mask PII in event data
            masked_event = mask_pii_in_dict(event)

            # Send event
            yield f"data: {json.dumps(masked_event)}\n\n"

            # Send heartbeat if >30s since last event
            if time.time() - last_heartbeat > 30:
                heartbeat = {"type": "heartbeat", "timestamp": time.time()}
                yield f"data: {json.dumps(heartbeat)}\n\n"
                last_heartbeat = time.time()

    except Exception as e:
        logger.error(f"SSE streaming error: {e}")
        error_event = {
            "type": "error",
            "message": str(e),
            "recoverable": False
        }
        yield f"data: {json.dumps(error_event)}\n\n"


# Routes

# Analyze endpoints
@router.post("/analyze")
async def analyze_ticket(
    request: AnalyzeRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    platform: str = Header(..., alias="X-Platform")
):
    """
    Analyze ticket and generate AI proposal with optional streaming.

    Args:
        request: Analysis request with ticket_id
        tenant_id: Tenant identifier from header
        platform: Platform name from header

    Returns:
        StreamingResponse with SSE events or JSON response

    Events:
        - router_decision: Embedding mode decision
        - retriever_start: Search initiated
        - retriever_results: Search results found
        - retriever_fallback: Search failed, using direct analysis
        - resolution_start: Proposal generation started
        - resolution_complete: Proposal ready
        - heartbeat: Keep-alive ping (every 30s)
        - error: Error occurred

    Example:
        >>> # Client-side JavaScript
        >>> const eventSource = new EventSource('/api/v1/assist/analyze');
        >>> eventSource.onmessage = (event) => {
        ...     const data = JSON.parse(event.data);
        ...     console.log(data.type, data);
        ... };
    """
    try:
        # Set tenant context for RLS
        await tenant_repo.set_tenant_context(tenant_id)
        await proposal_repo.set_tenant_context(tenant_id)

        # Get tenant config
        config = await tenant_repo.get_config(tenant_id, platform)

        # Use provided ticket data if available, otherwise fallback to mock
        if request.subject and request.description:
            ticket_data = {
                "id": request.ticket_id,
                "subject": request.subject,
                "description": request.description,
                "conversations": [] # Conversations not passed from frontend yet
            }
        else:
            # For POC, mock ticket data if not provided
            ticket_data = {
                "id": request.ticket_id,
                "subject": "Cannot login to dashboard",
                "description": "User unable to access dashboard after password reset",
                "conversations": [
                    {"body": "I tried resetting password but still can't login", "user_id": 1},
                    {"body": "Have you cleared browser cache?", "user_id": 2},
                    {"body": "Yes, still not working", "user_id": 1}
                ]
            }

        if request.async_mode and request.stream_progress:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="async_mode is only supported with stream_progress=False"
            )

        if request.async_mode:
            result = await orchestrator.process_ticket(
                ticket_context=ticket_data,
                tenant_id=tenant_id,
                platform=platform,
                stream_events=False
            )

            proposal_id = result.get("id")
            return AnalyzeResponse(
                proposal=result,
                status_url=f"/api/assist/status/{proposal_id}"
            )

        if request.stream_progress:
            # Return SSE stream with orchestrator
            events = await orchestrator.process_ticket(
                ticket_context=ticket_data,
                tenant_id=tenant_id,
                platform=platform,
                stream_events=True
            )
            return StreamingResponse(
                sse_generator(events),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )
        else:
            # Return single JSON response with orchestrator
            result = await orchestrator.process_ticket(
                ticket_context=ticket_data,
                tenant_id=tenant_id,
                platform=platform,
                stream_events=False
            )
            return {"proposal": result}

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


# Note: _analyze_with_streaming and _analyze_ticket are now handled by orchestrator
# These functions are removed as orchestrator.process_ticket() handles both streaming and direct modes


# Approval endpoints
@router.post("/approve")
async def approve_proposal(
    request: ApproveRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """
    Approve or reject a proposal.

    Args:
        request: Approval request
        tenant_id: Tenant identifier

    Returns:
        Updated proposal with field updates for FDK insertion

    Example:
        >>> POST /api/v1/assist/approve
        >>> {
        ...     "ticket_id": "TKT-123",
        ...     "proposal_id": "prop-uuid",
        ...     "action": "approve",
        ...     "agent_email": "agent@example.com"
        ... }
    """
    try:
        await proposal_repo.set_tenant_context(tenant_id)

        # Get proposal
        proposal = await proposal_repo.get_by_id(request.proposal_id)
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {request.proposal_id} not found"
            )

        # Update status
        if request.action == "approve":
            await proposal_repo.update_status(
                request.proposal_id,
                "approved",
                approved_by=request.agent_email
            )

            # Log approval
            await proposal_repo.log_approval_action(
                request.proposal_id,
                "approve",
                agent_email=request.agent_email
            )

            # TODO: Update Freshdesk ticket with field_updates
            # For POC, return field_updates for FDK to apply

            return {
                "status": "approved",
                "field_updates": proposal.field_updates,
                "final_response": request.final_response or proposal.draft_response
            }

        elif request.action == "reject":
            await proposal_repo.update_status(
                request.proposal_id,
                "rejected",
                rejection_reason=request.rejection_reason
            )

            # Log rejection
            await proposal_repo.log_approval_action(
                request.proposal_id,
                "reject",
                agent_email=request.agent_email,
                feedback=request.rejection_reason
            )

            return {
                "status": "rejected",
                "reason": request.rejection_reason
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {request.action}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Refinement endpoints
@router.post("/refine")
async def refine_proposal(
    request: RefineRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """
    Refine a proposal based on agent feedback.

    Args:
        request: Refinement request
        tenant_id: Tenant identifier

    Returns:
        New proposal version with refined response

    Example:
        >>> POST /api/v1/assist/refine
        >>> {
        ...     "ticket_id": "TKT-123",
        ...     "proposal_id": "prop-uuid",
        ...     "refinement_request": "Make response more empathetic"
        ... }
    """
    try:
        await proposal_repo.set_tenant_context(tenant_id)

        # Get original proposal
        original = await proposal_repo.get_by_id(request.proposal_id)
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {request.proposal_id} not found"
            )

        # TODO: Call LLM for refinement
        # For POC, append refinement note
        refined_response = f"{original.draft_response}\n\n[Refined based on feedback: {request.refinement_request}]"

        # Create new version
        refined_data = {
            "draft_response": refined_response,
            "field_updates": original.field_updates,
            "confidence": original.confidence,
            "mode": original.mode,
            "reasoning": f"Refined from version {original.proposal_version}: {request.refinement_request}"
        }

        new_proposal = await proposal_repo.create_version(
            request.proposal_id,
            refined_data
        )

        # Log refinement action
        await proposal_repo.log_approval_action(
            request.proposal_id,
            "refine",
            agent_email=request.agent_email,
            feedback=request.refinement_request
        )

        return {
            "proposal": new_proposal.dict(),
            "version": new_proposal.proposal_version
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refinement error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Status endpoint
@router.get("/status/{proposal_id}")
async def get_proposal_status(
    proposal_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """
    Get the status of a proposal by its ID.
    
    Args:
        proposal_id: Proposal identifier
        tenant_id: Tenant identifier
        
    Returns:
        Proposal status and data
        
    Example:
        >>> GET /api/v1/assist/status/prop-uuid
    """
    try:
        await proposal_repo.set_tenant_context(tenant_id)
        
        # Get proposal
        proposal = await proposal_repo.get_by_id(proposal_id)
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {proposal_id} not found"
            )
        
        # Return proposal data
        return {
            "id": proposal.id,
            "status": proposal.status,
            "tenant_id": proposal.tenant_id,
            "ticket_id": proposal.ticket_id,
            "proposal_version": proposal.proposal_version,
            "draft_response": proposal.draft_response,
            "field_updates": proposal.field_updates or {},
            "field_reasons": proposal.field_reasons,
            "summary": proposal.summary,
            "intent": proposal.intent,
            "sentiment": proposal.sentiment,
            "confidence": proposal.confidence,
            "mode": proposal.mode,
            "similar_cases": proposal.similar_cases,
            "kb_references": proposal.kb_references,
            "analysis_time_ms": proposal.analysis_time_ms,
            "field_proposals": proposal.field_proposals
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class ProposalStatusResponse(BaseModel):
    """Response schema for proposal status polling."""
    id: str
    status: str
    tenant_id: str
    ticket_id: str
    proposal_version: int
    draft_response: Optional[str] = None
    field_updates: Dict[str, Any]
    field_reasons: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[str] = None
    mode: Optional[str] = None
    similar_cases: Optional[Any] = None
    kb_references: Optional[Any] = None
    analysis_time_ms: Optional[int] = None
