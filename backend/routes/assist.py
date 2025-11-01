"""
AI Assist API routes

Provides AI-powered ticket assistance endpoints:
- POST /api/assist/{ticket_id}/suggest - Generate AI suggestions
- POST /api/assist/{ticket_id}/approve - Process agent approval/rejection

Integrates with:
- LangGraph Orchestrator for workflow execution
- FreshdeskClient for ticket updates
- AgentDB for context retrieval
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List, Optional
import time
from datetime import datetime

from backend.agents.orchestrator import compile_workflow
from backend.services.freshdesk import FreshdeskClient
from backend.services.supabase_client import SupabaseService
from backend.models.schemas import (
    TicketContext,
    SearchResult,
    ProposedAction,
    ApprovalStatus,
    SourceType,
)
from backend.models.graph_state import create_initial_state, typed_dict_to_pydantic
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class AssistRequest(BaseModel):
    """
    AI assist request model

    Contains full ticket context for AI processing.
    """
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str = Field(..., description="Freshdesk ticket ID")
    ticket_content: str = Field(..., min_length=1, description="Ticket description/body")
    ticket_meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Ticket metadata (subject, status, priority, etc.)"
    )


class SimilarCase(BaseModel):
    """Similar case model for response"""
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str = Field(..., description="Ticket ID")
    summary: str = Field(..., description="Case summary")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")


class KBProcedure(BaseModel):
    """KB procedure model for response"""
    model_config = ConfigDict(from_attributes=True)

    doc_id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Procedure title")
    steps: List[str] = Field(..., description="Procedure steps")


class AssistResponse(BaseModel):
    """
    AI assist response model

    Contains AI-generated suggestions for agent review.
    """
    model_config = ConfigDict(from_attributes=True)

    draft_response: str = Field(..., description="AI-generated draft response")
    field_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Suggested ticket field updates"
    )
    similar_cases: List[SimilarCase] = Field(
        default_factory=list,
        description="Similar cases found"
    )
    kb_procedures: List[KBProcedure] = Field(
        default_factory=list,
        description="Relevant KB procedures"
    )
    justification: str = Field(..., description="Justification for suggestions")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")


class ApprovalRequest(BaseModel):
    """
    Agent approval request model

    Contains agent's decision and modifications.
    """
    model_config = ConfigDict(from_attributes=True)

    status: ApprovalStatus = Field(..., description="Approval status (approved/modified/rejected)")
    final_response: Optional[str] = Field(None, description="Final approved/modified response")
    final_field_updates: Optional[Dict[str, Any]] = Field(
        None,
        description="Final field updates after modification"
    )
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection")
    agent_id: Optional[str] = Field(None, description="Agent who made the decision")


class ExecutionResult(BaseModel):
    """
    Execution result model

    Contains result of approval execution.
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="Whether execution succeeded")
    ticket_id: str = Field(..., description="Ticket ID")
    updates_applied: List[str] = Field(
        default_factory=list,
        description="List of updates successfully applied"
    )
    message: str = Field(..., description="Result message")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# Helper Functions
# ============================================================================

def convert_search_result_to_similar_case(result: SearchResult) -> SimilarCase:
    """Convert SearchResult to SimilarCase"""
    return SimilarCase(
        ticket_id=result.ticket_id or result.id.hex[:8],
        summary=result.excerpt or result.content[:100],
        similarity_score=result.score
    )


