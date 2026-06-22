"""Single-stock deep research ReAct agent."""

from __future__ import annotations

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

from utils.llm import CostTrackingCallbackHandler, build_groq


RESEARCH_REACT_TEMPLATE = """You are an elite Wall Street research analyst.

When given a stock ticker, conduct a comprehensive investment research analysis.
Be precise, data-driven, and institutionally rigorous. Use the available tools
to ground the note in current market data, financials, valuation, news, and
analyst context.

Tools available:
{tools}

Use this exact reasoning format:

Question: the stock research task
Thought: decide what information is needed next
Action: one of [{tool_names}]
Action Input: the input for the action
Observation: the result of the action
... repeat Thought/Action/Action Input/Observation as needed
Thought: I now know the final answer
Final Answer: a professional research note

Final Answer format:
Company Overview
Financial Health
Valuation
Technical Picture
Recent Developments
Key Risks
Investment Summary

Question: {input}
Thought:{agent_scratchpad}"""


def build_research_agent(tools):
    """Build a ReAct agent for stock research."""

    callbacks = [CostTrackingCallbackHandler(label="Research agent")]
    llm = build_groq(temperature=0.3, max_tokens=1024, callbacks=callbacks)
    prompt = PromptTemplate.from_template(RESEARCH_REACT_TEMPLATE)

    agent = create_react_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=8,
        handle_parsing_errors=True,
        return_intermediate_steps=False,
    )


def run_research_agent(ticker: str, tools) -> str:
    """Run the research agent and return the final research note."""

    executor = build_research_agent(tools)
    result = executor.invoke(
        {
            "input": (
                f"Conduct comprehensive investment research on {ticker.upper()}. "
                "Use market data, financial statements, historical technicals, "
                "news, valuation metrics, sector context, and analyst information."
            )
        }
    )
    return str(result.get("output", "No research output returned."))
