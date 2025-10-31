"""
LangGraph Workflow Definition
"""
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.orchestrator import OrchestratorAgent


def build_workflow() -> StateGraph:
    """
    Build complete LangGraph workflow

    This is a convenience function for initializing the graph
    """
    orchestrator = OrchestratorAgent()
    return orchestrator.graph


# Export compiled graph
workflow = build_workflow()
