"""LiteLLM provider — wraps litellm.completion() as an LLM backend."""

from __future__ import annotations

import os
from typing import Any

from oar.llm.providers.base import LLMResponse


class LitellmProvider:
    """Use litellm.completion() as an LLM backend.

    This is the existing behavior, now behind the provider interface.
    Requires ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable.
    """

    @property
    def name(self) -> str:
        return "litellm"

    @property
    def available(self) -> bool:
        """True when at least one API key is configured."""
        return bool(
            os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )

    def health_check(self) -> bool:
        """Simple availability check — at least one key is set."""
        return self.available

    def complete(
        self,
        messages: list[dict],
        *,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send completion request via litellm."""
        import litellm
        from oar.llm.cost_tracker import estimate_cost

        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        content = response.choices[0].message.content
        cost = estimate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate."""
        return len(text) // 4
