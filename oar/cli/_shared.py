"""Shared CLI utilities — vault discovery, component building."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from oar.core.config import OarConfig
from oar.core.vault import Vault
from oar.llm.cost_tracker import CostTracker
from oar.llm.providers.registry import PROVIDER_CLASSES, ProviderRegistry
from oar.llm.providers.selector import DEFAULT_CHAIN, ProviderSelector
from oar.llm.router import LLMRouter

# Valid provider names that can be passed to build_router / query_wiki.
VALID_PROVIDERS = frozenset(PROVIDER_CLASSES.keys())


def find_vault_path() -> Optional[Path]:
    """Resolve vault path — prefer OAR_VAULT env var, else walk up from cwd."""
    env_path = os.environ.get("OAR_VAULT")
    if env_path:
        p = Path(env_path)
        if (p / ".oar" / "state.json").exists():
            return p

    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".oar" / "state.json").exists():
            return parent
    return None


def build_router(
    vault_path: Path,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[LLMRouter, CostTracker, OarConfig]:
    """Build an LLMRouter with CLI provider support.

    Returns (router, cost_tracker, config) so callers can also access config.

    Args:
        vault_path: Path to the OAR vault.
        model: Model name override (e.g. "claude-sonnet-4-20250514").
        provider: Provider to use (e.g. "claude-cli", "codex-cli", "opencode-cli",
                  "ollama", "litellm"). Must be a valid provider name. If not
                  specified, uses config default or auto-detects.

    Raises:
        ValueError: If provider is not a valid provider name.
    """
    if provider is not None and provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider: '{provider}'. "
            f"Valid providers: {sorted(VALID_PROVIDERS)}"
        )

    vault = Vault(vault_path)
    config = OarConfig.load(vault.oar_dir / "config.yaml")
    effective_model = model or config.llm.default_model
    cost_tracker = CostTracker(vault.oar_dir)

    # Check offline mode — force ollama-only chain when offline.
    from oar.llm.offline import OfflineManager

    offline_mgr = OfflineManager(config)
    if offline_mgr.is_offline():
        fallback_chain = offline_mgr.get_offline_fallback_chain()
        if fallback_chain:
            registry = ProviderRegistry(timeout=config.llm.cli_timeout)
            provider_selector = ProviderSelector(
                fallback_chain=fallback_chain, registry=registry
            )
            effective_model = offline_mgr.get_fallback_model()
            return (
                LLMRouter(
                    effective_model, cost_tracker, provider_selector=provider_selector
                ),
                cost_tracker,
                config,
            )

    # Build provider selector from config for CLI tool support.
    provider_selector = None
    try:
        timeout = config.llm.cli_timeout
        registry = ProviderRegistry(timeout=timeout)

        # Determine fallback chain — priority: explicit arg > config > auto-detect.
        if provider:
            # Explicit provider requested — use it exclusively.
            fallback_chain = [provider]
        elif config.llm.fallback_chain:
            # User-specified chain takes priority.
            fallback_chain = config.llm.fallback_chain
        elif config.llm.provider and config.llm.provider != "auto":
            # Specific provider preference — put it first, then defaults.
            default_chain = list(DEFAULT_CHAIN)
            preferred = config.llm.provider
            if preferred in default_chain:
                default_chain.remove(preferred)
            fallback_chain = [preferred] + default_chain
        else:
            fallback_chain = None  # Use ProviderSelector defaults

        provider_selector = ProviderSelector(
            fallback_chain=fallback_chain, registry=registry
        )
    except Exception:
        pass  # Fall back to litellm if provider system has issues

    router = LLMRouter(
        effective_model,
        cost_tracker,
        provider_selector=provider_selector,
    )

    return router, cost_tracker, config
