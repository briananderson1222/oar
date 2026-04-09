"""Model configuration — task-to-model routing and model registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskComplexity(Enum):
    SIMPLE = "simple"  # Classification, keyword extraction → cheap model
    MODERATE = "moderate"  # Article updates, linting → mid model
    COMPLEX = "complex"  # New article compile, complex Q&A → strong model


class ModelTier(Enum):
    CHEAP = "cheap"  # Haiku / local small model
    DEFAULT = "default"  # Sonnet / local mid model
    STRONG = "strong"  # Opus / local large model


@dataclass
class ModelDefinition:
    """Describes an LLM model's capabilities and pricing."""

    name: str  # litellm model name
    tier: ModelTier
    max_context: int  # Max context tokens
    cost_per_million_input: float
    cost_per_million_output: float

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given token usage."""
        cost = (input_tokens * self.cost_per_million_input / 1_000_000) + (
            output_tokens * self.cost_per_million_output / 1_000_000
        )
        return round(cost, 8)


# Model registry
MODEL_REGISTRY: dict[str, ModelDefinition] = {
    "claude-sonnet-4-20250514": ModelDefinition(
        "claude-sonnet-4-20250514",
        ModelTier.DEFAULT,
        200000,
        3.0,
        15.0,
    ),
    "claude-haiku-4-20250414": ModelDefinition(
        "claude-haiku-4-20250414",
        ModelTier.CHEAP,
        200000,
        0.25,
        1.25,
    ),
    "ollama/llama3.1": ModelDefinition(
        "ollama/llama3.1",
        ModelTier.DEFAULT,
        128000,
        0.0,
        0.0,
    ),
    "ollama/mistral": ModelDefinition(
        "ollama/mistral",
        ModelTier.CHEAP,
        32000,
        0.0,
        0.0,
    ),
}

TASK_MODEL_MAP: dict[TaskComplexity, ModelTier] = {
    TaskComplexity.SIMPLE: ModelTier.CHEAP,
    TaskComplexity.MODERATE: ModelTier.DEFAULT,
    TaskComplexity.COMPLEX: ModelTier.STRONG,
}

# Task → complexity mapping
TASK_COMPLEXITY_MAP: dict[str, TaskComplexity] = {
    "compile": TaskComplexity.COMPLEX,
    "compile_update": TaskComplexity.MODERATE,
    "query": TaskComplexity.COMPLEX,
    "query_simple": TaskComplexity.SIMPLE,
    "lint": TaskComplexity.SIMPLE,
    "classify": TaskComplexity.SIMPLE,
    "extract": TaskComplexity.MODERATE,
    "cluster": TaskComplexity.COMPLEX,
}


def get_model_for_task(
    task: str,
    online_model: str,
    offline_model: str | None = None,
    offline: bool = False,
) -> str:
    """Select the best model for a task based on complexity and online/offline status."""
    complexity = TASK_COMPLEXITY_MAP.get(task, TaskComplexity.MODERATE)
    tier = TASK_MODEL_MAP[complexity]

    if offline and offline_model:
        return offline_model

    # For online: use the configured model (simplified tier selection)
    # Tier selection is advisory — actual model routing depends on config.
    return online_model
