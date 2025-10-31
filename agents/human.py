"""
Human Agent - Approval Interface
"""
from typing import Dict, Any
from agents.state import AgentState


class HumanAgent:
    """
    Human Agent - Manages approval loop

    Responsibilities:
    - Render FDK app UI (ticket sidebar)
    - Collect agent feedback (approve/modify/reject)
    - Execute Freshdesk API updates
    - Log approval/rejection to Supabase

    Note: This agent is called from backend API routes,
    not directly from LangGraph workflow
    """

    def __init__(self):
        # TODO: Initialize Freshdesk client, Supabase client
        pass

    async def wait_for_approval(
        self,
        draft_response: str,
        field_updates: Dict[str, Any],
        similar_cases: list,
        kb_procedures: list
    ) -> Dict[str, Any]:
        """
        Display proposal and wait for agent decision

        This is called from backend/routes/assist.py
        after Orchestrator completes

        Returns:
            {
                "approval_status": "approved" | "modified" | "rejected",
                "final_response": str,
                "final_field_updates": dict,
                "feedback_notes": str
            }
        """
        # This method is implemented in FDK app UI + backend API
        # Not part of LangGraph workflow
        raise NotImplementedError(
            "Approval loop handled by FDK app + backend/routes/assist.py"
        )

    async def execute_updates(
        self,
        ticket_id: str,
        final_response: str,
        final_field_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute approved changes via Freshdesk API

        Actions:
        1. PATCH ticket fields
        2. POST note/reply
        3. Log to Supabase

        Returns:
            Execution result
        """
        # TODO: Freshdesk API calls
        return {
            "success": True,
            "ticket_updated": True,
            "note_added": True,
        }

    async def log_feedback(
        self,
        ticket_id: str,
        approval_status: str,
        draft_response: str,
        final_response: str,
        field_updates: Dict[str, Any],
        agent_id: str
    ) -> None:
        """
        Log approval decision to Supabase

        Schema: approval_logs table
        """
        # TODO: Supabase insert
        pass
