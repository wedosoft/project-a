"""
Orchestrator Agent - LangGraph Workflow Controller
"""
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.retriever import RetrieverAgent
from agents.resolution import ResolutionAgent


class OrchestratorAgent:
    """
    Orchestrator Agent - Controls overall workflow

    Responsibilities:
    - Route ticket context to appropriate agents
    - Manage execution order (sequential/parallel)
    - Handle errors and retries
    - Coordinate approval loop
    """

    def __init__(self):
        self.retriever = RetrieverAgent()
        self.resolution = ResolutionAgent()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow

        Flow:
        1. context_router → determine route
        2. retriever → find similar cases + KB
        3. resolution → synthesize draft response
        4. (human approval handled externally)
        """
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("route_context", self.route_context)
        workflow.add_node("retrieve", self.retriever.retrieve)
        workflow.add_node("resolve", self.resolution.generate_proposal)

        # Define edges
        workflow.set_entry_point("route_context")
        workflow.add_edge("route_context", "retrieve")
        workflow.add_edge("retrieve", "resolve")
        workflow.add_edge("resolve", END)

        return workflow.compile()

    def route_context(self, state: AgentState) -> AgentState:
        """
        Route ticket context to appropriate workflow

        Routes:
        - Ticket context → retriever
        - KB search → retriever (KB mode)
        - General chat → resolution (direct)
        """
        state["current_step"] = "routing"
        # Default: route to retriever
        return state

    async def process(self, ticket_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process ticket through LangGraph workflow

        Args:
            ticket_context: {ticket_id, ticket_content, ticket_meta}

        Returns:
            AI proposal with draft_response, field_updates, similar_cases, KB
        """
        initial_state: AgentState = {
            "ticket_id": ticket_context["ticket_id"],
            "ticket_content": ticket_context["ticket_content"],
            "ticket_meta": ticket_context["ticket_meta"],
            "similar_cases": None,
            "kb_procedures": None,
            "draft_response": None,
            "field_updates": None,
            "justification": None,
            "approval_status": None,
            "final_response": None,
            "final_field_updates": None,
            "current_step": "init",
            "error": None,
        }

        # Execute graph
        final_state = await self.graph.ainvoke(initial_state)

        return {
            "draft_response": final_state.get("draft_response"),
            "field_updates": final_state.get("field_updates"),
            "similar_cases": final_state.get("similar_cases", []),
            "kb_procedures": final_state.get("kb_procedures", []),
            "justification": final_state.get("justification"),
        }
