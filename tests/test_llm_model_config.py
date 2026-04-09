"""Tests for oar.llm.model_config — ModelConfig, task routing, model registry."""

from oar.llm.model_config import (
    MODEL_REGISTRY,
    TASK_COMPLEXITY_MAP,
    TASK_MODEL_MAP,
    ModelDefinition,
    ModelTier,
    TaskComplexity,
    get_model_for_task,
)


class TestTaskComplexityMapping:
    """Each task maps to the correct complexity level."""

    def test_compile_is_complex(self):
        assert TASK_COMPLEXITY_MAP["compile"] == TaskComplexity.COMPLEX

    def test_compile_update_is_moderate(self):
        assert TASK_COMPLEXITY_MAP["compile_update"] == TaskComplexity.MODERATE

    def test_query_is_complex(self):
        assert TASK_COMPLEXITY_MAP["query"] == TaskComplexity.COMPLEX

    def test_query_simple_is_simple(self):
        assert TASK_COMPLEXITY_MAP["query_simple"] == TaskComplexity.SIMPLE

    def test_lint_is_simple(self):
        assert TASK_COMPLEXITY_MAP["lint"] == TaskComplexity.SIMPLE

    def test_classify_is_simple(self):
        assert TASK_COMPLEXITY_MAP["classify"] == TaskComplexity.SIMPLE

    def test_extract_is_moderate(self):
        assert TASK_COMPLEXITY_MAP["extract"] == TaskComplexity.MODERATE

    def test_cluster_is_complex(self):
        assert TASK_COMPLEXITY_MAP["cluster"] == TaskComplexity.COMPLEX

    def test_unknown_task_defaults_to_moderate(self):
        assert (
            TASK_COMPLEXITY_MAP.get("unknown", TaskComplexity.MODERATE)
            == TaskComplexity.MODERATE
        )


class TestTaskModelMap:
    """TaskComplexity maps to the expected ModelTier."""

    def test_simple_maps_to_cheap(self):
        assert TASK_MODEL_MAP[TaskComplexity.SIMPLE] == ModelTier.CHEAP

    def test_moderate_maps_to_default(self):
        assert TASK_MODEL_MAP[TaskComplexity.MODERATE] == ModelTier.DEFAULT

    def test_complex_maps_to_strong(self):
        assert TASK_MODEL_MAP[TaskComplexity.COMPLEX] == ModelTier.STRONG


class TestGetModelForTask:
    """get_model_for_task returns correct model based on context."""

    def test_get_model_for_task_online(self):
        """Returns the online model for online tasks."""
        result = get_model_for_task("compile", "claude-sonnet-4-20250514")
        assert result == "claude-sonnet-4-20250514"

    def test_get_model_for_task_offline(self):
        """Returns offline model when offline=True."""
        result = get_model_for_task(
            "compile",
            "claude-sonnet-4-20250514",
            offline_model="ollama/llama3.1",
            offline=True,
        )
        assert result == "ollama/llama3.1"

    def test_get_model_for_task_offline_no_model(self):
        """Returns online model when offline=True but no offline_model."""
        result = get_model_for_task(
            "compile",
            "claude-sonnet-4-20250514",
            offline=True,
        )
        assert result == "claude-sonnet-4-20250514"

    def test_get_model_for_task_online_not_offline(self):
        """Returns online model when offline=False even with offline_model set."""
        result = get_model_for_task(
            "compile",
            "claude-sonnet-4-20250514",
            offline_model="ollama/llama3.1",
            offline=False,
        )
        assert result == "claude-sonnet-4-20250514"


class TestModelRegistry:
    """Model registry has expected models."""

    def test_model_registry_has_expected_models(self):
        expected = [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-20250414",
            "ollama/llama3.1",
            "ollama/mistral",
        ]
        for name in expected:
            assert name in MODEL_REGISTRY, f"{name} missing from MODEL_REGISTRY"

    def test_sonnet_is_default_tier(self):
        assert MODEL_REGISTRY["claude-sonnet-4-20250514"].tier == ModelTier.DEFAULT

    def test_haiku_is_cheap_tier(self):
        assert MODEL_REGISTRY["claude-haiku-4-20250414"].tier == ModelTier.CHEAP

    def test_ollama_llama_is_default_tier(self):
        assert MODEL_REGISTRY["ollama/llama3.1"].tier == ModelTier.DEFAULT

    def test_ollama_mistral_is_cheap_tier(self):
        assert MODEL_REGISTRY["ollama/mistral"].tier == ModelTier.CHEAP


class TestModelDefinitionCostCalculation:
    """ModelDefinition cost_for() calculates correctly."""

    def test_cost_calculation_sonnet(self):
        model = MODEL_REGISTRY["claude-sonnet-4-20250514"]
        # 1000 * 3/1M + 500 * 15/1M = 0.003 + 0.0075 = 0.0105
        cost = model.cost_for(1000, 500)
        assert cost == 0.0105

    def test_cost_calculation_haiku(self):
        model = MODEL_REGISTRY["claude-haiku-4-20250414"]
        # 1000 * 0.25/1M + 500 * 1.25/1M = 0.00025 + 0.000625 = 0.000875
        cost = model.cost_for(1000, 500)
        assert cost == 0.00087500

    def test_cost_calculation_free_model(self):
        model = MODEL_REGISTRY["ollama/llama3.1"]
        cost = model.cost_for(10000, 5000)
        assert cost == 0.0

    def test_cost_calculation_zero_tokens(self):
        model = MODEL_REGISTRY["claude-sonnet-4-20250514"]
        cost = model.cost_for(0, 0)
        assert cost == 0.0
