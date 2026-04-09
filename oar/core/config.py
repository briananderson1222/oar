"""Pydantic configuration models for OAR."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class BudgetConfigModel(BaseModel):
    """Budget settings for LLM spending."""

    max_per_call: float = 0.50
    max_per_session: float = 5.00
    max_per_day: float = 20.00


class LlmConfig(BaseModel):
    """LLM provider settings."""

    default_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "ollama/llama3.1"
    max_cost_per_call: float = 0.50
    budget: BudgetConfigModel = BudgetConfigModel()
    provider: str = (
        "auto"  # "auto" | "claude-cli" | "opencode-cli" | "codex-cli" | "litellm"
    )
    fallback_chain: list[str] = []  # empty = auto-detect order
    cli_timeout: int = 120
    offline: bool = False  # Force offline mode


class CompileConfig(BaseModel):
    """Compilation pipeline settings."""

    default_type: str = "concept"
    auto_index: bool = True


class OarConfig(BaseModel):
    """Top-level OAR configuration."""

    vault_path: str = ""
    llm: LlmConfig = LlmConfig()
    compile: CompileConfig = CompileConfig()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Serialise to YAML and write to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            yaml.dump(self.model_dump(), fh, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, path: Path) -> OarConfig:
        """Load from YAML file.

        Returns a default ``OarConfig`` when the file does not exist.
        """
        if not path.exists():
            return cls()
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)
