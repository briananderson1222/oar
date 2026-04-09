"""LLM Router — route completion calls through providers with cost tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oar.llm.cost_tracker import CostTracker, estimate_cost
from oar.llm.model_config import get_model_for_task
from oar.llm.providers.base import LLMProviderError, LLMResponse

if TYPE_CHECKING:
    from oar.llm.budget import BudgetManager
    from oar.llm.providers.selector import ProviderSelector


# Re-export LLMResponse for backward compatibility — this is the canonical
# import path used throughout the codebase.  The actual dataclass lives in
# oar.llm.providers.base but router.py re-exports it so existing imports
# like `from oar.llm.router import LLMResponse` keep working.
__all__ = ["LLMResponse", "BudgetExceededError", "LLMRouter"]


class BudgetExceededError(Exception):
    """Raised when a call would exceed budget limits."""


class LLMRouter:
    """Route LLM calls through providers with cost tracking.

    Supports two modes:
        1. **Provider mode** (new): pass a ``provider`` or ``provider_selector``
           to use CLI-based or other pluggable backends.
        2. **Litellm mode** (legacy): no provider configured → calls litellm
           directly, preserving backward compatibility.
    """

    def __init__(
        self,
        default_model: str,
        cost_tracker: CostTracker,
        budget_manager: BudgetManager | None = None,
        task_model_map: dict[str, str] | None = None,
        provider: object | None = None,
        provider_selector: ProviderSelector | None = None,
    ) -> None:
        self.default_model = default_model
        self.cost_tracker = cost_tracker
        self.budget_manager = budget_manager
        self.task_model_map = task_model_map or {}
        self._provider = provider
        self._provider_selector = provider_selector

    def select_model(self, task: str) -> str:
        """Select the best model for a given task."""
        if task in self.task_model_map:
            return self.task_model_map[task]
        return get_model_for_task(task, self.default_model)

    def get_status(self) -> dict:
        """Return router status including budget and model info."""
        status: dict = {
            "default_model": self.default_model,
            "session_cost": self.cost_tracker.get_session_cost(),
        }
        if self.budget_manager is not None:
            status["budget"] = self.budget_manager.get_status()
        return status

    def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        task: str = "compile",
    ) -> LLMResponse:
        """Send completion request via a provider or litellm fallback."""
        model = model or self.default_model

        # Budget check — if a budget manager is configured, enforce limits.
        if self.budget_manager is not None:
            estimated_cost = estimate_cost(model, max_tokens, max_tokens)
            can_proceed, reason = self.budget_manager.can_proceed(estimated_cost)
            if not can_proceed:
                raise BudgetExceededError(reason)

        # Provider path.
        if self._provider is not None:
            response = self._provider.complete(
                messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            self.cost_tracker.record(
                response.model,
                response.input_tokens,
                response.output_tokens,
                response.cost_usd,
                task,
            )
            return response

        # Selector path — try providers with fallback.
        if self._provider_selector is not None:
            providers = self._provider_selector.select_with_fallback()
            last_error: Exception | None = None
            for prov in providers:
                try:
                    response = prov.complete(
                        messages,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    self.cost_tracker.record(
                        response.model,
                        response.input_tokens,
                        response.output_tokens,
                        response.cost_usd,
                        task,
                    )
                    return response
                except LLMProviderError as exc:
                    last_error = exc
                    if not exc.recoverable:
                        raise
                    continue
            if last_error is not None:
                raise last_error
            raise LLMProviderError("router", "No providers available")

        # Legacy litellm path (backward compatibility).
        import litellm

        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Extract usage stats.
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        content = response.choices[0].message.content
        cost = estimate_cost(model, input_tokens, output_tokens)

        # Track cost.
        self.cost_tracker.record(model, input_tokens, output_tokens, cost, task)

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
