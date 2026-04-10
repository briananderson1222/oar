"""Tests for oar.core.vault — Vault class."""

import json
from pathlib import Path

import yaml

from oar.core.vault import Vault, REQUIRED_DIRS


class TestVaultInit:
    """Vault.init() behaviour."""

    def test_vault_init_creates_directory_tree(self, tmp_path):
        vault = Vault(tmp_path / "my-vault")
        vault.init()
        for rel in REQUIRED_DIRS:
            assert (vault.path / rel).is_dir(), f"Missing directory: {rel}"

    def test_vault_init_creates_state_json(self, tmp_path):
        vault = Vault(tmp_path / "my-vault")
        vault.init()
        state_file = vault.path / ".oar" / "state.json"
        assert state_file.is_file()
        data = json.loads(state_file.read_text())
        assert data["version"] == "0.2.0"
        assert "stats" in data
        assert "articles" in data

    def test_vault_init_creates_config_yaml(self, tmp_path):
        vault = Vault(tmp_path / "my-vault")
        vault.init()
        config_file = vault.path / ".oar" / "config.yaml"
        assert config_file.is_file()
        data = yaml.safe_load(config_file.read_text())
        assert "llm" in data
        assert data["llm"]["default_model"] == "claude-sonnet-4-20250514"

    def test_vault_init_creates_readme(self, tmp_path):
        vault = Vault(tmp_path / "my-vault")
        vault.init()
        readme = vault.path / "README.md"
        assert readme.is_file()
        content = readme.read_text()
        assert "OAR Vault" in content

    def test_vault_init_idempotent(self, tmp_path):
        vault = Vault(tmp_path / "my-vault")
        vault.init()
        # Capture the state file mtime before second init.
        state_file = vault.path / ".oar" / "state.json"
        first_content = state_file.read_text()
        # Second init must not raise.
        vault.init()
        # State file content should be unchanged (not overwritten).
        assert state_file.read_text() == first_content


class TestVaultValidate:
    """Vault.validate() behaviour."""

    def test_vault_validate_on_valid_vault(self, tmp_vault):
        vault = Vault(tmp_vault)
        assert vault.validate() is True

    def test_vault_validate_on_invalid_vault(self, tmp_path):
        empty = tmp_path / "empty-dir"
        empty.mkdir()
        vault = Vault(empty)
        assert vault.validate() is False


class TestVaultResolve:
    """Vault.resolve() behaviour."""

    def test_vault_resolve_path(self, tmp_vault):
        vault = Vault(tmp_vault)
        resolved = vault.resolve("01-raw/articles/test.md")
        assert resolved == tmp_vault / "01-raw" / "articles" / "test.md"
        assert resolved.is_absolute()


class TestVaultProperties:
    """Convenience directory properties."""

    def test_vault_properties(self, tmp_vault):
        vault = Vault(tmp_vault)
        assert vault.raw_dir == tmp_vault / "01-raw"
        assert vault.compiled_dir == tmp_vault / "02-compiled"
        assert vault.indices_dir == tmp_vault / "03-indices"
        assert vault.oar_dir == tmp_vault / ".oar"
