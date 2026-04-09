"""Budget management — enforce spending limits on LLM calls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BudgetConfig:
    """Spending limits for LLM API calls."""

    max_per_call: float = 0.50
    max_per_session: float = 5.00
    max_per_day: float = 20.00


class BudgetManager:
    """Manage LLM spending budgets."""

    def __init__(self, config: BudgetConfig, cost_tracker) -> None:
        self.config = config
        self.cost_tracker = cost_tracker

    def can_proceed(self, estimated_cost: float = 0.0) -> tuple[bool, str]:
        """Check if a request can proceed within budget.

        Returns (can_proceed, reason) tuple.
        """
        session_cost = self.cost_tracker.get_session_cost()

        if session_cost + estimated_cost > self.config.max_per_session:
            return (
                False,
                f"Session budget exceeded: ${session_cost:.2f}/${self.config.max_per_session:.2f}",
            )

        if estimated_cost > self.config.max_per_call:
            return (
                False,
                f"Single call exceeds max: ${estimated_cost:.2f}/${self.config.max_per_call:.2f}",
            )

        return True, "OK"

    def get_status(self) -> dict:
        """Return budget status summary."""
        session_cost = self.cost_tracker.get_session_cost()
        return {
            "session_cost": session_cost,
            "session_budget": self.config.max_per_session,
            "session_remaining": self.config.max_per_session - session_cost,
            "session_utilization": session_cost / self.config.max_per_session
            if self.config.max_per_session > 0
            else 0,
        }
