"""Formatting helpers for AlphaAgent UI and agent output."""

from __future__ import annotations

import math
from typing import Any


def compact_number(value: Any) -> str:
    """Format large numeric values for finance UI."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"

    if math.isnan(number):
        return "N/A"

    sign = "-" if number < 0 else ""
    number = abs(number)
    for suffix, divisor in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if number >= divisor:
            return f"{sign}{number / divisor:.2f}{suffix}"
    return f"{sign}{number:.2f}"


def currency(value: Any) -> str:
    """Format a numeric value as dollars."""

    formatted = compact_number(value)
    return "N/A" if formatted == "N/A" else f"${formatted}"


def percent(value: Any) -> str:
    """Format a ratio or percentage-like value."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if math.isnan(number):
        return "N/A"
    if abs(number) <= 1:
        number *= 100
    return f"{number:.2f}%"


def safe_round(value: Any, digits: int = 2) -> float | str:
    """Round numbers while preserving missing values as N/A."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if math.isnan(number):
        return "N/A"
    return round(number, digits)


def normalize_ticker(ticker: str) -> str:
    """Normalize a user-provided ticker symbol."""

    return ticker.strip().upper().replace("$", "")


def render_markdown_sections(text: str) -> str:
    """Make bracketed agent headings display nicely in Markdown."""

    replacements = {
        "[Bull Case Summary]": "### Bull Case Summary",
        "[Key Arguments (with data)]": "### Key Arguments",
        "[Upside Scenario]": "### Upside Scenario",
        "[Target Price Rationale]": "### Target Price Rationale",
        "[Bear Case Summary]": "### Bear Case Summary",
        "[Downside Scenario]": "### Downside Scenario",
        "[Weighing the Arguments]": "### Weighing the Arguments",
        "[Conviction Level: X/10]": "### Conviction Level",
        "[Final Verdict: BUY / HOLD / SELL]": "### Final Verdict",
        "[Recommended Position Sizing]": "### Recommended Position Sizing",
        "[Key Catalysts to Watch]": "### Key Catalysts to Watch",
    }
    formatted = text
    for source, target in replacements.items():
        formatted = formatted.replace(source, target)
    return formatted