def convert_search_result_to_kb_procedure(result: SearchResult) -> KBProcedure:
    """Convert SearchResult to KBProcedure"""
    # Parse steps from content (assuming newline-separated steps)
    steps = [
        step.strip()
        for step in result.content.split('\n')
        if step.strip()
    ]

    return KBProcedure(
        doc_id=result.article_id or result.id.hex[:8],
        title=result.excerpt or "Procedure",
        steps=steps[:5]  # Limit to 5 steps for response
    )


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/{ticket_id}/suggest", response_model=AssistResponse)
async def suggest_solution(ticket_id: str, request: AssistRequest):
    """
    Generate AI-powered solution suggestions

    Workflow:
    1. Create TicketContext from request
    2. Initialize AgentState with ticket context
    3. Execute LangGraph Orchestrator workflow
    4. Extract and return ProposedAction as AssistResponse

    Args:
        ticket_id: Freshdesk ticket ID (path parameter)
        request: AssistRequest with ticket content and metadata

    Returns:
        AssistResponse with AI suggestions

    Raises:
        HTTPException 422: Invalid request data
        HTTPException 500: Orchestrator execution error
        HTTPException 504: Workflow timeout
    """
    start_time = time.time()
    logger.info(f"Received assist request for ticket {ticket_id}")

    try:
        # 1. Validate ticket_id matches request
        if ticket_id != request.ticket_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ticket ID mismatch: path={ticket_id}, body={request.ticket_id}"
            )

        # 2. Create TicketContext from request
        try:
            ticket_context = TicketContext(
                ticket_id=request.ticket_id,
                tenant_id=request.ticket_meta.get("tenant_id", "default"),
                subject=request.ticket_meta.get("subject", "No subject"),
                description=request.ticket_content,
                status=request.ticket_meta.get("status", "open"),
                priority=request.ticket_meta.get("priority", "medium"),
                product=request.ticket_meta.get("product"),
                component=request.ticket_meta.get("component"),
                tags=request.ticket_meta.get("tags", []),
                custom_fields=request.ticket_meta.get("custom_fields"),
            )
        except Exception as e:
            logger.error(f"Failed to create TicketContext: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid ticket metadata: {str(e)}"
            )

        # 3. Initialize AgentState
        initial_state = create_initial_state(ticket_context)
        logger.debug(f"Created initial state for ticket {ticket_id}")

        # 4. Compile and execute workflow
        try:
            logger.info(f"Compiling LangGraph workflow for ticket {ticket_id}")
            workflow = compile_workflow()

            logger.info(f"Executing workflow for ticket {ticket_id}")
            result_state = await workflow.ainvoke(initial_state)

            execution_time = time.time() - start_time
            logger.info(f"Workflow completed for ticket {ticket_id} in {execution_time:.2f}s")

        except TimeoutError:
            logger.error(f"Workflow timeout for ticket {ticket_id}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Workflow execution timed out. Please try again."
            )
        except Exception as e:
            logger.error(f"Workflow execution error for ticket {ticket_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Workflow execution failed: {str(e)}"
            )

        # 5. Extract ProposedAction from result state
        proposed_action_data = result_state.get("proposed_action")
        if not proposed_action_data:
            logger.error(f"No proposed action in workflow result for ticket {ticket_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workflow did not produce a proposed action"
            )

        # 6. Convert to Pydantic model for validation
        try:
            pydantic_state = typed_dict_to_pydantic(result_state)
            proposed_action = pydantic_state.proposed_action
        except Exception as e:
            logger.error(f"Failed to convert workflow result to Pydantic: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process workflow result: {str(e)}"
            )

        # 7. Convert to AssistResponse
        similar_cases = [
            convert_search_result_to_similar_case(case)
            for case in proposed_action.similar_cases
        ]

        kb_procedures = [
            convert_search_result_to_kb_procedure(kb)
            for kb in proposed_action.kb_procedures
        ]

        response = AssistResponse(
            draft_response=proposed_action.draft_response,
            field_updates=proposed_action.proposed_field_updates,
            similar_cases=similar_cases,
            kb_procedures=kb_procedures,
            justification=proposed_action.justification,
            confidence=proposed_action.confidence
        )

        logger.info(
            f"Successfully generated suggestions for ticket {ticket_id} "
            f"(confidence={proposed_action.confidence:.2f})"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in suggest_solution for ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/{ticket_id}/approve", response_model=ExecutionResult)
async def approve_suggestion(ticket_id: str, approval: ApprovalRequest):
    """
    Process agent approval and execute Freshdesk updates

    Workflow:
    1. Validate approval request
    2. If approved: Apply updates to Freshdesk ticket
    3. If modified: Re-run orchestrator with modifications
    4. If rejected: Log rejection reason
    5. Return execution result

    Args:
        ticket_id: Freshdesk ticket ID (path parameter)
        approval: ApprovalRequest with agent's decision

    Returns:
        ExecutionResult with success status and details

    Raises:
        HTTPException 422: Invalid approval data
        HTTPException 500: Freshdesk update error
    """
    logger.info(
        f"Received approval request for ticket {ticket_id}: status={approval.status.value}"
    )

    try:
        # 1. Initialize Freshdesk client and Supabase service
        freshdesk_client = FreshdeskClient()
        supabase_service = SupabaseService()
        updates_applied = []

        # 2. Handle approval status
        if approval.status == ApprovalStatus.APPROVED:
            # Apply approved suggestions to Freshdesk
            logger.info(f"Applying approved suggestions to ticket {ticket_id}")

            try:
                # Post approved response as reply
                if approval.final_response:
                    await freshdesk_client.post_reply(
                        ticket_id=ticket_id,
                        body=approval.final_response,
                        private=False  # Public reply to customer
                    )
                    updates_applied.append("Posted reply to customer")
                    logger.info(f"Posted reply to ticket {ticket_id}")

                # Apply field updates
                if approval.final_field_updates:
                    await freshdesk_client.update_ticket_fields(
                        ticket_id=ticket_id,
                        updates=approval.final_field_updates
                    )
                    updates_applied.append(
                        f"Updated fields: {', '.join(approval.final_field_updates.keys())}"
                    )
                    logger.info(
                        f"Updated {len(approval.final_field_updates)} fields for ticket {ticket_id}"
                    )

                # Log approval to Supabase
                try:
                    # Get ticket data for tenant_id extraction
                    ticket_data = await freshdesk_client.get_ticket(ticket_id)
                    tenant_id = ticket_data.get("custom_fields", {}).get("cf_tenant_id", "default")

                    await supabase_service.log_approval({
                        "tenant_id": tenant_id,
                        "ticket_id": ticket_id,
                        "draft_response": None,  # Not available in approval request
                        "final_response": approval.final_response,
                        "field_updates": approval.final_field_updates,
                        "approval_status": "approved",
                        "agent_id": approval.agent_id or "unknown",
                        "feedback_notes": None
                    })
                    updates_applied.append("Logged approval to Supabase")
                    logger.info(f"Logged approval to Supabase for ticket {ticket_id}")
                except Exception as e:
                    # Don't fail the entire operation if Supabase logging fails
                    logger.warning(f"Failed to log approval to Supabase for ticket {ticket_id}: {e}")

                return ExecutionResult(
                    success=True,
                    ticket_id=ticket_id,
                    updates_applied=updates_applied,
                    message=f"Successfully applied approved suggestions to ticket {ticket_id}"
                )

            except Exception as e:
                logger.error(f"Failed to apply updates to ticket {ticket_id}: {e}")
                return ExecutionResult(
                    success=False,
                    ticket_id=ticket_id,
                    updates_applied=updates_applied,
                    message="Partial update failure",
                    error=str(e)
                )

        elif approval.status == ApprovalStatus.MODIFIED:
            # Re-run orchestrator with modifications
            logger.info(f"Re-running orchestrator with modifications for ticket {ticket_id}")

            try:
                # Get original ticket data
                ticket_data = await freshdesk_client.get_ticket(ticket_id)

                # Create modified AssistRequest
                modified_request = AssistRequest(
                    ticket_id=ticket_id,
                    ticket_content=approval.final_response or ticket_data.get("description", ""),
                    ticket_meta={
                        "tenant_id": ticket_data.get("custom_fields", {}).get("cf_tenant_id", "default"),
                        "subject": ticket_data.get("subject", ""),
                        "status": ticket_data.get("status", "open"),
                        "priority": ticket_data.get("priority", "medium"),
                        "product": ticket_data.get("product", ""),
                        "component": ticket_data.get("custom_fields", {}).get("cf_component"),
                        "tags": ticket_data.get("tags", []),
                        "custom_fields": approval.final_field_updates or {},
                    }
                )

                # Re-run suggestion workflow
                modified_result = await suggest_solution(ticket_id, modified_request)

                logger.info(f"Re-ran orchestrator for ticket {ticket_id} with modifications")

                # Log modification to Supabase
                try:
                    tenant_id = ticket_data.get("custom_fields", {}).get("cf_tenant_id", "default")
                    await supabase_service.log_approval({
                        "tenant_id": tenant_id,
                        "ticket_id": ticket_id,
                        "draft_response": None,  # Original draft not available
                        "final_response": approval.final_response,
                        "field_updates": approval.final_field_updates,
                        "approval_status": "modified",
                        "agent_id": approval.agent_id or "unknown",
                        "feedback_notes": f"Re-executed with modifications. New confidence: {modified_result.confidence:.2f}"
                    })
                    logger.info(f"Logged modification to Supabase for ticket {ticket_id}")
                except Exception as e:
                    logger.warning(f"Failed to log modification to Supabase for ticket {ticket_id}: {e}")

                return ExecutionResult(
                    success=True,
                    ticket_id=ticket_id,
                    updates_applied=["Re-executed workflow with modifications", "Logged to Supabase"],
                    message=f"Workflow re-executed with modifications. New confidence: {modified_result.confidence:.2f}"
                )

            except Exception as e:
                logger.error(f"Failed to re-run orchestrator for ticket {ticket_id}: {e}")
                return ExecutionResult(
                    success=False,
                    ticket_id=ticket_id,
                    updates_applied=[],
                    message="Failed to re-execute workflow",
                    error=str(e)
                )

        elif approval.status == ApprovalStatus.REJECTED:
            # Log rejection
            logger.info(
                f"Suggestion rejected for ticket {ticket_id}: {approval.rejection_reason}"
            )

            # Add internal note about rejection
            try:
                await freshdesk_client.add_note(
                    ticket_id=ticket_id,
                    note_body=f"AI suggestion rejected by {approval.agent_id or 'agent'}. "
                              f"Reason: {approval.rejection_reason or 'No reason provided'}",
                    private=True
                )
                updates_applied.append("Added rejection note to ticket")
            except Exception as e:
                logger.warning(f"Failed to add rejection note to ticket {ticket_id}: {e}")

            # Log rejection to Supabase
            try:
                # Get ticket data for tenant_id extraction
                ticket_data = await freshdesk_client.get_ticket(ticket_id)
                tenant_id = ticket_data.get("custom_fields", {}).get("cf_tenant_id", "default")

                await supabase_service.log_approval({
                    "tenant_id": tenant_id,
                    "ticket_id": ticket_id,
                    "draft_response": None,  # Not available in approval request
                    "final_response": None,  # Rejected, no final response
                    "field_updates": None,
                    "approval_status": "rejected",
                    "agent_id": approval.agent_id or "unknown",
                    "feedback_notes": approval.rejection_reason or "No reason provided"
                })
                updates_applied.append("Logged rejection to Supabase")
                logger.info(f"Logged rejection to Supabase for ticket {ticket_id}")
            except Exception as e:
                logger.warning(f"Failed to log rejection to Supabase for ticket {ticket_id}: {e}")

            return ExecutionResult(
                success=True,
                ticket_id=ticket_id,
                updates_applied=updates_applied,
                message=f"Suggestion rejected: {approval.rejection_reason or 'No reason provided'}"
            )

        else:
            logger.error(f"Unknown approval status: {approval.status}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid approval status: {approval.status}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in approve_suggestion for ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
