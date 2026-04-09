"""Tests for oar.core.config — OarConfig persistence."""

from pathlib import Path

from oar.core.config import OarConfig, LlmConfig, CompileConfig


class TestOarConfigDefaults:
    """Default values on a freshly constructed config."""

    def test_config_default_values(self):
        cfg = OarConfig()
        assert cfg.vault_path == ""
        assert cfg.llm.default_model == "claude-sonnet-4-20250514"
        assert cfg.llm.fallback_model == "ollama/llama3.1"
        assert cfg.llm.max_cost_per_call == 0.50
        assert cfg.compile.default_type == "concept"
        assert cfg.compile.auto_index is True


class TestOarConfigPersistence:
    """Round-trip save / load."""

    def test_config_save_and_load(self, tmp_path):
        config_path = tmp_path / ".oar" / "config.yaml"
        original = OarConfig(vault_path="/tmp/test-vault")
        original.save(config_path)

        loaded = OarConfig.load(config_path)
        assert loaded.vault_path == "/tmp/test-vault"
        assert loaded.llm.default_model == "claude-sonnet-4-20250514"
        assert loaded.compile.auto_index is True

    def test_config_load_missing_file(self, tmp_path):
        missing = tmp_path / "does-not-exist.yaml"
        cfg = OarConfig.load(missing)
        # Should return defaults.
        assert cfg.vault_path == ""
        assert cfg.llm.default_model == "claude-sonnet-4-20250514"
