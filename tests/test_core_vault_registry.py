"""Tests for oar.core.vault_registry — named-vault registry."""

import pytest

from oar.core import vault_registry


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point XDG_CONFIG_HOME at a temp dir so tests never touch the real registry."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


class TestRegistryLocation:
    def test_respects_xdg_config_home(self, tmp_path):
        expected = tmp_path / "config" / "oar" / "vaults.yaml"
        assert vault_registry.registry_path() == expected

    def test_load_missing_returns_empty(self):
        data = vault_registry.load()
        assert data == {"vaults": {}, "default": None}


class TestAddRemove:
    def test_add_creates_entry_and_autodefaults(self, tmp_path):
        vpath = tmp_path / "vault-a"
        vpath.mkdir()
        data = vault_registry.add("a", vpath)
        assert data["vaults"]["a"] == str(vpath.resolve())
        # First vault becomes default.
        assert data["default"] == "a"
        # Persisted.
        assert vault_registry.load()["vaults"]["a"] == str(vpath.resolve())

    def test_second_add_does_not_change_default(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        vault_registry.add("a", tmp_path / "a")
        vault_registry.add("b", tmp_path / "b")
        assert vault_registry.default_name() == "a"

    def test_remove_clears_default_when_needed(self, tmp_path):
        (tmp_path / "a").mkdir()
        vault_registry.add("a", tmp_path / "a")
        vault_registry.remove("a")
        data = vault_registry.load()
        assert "a" not in data["vaults"]
        assert data["default"] is None

    def test_resolve_name(self, tmp_path):
        (tmp_path / "a").mkdir()
        vault_registry.add("a", tmp_path / "a")
        assert vault_registry.resolve_name("a") == (tmp_path / "a").resolve()
        assert vault_registry.resolve_name("missing") is None


class TestSetDefault:
    def test_set_default(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        vault_registry.add("a", tmp_path / "a")
        vault_registry.add("b", tmp_path / "b")
        vault_registry.set_default("b")
        assert vault_registry.default_name() == "b"

    def test_set_default_unknown_raises(self):
        with pytest.raises(KeyError):
            vault_registry.set_default("nope")

    def test_load_drops_dangling_default(self, tmp_path):
        # Manually write a registry whose default points at a removed vault.
        path = vault_registry.registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("vaults: {}\ndefault: ghost\n")
        assert vault_registry.load()["default"] is None
