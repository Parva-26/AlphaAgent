"""CIO-style synthesis and verdict agent."""

from __future__ import annotations

from utils.llm import build_groq, invoke_with_tracking


def generate_verdict(bull_thesis: str, bear_thesis: str, ticker: str) -> str:
    """Synthesize bull and bear cases into an investment verdict."""

    llm = build_groq(temperature=0.3, max_tokens=768)
    prompt = f"""You are the CIO of a $10B hedge fund. You have received:

BULL THESIS:
{bull_thesis}

BEAR THESIS:
{bear_thesis}

Weigh both sides objectively. Which arguments are most compelling? What's the risk/reward?

Output format:
[Weighing the Arguments]
[Conviction Level: X/10]
[Final Verdict: BUY / HOLD / SELL]
[Recommended Position Sizing]
[Key Catalysts to Watch]
"""

    try:
        return invoke_with_tracking(llm, prompt, label="Arbiter agent")
    except Exception as exc:
        return f"Unable to generate verdict: {exc}"
