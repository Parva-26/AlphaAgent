"""Token and cost tracking for Groq usage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .config import COST_CONFIG


@dataclass
class UsageEvent:
    """Single LLM usage record."""

    timestamp_utc: datetime
    input_tokens: int
    output_tokens: int
    cost_usd: float
    label: str


class CostTracker:
    """Tracks Groq API usage and estimated costs."""

    INPUT_PRICE_PER_MTOK = COST_CONFIG.input_price_per_mtok
    OUTPUT_PRICE_PER_MTOK = COST_CONFIG.output_price_per_mtok
    MAX_BUDGET_USD = COST_CONFIG.max_budget_usd

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.requests_made = 0
        self.usage_events: list[UsageEvent] = []
        self.current_day = date.today()

    def reset_if_new_day(self) -> None:
        """Reset process-local counters at midnight UTC."""

        utc_today = datetime.utcnow().date()
        if utc_today != self.current_day:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.total_cost_usd = 0.0
            self.requests_made = 0
            self.usage_events = []
            self.current_day = utc_today

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate Groq cost for a token pair."""

        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_MTOK
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_MTOK
        return input_cost + output_cost

    def add_usage(self, input_tokens: int, output_tokens: int, label: str = "Groq call") -> float:
        """Log token usage from an API call and return the estimated cost."""

        self.reset_if_new_day()
        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)
        cost = self.estimate_cost(input_tokens, output_tokens)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.requests_made += 1
        self.usage_events.append(
            UsageEvent(
                timestamp_utc=datetime.utcnow(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                label=label,
            )
        )
        return cost

    def can_afford_request(self, estimated_cost_usd: float = 0.0) -> bool:
        """Check whether a request can be attempted within the hard budget."""

        self.reset_if_new_day()
        return (self.total_cost_usd + estimated_cost_usd) < self.MAX_BUDGET_USD

    def get_status(self) -> dict[str, object]:
        """Return current tracking status."""

        self.reset_if_new_day()
        remaining = max(0.0, self.MAX_BUDGET_USD - self.total_cost_usd)
        return {
            "total_cost": f"${self.total_cost_usd:.4f}",
            "remaining_budget": f"${remaining:.4f}",
            "raw_total_cost": self.total_cost_usd,
            "raw_remaining_budget": remaining,
            "total_requests": self.requests_made,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "budget_exceeded": not self.can_afford_request(),
            "usage_events": list(self.usage_events[-10:]),
        }


cost_tracker = CostTracker()
