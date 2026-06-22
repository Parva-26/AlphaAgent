"""LangGraph workflow for multi-agent investment debate."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents.arbiter_agent import generate_verdict
from agents.bear_agent import generate_bear_thesis
from agents.bull_agent import generate_bull_thesis
from agents.research_agent import run_research_agent
from tools import ALL_TOOLS


class DebateState(TypedDict):
    """State passed through the debate workflow."""

    ticker: str
    research_note: str
    bull_thesis: str
    bear_thesis: str
    verdict: str
    error: str


def _research_node(state: DebateState) -> DebateState:
    try:
        research_note = run_research_agent(state["ticker"], ALL_TOOLS)
        return {**state, "research_note": research_note, "error": ""}
    except Exception as exc:
        return {**state, "error": f"Research step failed: {exc}"}


def _bull_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    bull_thesis = generate_bull_thesis(state["research_note"], state["ticker"])
    return {**state, "bull_thesis": bull_thesis}


def _bear_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    bear_thesis = generate_bear_thesis(state["research_note"], state["ticker"])
    return {**state, "bear_thesis": bear_thesis}


def _arbiter_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    verdict = generate_verdict(state["bull_thesis"], state["bear_thesis"], state["ticker"])
    return {**state, "verdict": verdict}


def build_debate_graph():
    """Compile the LangGraph debate workflow."""

    workflow = StateGraph(DebateState)
    workflow.add_node("research", _research_node)
    workflow.add_node("bull_agent", _bull_node)
    workflow.add_node("bear_agent", _bear_node)
    workflow.add_node("arbiter_agent", _arbiter_node)

    workflow.set_entry_point("research")
    workflow.add_edge("research", "bull_agent")
    workflow.add_edge("bull_agent", "bear_agent")
    workflow.add_edge("bear_agent", "arbiter_agent")
    workflow.add_edge("arbiter_agent", END)
    return workflow.compile()


def run_debate_workflow(ticker: str) -> DebateState:
    """Run the multi-agent debate for a ticker."""

    graph = build_debate_graph()
    return graph.invoke(
        {
            "ticker": ticker.upper(),
            "research_note": "",
            "bull_thesis": "",
            "bear_thesis": "",
            "verdict": "",
            "error": "",
        }
    )
