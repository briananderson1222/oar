"""Offline manager — detect offline mode, manage Ollama fallback."""

from __future__ import annotations

import os

from oar.core.config import OarConfig


class OfflineManager:
    """Manage offline mode detection and Ollama fallback."""

    def __init__(self, config: OarConfig | None = None) -> None:
        self._config = config
        self._offline_override: bool | None = None

    def set_offline(self, offline: bool) -> None:
        """Force offline mode on or off (from --offline CLI flag)."""
        self._offline_override = offline

    def is_offline(self) -> bool:
        """Check if we should operate in offline mode.

        Offline when:
        1. Explicitly forced via --offline flag
        2. Config has offline=true
        3. OAR_OFFLINE env var is set
        """
        if self._offline_override is not None:
            return self._offline_override
        if os.environ.get("OAR_OFFLINE", "").lower() in ("1", "true", "yes"):
            return True
        if self._config and getattr(self._config.llm, "offline", False):
            return True
        return False

    def check_ollama_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            from oar.llm.providers.ollama_provider import OllamaProvider

            provider = OllamaProvider()
            return provider.health_check()
        except Exception:
            return False

    def list_local_models(self) -> list[str]:
        """List available local (Ollama) models."""
        try:
            from oar.llm.providers.ollama_provider import OllamaProvider

            provider = OllamaProvider()
            return provider.list_models()
        except Exception:
            return []

    def get_fallback_model(self, task: str = "compile") -> str:
        """Return a local model suitable for the given task."""
        models = self.list_local_models()
        if not models:
            return "ollama/llama3.1"  # Sensible default

        # Prefer models with more parameters for complex tasks.
        preferred = ["llama3.1", "llama3", "mistral", "phi3", "gemma"]
        for pref in preferred:
            for m in models:
                if pref in m.lower():
                    return f"ollama/{m}"
        return f"ollama/{models[0]}"

    def get_offline_fallback_chain(self) -> list[str]:
        """Return a provider chain for offline mode (ollama only)."""
        if self.check_ollama_available():
            return ["ollama"]
        return []  # No providers available offline

    def should_disable_feature(self, feature: str) -> bool:
        """Check if a feature should be disabled in offline mode.

        Features that require internet:
        - web_search
        - url_ingest
        - web_augment

        Features that work offline:
        - compile (with local model)
        - search (local SQLite FTS)
        - lint (structural checks)
        - query (with local model)
        """
        offline_features = {"web_search", "url_ingest", "web_augment"}
        if self.is_offline() and feature in offline_features:
            return True
        return False
