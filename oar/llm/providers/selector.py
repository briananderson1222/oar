"""Provider selector — choose an LLM provider with fallback logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oar.llm.providers.base import ProviderUnavailableError

if TYPE_CHECKING:
    from oar.llm.providers.registry import ProviderRegistry


# Default fallback order: best CLI tools first, then litellm.
DEFAULT_CHAIN: list[str] = [
    "claude-cli",
    "opencode-cli",
    "codex-cli",
    "ollama",
    "litellm",
]


class ProviderSelector:
    """Select a healthy LLM provider from a fallback chain."""

    def __init__(
        self,
        fallback_chain: list[str] | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        from oar.llm.providers.registry import ProviderRegistry

        self.fallback_chain = fallback_chain or list(DEFAULT_CHAIN)
        self.registry = registry or ProviderRegistry()

    def select(self):
        """Return the first healthy provider, or raise."""
        for name in self.fallback_chain:
            provider = self.registry.get_healthy(name)
            if provider is not None:
                return provider
        raise ProviderUnavailableError(
            "selector",
            f"No healthy provider in chain: {self.fallback_chain}",
        )

    def select_with_fallback(self, preferred: str | None = None) -> list:
        """Return an ordered list of healthy providers to try.

        If *preferred* is given, it is placed first (if healthy).
        """
        providers: list = []
        seen: set[str] = set()

        # Try preferred first.
        if preferred:
            provider = self.registry.get_healthy(preferred)
            if provider is not None:
                providers.append(provider)
                seen.add(preferred)

        # Then try the fallback chain.
        for name in self.fallback_chain:
            if name in seen:
                continue
            provider = self.registry.get_healthy(name)
            if provider is not None:
                providers.append(provider)
                seen.add(name)

        return providers
