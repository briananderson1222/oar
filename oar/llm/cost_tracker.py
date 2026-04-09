"""Cost tracking — record LLM API usage and estimate costs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# Pricing per million tokens (USD).
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.25, 1.25),
    "claude-3-haiku-20240307": (0.25, 1.25),
}
DEFAULT_PRICING: tuple[float, float] = (3.0, 15.0)  # Sonnet pricing


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD based on model pricing per million tokens."""
    # Normalise model name for lookup.
    key = model
    # Handle litellm-style prefixes like "anthropic/"
    if "/" in key:
        key = key.split("/", 1)[1]
    input_per_m, output_per_m = MODEL_PRICING.get(key, DEFAULT_PRICING)
    cost = (input_tokens * input_per_m / 1_000_000) + (
        output_tokens * output_per_m / 1_000_000
    )
    return round(cost, 8)


class CostTracker:
    """Track LLM API costs per session and cumulatively."""

    def __init__(self, state_dir: Path) -> None:
        self.history_path = state_dir / "cost-history.jsonl"
        self._session_cost: float = 0.0
        self._session_calls: list[dict] = []

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        task: str = "",
    ) -> None:
        """Record a single LLM call.  Append to JSONL file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "task": task,
        }
        self._session_cost += cost_usd
        self._session_calls.append(entry)

        # Append to JSONL file.
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def get_session_cost(self) -> float:
        """Total USD spent this session."""
        return round(self._session_cost, 8)

    def get_total_cost(self) -> float:
        """Total USD spent all time (from JSONL file)."""
        if not self.history_path.exists():
            return 0.0
        total = 0.0
        with open(self.history_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    total += entry.get("cost_usd", 0.0)
                except json.JSONDecodeError:
                    continue
        return round(total, 8)

    def get_call_history(self, limit: int = 100) -> list[dict]:
        """Recent call history from JSONL file (most recent last)."""
        if not self.history_path.exists():
            return []
        entries: list[dict] = []
        with open(self.history_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries[-limit:]

    def check_budget(self, max_cost: float) -> bool:
        """Returns True if session cost is UNDER *max_cost* (can proceed)."""
        return self._session_cost < max_cost
