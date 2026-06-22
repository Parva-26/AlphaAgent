"""LangGraph workflow for single-stock deep research."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents.research_agent import run_research_agent
from tools import ALL_TOOLS


class ResearchState(TypedDict):
    """State passed through the research workflow."""

    ticker: str
    research_note: str
    error: str


def _research_node(state: ResearchState) -> ResearchState:
    try:
        research_note = run_research_agent(state["ticker"], ALL_TOOLS)
        return {**state, "research_note": research_note, "error": ""}
    except Exception as exc:
        return {**state, "research_note": "", "error": str(exc)}


def build_research_graph():
    """Compile the LangGraph research workflow."""

    workflow = StateGraph(ResearchState)
    workflow.add_node("deep_research", _research_node)
    workflow.set_entry_point("deep_research")
    workflow.add_edge("deep_research", END)
    return workflow.compile()


def run_research_workflow(ticker: str) -> ResearchState:
    """Run deep research for a ticker."""

    graph = build_research_graph()
    return graph.invoke({"ticker": ticker.upper(), "research_note": "", "error": ""})

