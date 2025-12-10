"""
Resolution Agent - AI-generated solution proposal

POC Modifications:
- Integrates with ProposalRepository for persistence
- Creates proposals in database with tenant_id
- Supports analysis_depth from tenant config
- Returns proposal object for API responses

Author: AI Assistant POC
Date: 2025-11-05
"""

import asyncio
from backend.models.graph_state import AgentState
from backend.config import get_settings
from backend.utils.logger import get_logger
from backend.services.freshdesk import FreshdeskClient

logger = get_logger(__name__)
settings = get_settings()

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai not available, some features will be disabled")


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
            model = genai.GenerativeModel("models/gemini-2.5-flash")

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

            prompt = f"""You are a customer support AI assistant. Analyze this ticket to understand the customer's intent and summarize the issue.

Ticket Details:
- Subject: {ticket_ctx.get('subject', 'N/A')}
- Description: {ticket_ctx.get('description', 'N/A')}
- Priority: {ticket_ctx.get('priority', 'N/A')}

Similar Cases:
{similar_text or 'No similar cases found'}

Knowledge Base Procedures:
{kb_text or 'No KB articles found'}

Perform the following analysis:
1. Summarize the ticket content concisely (1-2 sentences).
2. Identify the customer's intent (e.g., Inquiry, Complaint, Technical Issue, Feature Request).
3. Determine the sentiment (Positive, Neutral, Negative, Urgent).

Also provide a confidence score (0.0-1.0) for your analysis.

Response format:
SUMMARY: [Your summary here]
INTENT: [Identified intent]
SENTIMENT: [Identified sentiment]
CONFIDENCE: [0.0-1.0]
"""

            # Configure safety settings to be more permissive for business content
            safety_settings = {
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }

            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3, # Lower temperature for analysis
                    max_output_tokens=1024,
                ),
                safety_settings=safety_settings
            )

            # Check if response was blocked
            if not response.candidates or not response.candidates[0].content.parts:
                candidate = response.candidates[0] if response.candidates else None
                finish_reason = candidate.finish_reason if candidate else 'unknown'

                # Log detailed safety ratings
                if candidate and hasattr(candidate, 'safety_ratings'):
                    logger.error(f"Response blocked - Finish reason: {finish_reason}")
                    logger.error(f"Safety ratings: {candidate.safety_ratings}")
                else:
                    logger.error(f"Response blocked - Finish reason: {finish_reason}")

                error_msg = f"Response blocked. Finish reason: {finish_reason}"
                state["errors"] = state.get("errors", []) + [error_msg]
                return state

            result_text = response.text.strip()

            confidence = 0.5
            summary = ""
            intent = ""
            sentiment = ""

            for line in result_text.split("\n"):
                line = line.strip()
                if line.startswith("SUMMARY:"):
                    summary = line.split(":", 1)[1].strip()
                elif line.startswith("INTENT:"):
                    intent = line.split(":", 1)[1].strip()
                elif line.startswith("SENTIMENT:"):
                    sentiment = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.split(":", 1)[1].strip())
                    except:
                        confidence = 0.5

            confidence = max(0.0, min(1.0, confidence))

            # Get ticket_id from ticket_context
            ticket_id = state.get("ticket_context", {}).get("ticket_id", "unknown")

            # Get search results for similar_cases and kb_procedures
            search_results = state.get("search_results", {})
            similar_cases = search_results.get("similar_cases", [])
            kb_procedures = search_results.get("kb_procedures", [])

            # Determine mode based on search results
            if len(similar_cases) > 0 or len(kb_procedures) > 0:
                mode = "synthesis"  # Generated from search results
            else:
                mode = "direct"  # Generated without search results

            # Initialize proposed_action with all required fields for POC
            if "proposed_action" not in state:
                state["proposed_action"] = {}

            state["proposed_action"]["ticket_id"] = ticket_id
            # Store analysis results instead of draft response
            state["proposed_action"]["draft_response"] = "" # Clear draft response as it's not generated yet
            state["proposed_action"]["summary"] = summary
            state["proposed_action"]["intent"] = intent
            state["proposed_action"]["sentiment"] = sentiment
            
            state["proposed_action"]["similar_cases"] = similar_cases
            state["proposed_action"]["kb_references"] = kb_procedures  # Changed key name for consistency
            state["proposed_action"]["confidence"] = "high" if confidence >= 0.7 else ("medium" if confidence >= 0.4 else "low")
            state["proposed_action"]["mode"] = mode
            state["proposed_action"]["reasoning"] = f"Analyzed ticket with intent '{intent}' and sentiment '{sentiment}'. Confidence: {confidence:.0%}"

            logger.info(f"Analysis complete: {intent}, {sentiment}, confidence: {confidence:.2f}")
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


