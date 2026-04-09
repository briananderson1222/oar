"""Provider registry — auto-detect available LLM providers."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oar.llm.providers.cli_base import CliProvider
    from oar.llm.providers.litellm_provider import LitellmProvider

# Provider name → (module path, class name)
PROVIDER_CLASSES: dict[str, tuple[str, str]] = {
    "claude-cli": ("oar.llm.providers.claude_cli", "ClaudeCliProvider"),
    "opencode-cli": ("oar.llm.providers.opencode_cli", "OpenCodeCliProvider"),
    "codex-cli": ("oar.llm.providers.codex_cli", "CodexCliProvider"),
    "ollama": ("oar.llm.providers.ollama_provider", "OllamaProvider"),
    "litellm": ("oar.llm.providers.litellm_provider", "LitellmProvider"),
}


class ProviderRegistry:
    """Discover, instantiate, and cache LLM providers."""

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout
        self._cache: dict[str, CliProvider | LitellmProvider] = {}

    def _load_provider(self, name: str):
        """Lazily import and instantiate a provider by name."""
        if name in self._cache:
            return self._cache[name]

        if name not in PROVIDER_CLASSES:
            raise ValueError(f"Unknown provider: {name}")

        module_path, class_name = PROVIDER_CLASSES[name]
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        # Instantiate with appropriate kwargs.
        # OllamaProvider takes (base_url, timeout); CLI providers take (timeout);
        # litellm takes no args.
        if name == "ollama":
            provider = cls(timeout=self.timeout)
        elif (
            hasattr(cls, "__init__") and "timeout" in cls.__init__.__code__.co_varnames
        ):
            provider = cls(timeout=self.timeout)
        else:
            provider = cls()

        self._cache[name] = provider
        return provider

    def detect_available(self, names: list[str] | None = None) -> list[str]:
        """Return list of provider names that are available.

        If *names* is None, check all known providers.
        """
        check = names or list(PROVIDER_CLASSES.keys())
        available: list[str] = []
        for name in check:
            try:
                provider = self._load_provider(name)
                if provider.available:
                    available.append(name)
            except Exception:
                continue
        return available

    def get(self, name: str):
        """Return a provider instance by name (cached)."""
        return self._load_provider(name)

    def get_healthy(self, name: str):
        """Return a provider only if it passes a health check."""
        try:
            provider = self._load_provider(name)
            if provider.health_check():
                return provider
        except Exception:
            pass
        return None
