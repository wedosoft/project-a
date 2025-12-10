"""
Orchestrator Service - LangGraph integration

Coordinates retriever and resolver agents for ticket analysis.

POC Implementation:
- Integrates with tenant_configs for routing decisions
- Uses issue_blocks and kb_blocks for search
- Creates proposals in database via ProposalRepository
- Supports streaming progress events

Author: AI Assistant POC
Date: 2025-11-05
"""

import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator
from backend.models.graph_state import AgentState
from backend.agents.retriever import retrieve_cases, retrieve_kb
from backend.agents.resolver import propose_solution, propose_field_updates
from backend.repositories.tenant_repository import TenantRepository
from backend.repositories.proposal_repository import ProposalRepository
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class OrchestratorService:
    """
    Service layer for LangGraph workflow orchestration.

    Workflow:
    1. Load tenant config
    2. Decide: retrieve (if embedding enabled) or direct analysis
    3. If retrieve: search issue_blocks + kb_blocks
    4. Generate solution proposal
    5. Generate field update recommendations
    6. Save proposal to database
    """

    def __init__(self):
        self.tenant_repo = TenantRepository()
        self.proposal_repo = ProposalRepository()

    async def process_ticket(
        self,
        ticket_context: Dict[str, Any],
        tenant_id: str,
        platform: str,
        stream_events: bool = False
    ) -> Dict[str, Any]:
        """
        Process ticket through LangGraph workflow.

        Args:
            ticket_context: Ticket data (id, subject, description, etc.)
            tenant_id: Tenant identifier for RLS
            platform: Platform name (freshdesk, zendesk, etc.)
            stream_events: Enable streaming progress events

        Returns:
            Proposal object with draft response and field updates
        """
        try:
            # Set tenant context for RLS
            await self.tenant_repo.set_tenant_context(tenant_id)
            await self.proposal_repo.set_tenant_context(tenant_id)

            # Get tenant config
            config = await self.tenant_repo.get_config(tenant_id, platform)

            if stream_events:
                # Return async generator for SSE streaming
                return self._process_with_streaming(ticket_context, config, tenant_id)
            else:
                # Return single response
                proposal = await self._process_direct(ticket_context, config, tenant_id)
                return proposal.dict()

        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            raise

    async def _process_direct(
        self,
        ticket_context: Dict[str, Any],
        config,
        tenant_id: str
    ):
        """
        Process ticket without streaming (direct mode).

        Args:
            ticket_context: Ticket data
            config: Tenant configuration
            tenant_id: Tenant identifier

        Returns:
            Proposal object
        """
        start_time = time.time()

        # Initialize state
        state: AgentState = {
            "ticket_context": ticket_context,
            "tenant_config": config.dict() if hasattr(config, 'dict') else config,
            "search_results": {
                "similar_cases": [],
                "kb_procedures": [],
                "total_results": 0
            },
            "proposed_action": {},
            "errors": []
        }

        # Step 1: Retrieval (if embedding enabled)
        if config.embedding_enabled:
            logger.info("Embedding enabled, executing retrieval workflow")
            state = await retrieve_cases(state)
            state = await retrieve_kb(state)
        else:
            logger.info("Embedding disabled, skipping retrieval")

        # Step 2: Generate solution proposal
        state = await propose_solution(state)

        # Step 3: Generate field updates
        state = await propose_field_updates(state)

        # Step 4: Save to database
        analysis_time_ms = int((time.time() - start_time) * 1000)
        proposal = await self._save_proposal(state, tenant_id, analysis_time_ms)

        return proposal

    async def _process_with_streaming(
        self,
        ticket_context: Dict[str, Any],
        config,
        tenant_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process ticket with streaming progress events.

        Args:
            ticket_context: Ticket data
            config: Tenant configuration
            tenant_id: Tenant identifier

        Yields:
            Progress events for SSE
        """
        start_time = time.time()

        try:
            # Initialize state
            state: AgentState = {
                "ticket_context": ticket_context,
                "tenant_config": config.dict() if hasattr(config, 'dict') else config,
                "search_results": {
                    "similar_cases": [],
                    "kb_procedures": [],
                    "total_results": 0
                },
                "proposed_action": {},
                "errors": []
            }

            # Event 1: Router decision
            yield {
                "type": "router_decision",
                "decision": "retrieve_cases" if config.embedding_enabled else "propose_solution_direct",
                "reasoning": "Embedding mode enabled" if config.embedding_enabled else "Embedding mode disabled",
                "embedding_enabled": config.embedding_enabled,
                "analysis_depth": config.analysis_depth
            }

            # Step 1: Retrieval (if enabled)
            if config.embedding_enabled:
                # Event 2: Retriever start
                yield {"type": "retriever_start", "mode": "embedding"}

                # Execute retrieval
                state = await retrieve_cases(state)
                state = await retrieve_kb(state)

                # Event 3: Retriever results
                search_results = state.get("search_results", {})
                yield {
                    "type": "retriever_results",
                    "similar_cases_count": len(search_results.get("similar_cases", [])),
                    "kb_articles_count": len(search_results.get("kb_procedures", [])),
                    "total_results": search_results.get("total_results", 0)
                }

            # Step 2: Resolution
            # Event 4: Resolution start
            yield {"type": "resolution_start"}

            # Generate solution
            state = await propose_solution(state)

            # Generate field updates
            state = await propose_field_updates(state)

            # Step 3: Save to database
            analysis_time_ms = int((time.time() - start_time) * 1000)
            proposal = await self._save_proposal(state, tenant_id, analysis_time_ms)

            # Event 5: Resolution complete
            yield {
                "type": "resolution_complete",
                "proposal_id": proposal.id,
                "confidence": proposal.confidence,
                "mode": proposal.mode,
                "analysis_time_ms": analysis_time_ms
            }

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {
                "type": "error",
                "message": str(e),
                "recoverable": False
            }

    async def _save_proposal(
        self,
        state: AgentState,
        tenant_id: str,
        analysis_time_ms: int
    ):
        """
        Save proposal to database from agent state.

        Args:
            state: Agent state with proposed_action
            tenant_id: Tenant identifier
            analysis_time_ms: Analysis duration

        Returns:
            Created Proposal object
        """
        proposed_action = state.get("proposed_action", {})
        ticket_context = state.get("ticket_context", {})

        # Build proposal data
        reasoning = proposed_action.get("reasoning", "")
        justification = proposed_action.get("justification", "")
        combined_reasoning = f"{reasoning}\n\n[Field Updates]: {justification}".strip() if justification else reasoning

        proposal_data = {
            "tenant_id": tenant_id,
            "ticket_id": str(proposed_action.get("ticket_id", ticket_context.get("id", "unknown"))),
            "draft_response": proposed_action.get("draft_response", ""),
            "field_updates": proposed_action.get("proposed_field_updates", {}),
            "reasoning": combined_reasoning,
            "confidence": proposed_action.get("confidence", "medium"),
            "mode": proposed_action.get("mode", "direct"),
            "similar_cases": proposed_action.get("similar_cases", []),
            "kb_references": proposed_action.get("kb_references", []),
            "analysis_time_ms": analysis_time_ms
        }

        # Create proposal
        proposal = await self.proposal_repo.create(proposal_data)
        logger.info(f"Created proposal {proposal.id} for ticket {proposal.ticket_id}")

        return proposal
