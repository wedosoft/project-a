"""
Resolution Agent - AI-generated solution proposal
"""

import asyncio
from backend.models.graph_state import AgentState
from backend.config import get_settings
from backend.utils.logger import get_logger

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger = get_logger(__name__)
    logger.warning("google-generativeai not available, some features will be disabled")

logger = get_logger(__name__)
settings = get_settings()


async def propose_solution(state: AgentState) -> AgentState:
    """
    Generate AI-powered solution proposal using ticket context and search results

    Args:
        state: Current agent state with ticket context and search results

    Returns:
        Updated state with proposed solution
    """
    logger.info("Starting solution proposal generation")

    if not GENAI_AVAILABLE:
        logger.warning("google-generativeai not available, skipping solution generation")
        state["errors"] = state.get("errors", []) + ["google-generativeai not installed"]
        return state

    try:
        async def _generate():
            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")

            ticket_ctx = state.get("ticket_context", {})
            search_res = state.get("search_results", {})

            similar_cases = search_res.get("similar_cases", [])
            kb_procedures = search_res.get("kb_procedures", [])

            similar_text = "\n".join([
                f"- Case {i+1}: {case.get('content', 'N/A')[:200]}"
                for i, case in enumerate(similar_cases[:3])
            ])

            kb_text = "\n".join([
                f"- KB {i+1}: {kb.get('content', 'N/A')[:200]}"
                for i, kb in enumerate(kb_procedures[:3])
            ])

            prompt = f"""You are a customer support AI assistant. Generate a professional solution for this ticket.

Ticket Details:
- Subject: {ticket_ctx.get('subject', 'N/A')}
- Description: {ticket_ctx.get('description', 'N/A')}
- Priority: {ticket_ctx.get('priority', 'N/A')}

Similar Cases:
{similar_text or 'No similar cases found'}

Knowledge Base Procedures:
{kb_text or 'No KB articles found'}

Generate a clear, actionable solution that:
1. Addresses the customer's issue directly
2. Uses information from similar cases and KB articles when relevant
3. Provides step-by-step instructions if applicable
4. Maintains a professional and empathetic tone

Also provide a confidence score (0.0-1.0) based on:
- Availability of similar cases
- Clarity of the issue
- KB article relevance

Response format:
SOLUTION:
[Your solution text here]

CONFIDENCE: [0.0-1.0]
"""

            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=1024,
                )
            )

            result_text = response.text.strip()

            confidence = 0.5
            draft = result_text

            if "CONFIDENCE:" in result_text:
                parts = result_text.split("CONFIDENCE:")
                draft = parts[0].replace("SOLUTION:", "").strip()
                try:
                    confidence = float(parts[1].strip())
                except:
                    confidence = 0.5
            else:
                draft = result_text.replace("SOLUTION:", "").strip()

            confidence = max(0.0, min(1.0, confidence))

            # Get ticket_id from ticket_context
            ticket_id = state.get("ticket_context", {}).get("ticket_id", "unknown")

            # Get search results for similar_cases and kb_procedures
            search_results = state.get("search_results", {})
            similar_cases = search_results.get("similar_cases", [])
            kb_procedures = search_results.get("kb_procedures", [])

            # Initialize proposed_action with all required fields
            if "proposed_action" not in state:
                state["proposed_action"] = {}

            state["proposed_action"]["ticket_id"] = ticket_id
            state["proposed_action"]["draft_response"] = draft
            state["proposed_action"]["similar_cases"] = similar_cases
            state["proposed_action"]["kb_procedures"] = kb_procedures
            state["proposed_action"]["confidence"] = confidence
            state["proposed_action"]["justification"] = f"Generated based on {len(similar_cases)} similar cases and {len(kb_procedures)} KB articles with {confidence:.0%} confidence."

            logger.info(f"Solution generated with confidence: {confidence:.2f}")
            return state

        state = await asyncio.wait_for(_generate(), timeout=30.0)
        return state

    except asyncio.TimeoutError:
        logger.error("Solution generation timed out")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append("Solution generation timeout")
        return state

    except Exception as e:
        logger.error(f"Error generating solution: {e}")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(f"Solution generation error: {str(e)}")
        return state


async def propose_field_updates(state: AgentState) -> AgentState:
    """
    Propose ticket field updates based on ticket context and proposed solution

    Args:
        state: Current agent state with ticket context and proposed action

    Returns:
        Updated state with proposed field updates
    """
    logger.info("Starting field updates proposal")

    if not GENAI_AVAILABLE:
        logger.warning("google-generativeai not available, skipping field updates proposal")
        state["errors"] = state.get("errors", []) + ["google-generativeai not installed"]
        return state

    try:
        async def _generate():
            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")

            ticket_ctx = state.get("ticket_context", {})
            proposed = state.get("proposed_action", {})

            draft_response = proposed.get("draft_response", "")
            confidence = proposed.get("confidence", 0.5)

            prompt = f"""You are a ticket management AI. Analyze this ticket and propose field updates.

Ticket Details:
- Subject: {ticket_ctx.get('subject', 'N/A')}
- Description: {ticket_ctx.get('description', 'N/A')}
- Current Priority: {ticket_ctx.get('priority', 'N/A')}
- Current Status: {ticket_ctx.get('status', 'N/A')}

Proposed Solution:
{draft_response[:300]}

Solution Confidence: {confidence:.2f}

Based on the ticket analysis, propose appropriate field updates:
- Priority: [low/medium/high/urgent]
- Status: [open/pending/resolved/closed]
- Tags: [comma-separated relevant tags]

Also provide a brief justification for each update.

Response format:
PRIORITY: [value]
STATUS: [value]
TAGS: [tag1, tag2, tag3]
JUSTIFICATION: [Brief explanation of the updates]
"""

            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=512,
                )
            )

            result_text = response.text.strip()

            updates = {}
            justification = ""

            for line in result_text.split("\n"):
                line = line.strip()
                if line.startswith("PRIORITY:"):
                    updates["priority"] = line.split(":", 1)[1].strip().lower()
                elif line.startswith("STATUS:"):
                    updates["status"] = line.split(":", 1)[1].strip().lower()
                elif line.startswith("TAGS:"):
                    tags_str = line.split(":", 1)[1].strip()
                    updates["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()]
                elif line.startswith("JUSTIFICATION:"):
                    justification = line.split(":", 1)[1].strip()

            if "proposed_action" not in state:
                state["proposed_action"] = {}

            state["proposed_action"]["proposed_field_updates"] = updates
            state["proposed_action"]["justification"] = justification

            logger.info(f"Field updates proposed: {updates}")
            return state

        state = await asyncio.wait_for(_generate(), timeout=30.0)
        return state

    except asyncio.TimeoutError:
        logger.error("Field updates proposal timed out")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append("Field updates proposal timeout")
        return state

    except Exception as e:
        logger.error(f"Error proposing field updates: {e}")
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(f"Field updates proposal error: {str(e)}")
        return state