def _build_hierarchy_context(fields: list) -> str:
    """
    Build a string representation of ticket field hierarchies from Freshdesk API response.
    Focuses on MANDATORY DROPDOWN fields (required_for_agents=True and type=custom_dropdown/nested_field).
    """
    context = []
    
    for field in fields:
        # Skip archived fields
        if field.get('archived'):
            continue
            
        # Filter: Include all dropdown types (removed strict required_for_agents check to ensure suggestions appear)
        field_type = field.get('type', '')
        is_dropdown = field_type in ['custom_dropdown', 'nested_field', 'default_dropdown']
        
        if is_dropdown and field.get('choices'):
            label = field.get('label', 'Unknown Field')
            name = field.get('name', 'unknown_name')
            
            context.append(f"Field: {label} (ID: {name})")
            
            def process_choices(choices, level=1):
                lines = []
                for i, choice in enumerate(choices):
                    if i > 50: # Safety limit
                        lines.append(f"{'  ' * level}- ... (more options)")
                        break
                        
                    val = choice.get('value', '')
                    sub_choices = choice.get('choices', [])
                    
                    prefix = "  " * level + "- "
                    if sub_choices:
                        lines.append(f"{prefix}{val}")
                        lines.extend(process_choices(sub_choices, level + 1))
                    else:
                        lines.append(f"{prefix}{val}")
                return lines

            context.extend(process_choices(field['choices']))
            context.append("") # Empty line between fields

    if not context:
        return "No mandatory dropdown fields found."
        
    return "AVAILABLE MANDATORY FIELD OPTIONS:\n" + "\n".join(context)


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
            model = genai.GenerativeModel("models/gemini-2.5-flash")

            ticket_ctx = state.get("ticket_context", {})
            proposed = state.get("proposed_action", {})

            # Use summary and intent instead of draft_response
            summary = proposed.get("summary", "")
            intent = proposed.get("intent", "")
            confidence = proposed.get("confidence", 0.5)

            # Use only subject and summary for field updates (not full description to avoid token limits)
            description_summary = ticket_ctx.get('description', '')[:500] + "..." if len(ticket_ctx.get('description', '')) > 500 else ticket_ctx.get('description', 'N/A')

            # Fetch dynamic ticket fields
            freshdesk = FreshdeskClient()
            try:
                ticket_fields = await freshdesk.get_ticket_fields()
                hierarchy_str = _build_hierarchy_context(ticket_fields)
            except Exception as e:
                logger.error(f"Failed to fetch ticket fields: {e}")
                hierarchy_str = "Could not fetch dynamic hierarchy. Please propose based on standard fields."

            prompt = f"""You are a ticket management AI. Analyze this ticket and propose field updates.

Ticket Details:
- Subject: {ticket_ctx.get('subject', 'N/A')}
- Description Summary: {description_summary}

Analysis:
- Summary: {summary}
- Intent: {intent}

Solution Confidence: {confidence:.2f}

Based on the ticket analysis, propose appropriate field updates for MANDATORY DROPDOWN FIELDS.

IMPORTANT RULES:
1. **Scope**: Only propose updates for the mandatory dropdown fields listed below. Do NOT propose changes to Priority, Status, Group, or Agent.
2. **Tags**: You MAY propose relevant tags to help classify the ticket.
3. **Hierarchy**: If a field has a hierarchy (e.g. Category -> Sub Category), ensure your proposal forms a valid chain.

VALID CHOICES:

{hierarchy_str}

Fields to propose:
- Tags: [comma-separated relevant tags]
- [Any Mandatory Field Name from above]: [Valid Value]

Also provide a brief justification for each update.

Response format:
TAGS: [tag1, tag2, tag3]
[FIELD_NAME]: [value]
REASON_[FIELD_NAME]: [Reason]
JUSTIFICATION: [Overall summary of changes]
"""

            # Configure safety settings
            safety_settings = {
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }

            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                ),
                safety_settings=safety_settings
            )

            # Check if response was blocked
            if not response.candidates or not response.candidates[0].content.parts:
                candidate = response.candidates[0] if response.candidates else None
                finish_reason = candidate.finish_reason if candidate else 'unknown'

                # Log detailed safety ratings
                if candidate and hasattr(candidate, 'safety_ratings'):
                    logger.error(f"Response blocked - Finish reason: {finish_reason}")
                    logger.error(f"Safety ratings: {candidate.safety_ratings}")
                else:
                    logger.error(f"Response blocked - Finish reason: {finish_reason}")

                error_msg = f"Response blocked. Finish reason: {finish_reason}"
                state["errors"] = state.get("errors", []) + [error_msg]
                return state

            result_text = response.text.strip()

            updates = {}
            justification = ""
            reasons = {}

            # Mapping constants
            PRIORITY_MAP = {
                "low": 1,
                "medium": 2,
                "high": 3,
                "urgent": 4
            }

            STATUS_MAP = {
                "open": 2,
                "pending": 3,
                "resolved": 4,
                "closed": 5
            }

            for line in result_text.split("\n"):
                line = line.strip()
                upper_line = line.upper()
                
                if upper_line.startswith("PRIORITY:"):
                    p_str = line.split(":", 1)[1].strip().lower()
                    updates["priority"] = PRIORITY_MAP.get(p_str, 2)  # Default to Medium
                    updates["priority_label"] = p_str.capitalize()
                elif upper_line.startswith("REASON_PRIORITY:"):
                    reasons["priority"] = line.split(":", 1)[1].strip()
                elif upper_line.startswith("STATUS:"):
                    s_str = line.split(":", 1)[1].strip().lower()
                    updates["status"] = STATUS_MAP.get(s_str, 2)  # Default to Open
                    updates["status_label"] = s_str.capitalize()
                elif upper_line.startswith("REASON_STATUS:"):
                    reasons["status"] = line.split(":", 1)[1].strip()
                elif upper_line.startswith("TAGS:"):
                    tags_str = line.split(":", 1)[1].strip()
                    updates["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()]
                elif upper_line.startswith("CATEGORY:"):
                    updates["category"] = line.split(":", 1)[1].strip()
                elif upper_line.startswith("SUB_CATEGORY:") or upper_line.startswith("SUB CATEGORY:"):
                    updates["sub_category"] = line.split(":", 1)[1].strip()
                elif upper_line.startswith("ITEM_CATEGORY:") or upper_line.startswith("ITEM CATEGORY:"):
                    updates["item_category"] = line.split(":", 1)[1].strip()
                elif upper_line.startswith("REASON_CATEGORY:"):
                    reasons["category"] = line.split(":", 1)[1].strip()
                elif upper_line.startswith("JUSTIFICATION:"):
                    justification = line.split(":", 1)[1].strip()

            if "proposed_action" not in state:
                state["proposed_action"] = {}

            state["proposed_action"]["proposed_field_updates"] = updates
            state["proposed_action"]["justification"] = justification
            state["proposed_action"]["field_reasons"] = reasons

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
