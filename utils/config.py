"""Central configuration for AlphaAgent.

All defaults are intentionally conservative so the app remains suitable for a
free-tier portfolio demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Groq model settings used by every agent."""

    model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    temperature: float = 0.3
    max_tokens: int = 1024


@dataclass(frozen=True)
class RateLimitConfig:
    """Simple request caps that protect free demo usage."""

    max_requests_per_hour: int = 5
    max_requests_per_day: int = 20


@dataclass(frozen=True)
class CostConfig:
    """Groq pricing estimate and hard stop for demo usage."""

    input_price_per_mtok: float = 0.59
    output_price_per_mtok: float = 0.79
    max_budget_usd: float = 4.90
    displayed_free_tier_usd: float = 5.00


LLM_CONFIG = LLMConfig()
RATE_LIMIT_CONFIG = RateLimitConfig()
COST_CONFIG = CostConfig()


def get_groq_api_key() -> str | None:
    """Return the Groq API key from the environment, if configured."""

    return os.getenv("GROQ_API_KEY")
