"""In-memory request limiter for AlphaAgent.

The limiter is intentionally simple for a portfolio demo: it tracks request
timestamps by Streamlit session id and a process-wide daily request count.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from .config import RATE_LIMIT_CONFIG


class RateLimiter:
    """Prevents cost creep and API abuse."""

    def __init__(
        self,
        max_requests_per_hour: int = RATE_LIMIT_CONFIG.max_requests_per_hour,
        max_requests_per_day: int = RATE_LIMIT_CONFIG.max_requests_per_day,
    ):
        self.max_requests_per_hour = max_requests_per_hour
        self.max_requests_per_day = max_requests_per_day
        self.request_times: dict[str, list[datetime]] = defaultdict(list)
        self.daily_count: dict[str, int] = defaultdict(int)

    def _prune_old_session_requests(self, session_id: str, now: datetime) -> list[datetime]:
        one_hour_ago = now - timedelta(hours=1)
        recent_requests = [t for t in self.request_times[session_id] if t > one_hour_ago]
        self.request_times[session_id] = recent_requests
        return recent_requests

    def is_allowed(self, session_id: str) -> tuple[bool, str]:
        """
        Check if request is allowed.

        Returns:
            (is_allowed, message)
        """

        now = datetime.utcnow()
        today = str(now.date())

        if self.daily_count[today] >= self.max_requests_per_day:
            return (
                False,
                f"Daily limit reached ({self.max_requests_per_day} requests). Try again tomorrow.",
            )

        recent_requests = self._prune_old_session_requests(session_id, now)
        if len(recent_requests) >= self.max_requests_per_hour:
            wait_seconds = (recent_requests[0] + timedelta(hours=1) - now).total_seconds()
            minutes_left = max(1, int(wait_seconds // 60) + (1 if wait_seconds % 60 else 0))
            return (
                False,
                f"Hourly limit reached ({self.max_requests_per_hour} requests). Wait {minutes_left} minutes.",
            )

        return True, "OK"

    def log_request(self, session_id: str) -> None:
        """Log that a request was made."""

        now = datetime.utcnow()
        self.request_times[session_id].append(now)
        self.daily_count[str(now.date())] += 1

    def get_session_status(self, session_id: str) -> dict[str, int]:
        """Return remaining request capacity for the current session."""

        now = datetime.utcnow()
        today = str(now.date())
        recent_requests = self._prune_old_session_requests(session_id, now)
        return {
            "hourly_used": len(recent_requests),
            "hourly_remaining": max(0, self.max_requests_per_hour - len(recent_requests)),
            "daily_used": self.daily_count[today],
            "daily_remaining": max(0, self.max_requests_per_day - self.daily_count[today]),
            "hourly_limit": self.max_requests_per_hour,
            "daily_limit": self.max_requests_per_day,
        }


rate_limiter = RateLimiter()
