"""Bull thesis agent."""

from __future__ import annotations

from utils.llm import build_groq, invoke_with_tracking


def generate_bull_thesis(research_context: str, ticker: str) -> str:
    """Generate a bull investment thesis using Groq."""

    llm = build_groq(temperature=0.2, max_tokens=512)
    prompt = f"""Based on this research about {ticker.upper()}:

{research_context}

Construct the strongest possible BULL case for investing. Focus on:
- Growth catalysts and tailwinds
- Competitive moats
- Undervalued metrics
- Positive momentum

Output a structured bull thesis with 3-4 key arguments, each backed by specific data from the research above.

Format:
[Bull Case Summary]
[Key Arguments (with data)]
[Upside Scenario]
[Target Price Rationale]
"""

    try:
        return invoke_with_tracking(llm, prompt, label="Bull thesis agent")
    except Exception as exc:
        return f"Unable to generate bull thesis: {exc}"
