"""
AI Assistant API Routes

Handles ticket analysis, proposal approval, and refinement with
Server-Sent Events (SSE) streaming for real-time progress updates.

Author: AI Assistant POC
Date: 2025-11-05
"""

from fastapi import APIRouter, HTTPException, Header, status, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, AsyncGenerator
import asyncio
import json
import logging
import time

from backend.repositories.tenant_repository import TenantRepository
from backend.repositories.proposal_repository import ProposalRepository
from backend.utils.pii_masker import mask_pii_in_dict
from backend.utils.token_counter import get_token_counter
from backend.utils.chunking import TicketChunker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assist", tags=["assist"])

# Initialize repositories
tenant_repo = TenantRepository()
proposal_repo = ProposalRepository()


# Request/Response Models

class AnalyzeRequest(BaseModel):
    """Request model for ticket analysis."""
    ticket_id: str
    stream_progress: bool = True


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

        # TODO: Fetch ticket data from Freshdesk
        # For POC, mock ticket data
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

        if request.stream_progress:
            # Return SSE stream
            return StreamingResponse(
                sse_generator(
                    _analyze_with_streaming(ticket_data, config)
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )
        else:
            # Return single JSON response
            proposal = await _analyze_ticket(ticket_data, config)
            return {"proposal": proposal.dict()}

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


async def _analyze_with_streaming(
    ticket_data: Dict[str, Any],
    config
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Analyze ticket with streaming progress events.

    Args:
        ticket_data: Ticket information
        config: Tenant configuration

    Yields:
        Progress events
    """
    start_time = time.time()

    try:
        # Step 1: Router decision
        yield {
            "type": "router_decision",
            "decision": "retrieve_cases" if config.embedding_enabled else "propose_solution_direct",
            "reasoning": "Embedding mode enabled" if config.embedding_enabled else "Embedding mode disabled",
            "embedding_mode": config.embedding_enabled
        }

        await asyncio.sleep(0.5)  # Simulate processing

        # Step 2: Retrieval (if enabled)
        if config.embedding_enabled:
            yield {"type": "retriever_start", "mode": "embedding"}
            await asyncio.sleep(1)

            # Simulate search (would call actual retriever)
            # For POC, return empty results
            yield {
                "type": "retriever_results",
                "results": {
                    "similar_cases": [],
                    "kb_articles": []
                },
                "result_count": 0
            }

        # Step 3: Resolution
        yield {"type": "resolution_start"}
        await asyncio.sleep(1)

        # Generate proposal
        proposal = await _analyze_ticket(ticket_data, config)

        # Final event
        analysis_time = int((time.time() - start_time) * 1000)
        yield {
            "type": "resolution_complete",
            "proposal": proposal.dict(),
            "analysis_time_ms": analysis_time
        }

    except Exception as e:
        logger.error(f"Streaming analysis error: {e}")
        yield {
            "type": "error",
            "message": str(e),
            "recoverable": False
        }


async def _analyze_ticket(ticket_data: Dict[str, Any], config):
    """
    Core analysis logic (direct mode for POC).

    Args:
        ticket_data: Ticket information
        config: Tenant configuration

    Returns:
        Created Proposal object
    """
    # Check token count and chunk if needed
    chunker = TicketChunker(max_tokens=config.llm_max_tokens)
    chunked = chunker.chunk_ticket(ticket_data)

    # TODO: Call LLM service for analysis
    # For POC, create mock proposal
    draft_response = f"Thank you for contacting us. Based on the issue description, please try the following steps:\n\n1. Clear browser cache and cookies\n2. Use incognito mode\n3. Try different browser\n\nIf issue persists, please contact support."

    # Create proposal
    proposal_data = {
        "tenant_id": config.tenant_id,
        "ticket_id": ticket_data["id"],
        "draft_response": draft_response,
        "field_updates": {"status": "pending", "priority": "high"},
        "confidence": "medium",
        "mode": "direct",
        "reasoning": "Generated using direct analysis mode (no search results)",
        "similar_cases": [],
        "kb_references": [],
        "token_count": chunked["metadata"]["token_count"]
    }

    proposal = await proposal_repo.create(proposal_data)
    return proposal


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
