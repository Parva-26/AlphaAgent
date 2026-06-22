"""Bear thesis agent."""

from __future__ import annotations

from utils.llm import build_groq, invoke_with_tracking


def generate_bear_thesis(research_context: str, ticker: str) -> str:
    """Generate a bear investment thesis using Groq."""

    llm = build_groq(temperature=0.2, max_tokens=512)
    prompt = f"""Based on this research about {ticker.upper()}:

{research_context}

Construct the strongest possible BEAR case against investing. Focus on:
- Deteriorating fundamentals and quality of earnings risks
- Competitive threats and business model pressure
- Overvaluation or stretched expectations
- Negative technical, analyst, or news signals

Output a structured bear thesis with 3-4 key arguments, each backed by specific data from the research above.

Format:
[Bear Case Summary]
[Key Arguments (with data)]
[Downside Scenario]
[Target Price Rationale]
"""

    try:
        return invoke_with_tracking(llm, prompt, label="Bear thesis agent")
    except Exception as exc:
        return f"Unable to generate bear thesis: {exc}"
