"""Tests for vault resolution precedence, the incident scenario, and `oar vault`."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from oar.cli._shared import find_vault_path, resolve_vault
from oar.cli.main import app
from oar.core import vault_registry
from oar.core.vault import Vault

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Isolate the registry and clear OAR_VAULT for every test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("OAR_VAULT", raising=False)
    return tmp_path


def _make_vault(path):
    v = Vault(path)
    v.init()
    return v.path


class TestResolvePrecedence:
    def test_cwd_beats_env(self, tmp_path, monkeypatch):
        """New precedence: cwd walk-up wins over OAR_VAULT env."""
        vault_a = _make_vault(tmp_path / "vault-a")  # the "real" polluted vault
        vault_b = _make_vault(tmp_path / "vault-b")  # the one we're standing in
        monkeypatch.setenv("OAR_VAULT", str(vault_a))
        monkeypatch.chdir(vault_b)

        resolved = resolve_vault(None)
        assert resolved is not None
        path, source = resolved
        assert path == vault_b.resolve()
        assert source == "cwd"

    def test_incident_env_never_overrides_cwd(self, tmp_path, monkeypatch):
        """The driving incident: OAR_VAULT=A, cwd inside B → resolves B."""
        vault_a = _make_vault(tmp_path / "A")
        vault_b = _make_vault(tmp_path / "B")
        monkeypatch.setenv("OAR_VAULT", str(vault_a))
        monkeypatch.chdir(vault_b)
        assert find_vault_path() == vault_b.resolve()

    def test_explicit_name_beats_cwd_and_env(self, tmp_path, monkeypatch):
        """--vault NAME beats both cwd and OAR_VAULT env."""
        vault_a = _make_vault(tmp_path / "A")
        vault_b = _make_vault(tmp_path / "B")
        vault_c = _make_vault(tmp_path / "C")
        vault_registry.add("c", vault_c)
        monkeypatch.setenv("OAR_VAULT", str(vault_a))
        monkeypatch.chdir(vault_b)

        resolved = resolve_vault("c")
        assert resolved is not None
        path, source = resolved
        assert path == vault_c.resolve()
        assert source == "registry:c"

    def test_explicit_path(self, tmp_path, monkeypatch):
        vault_a = _make_vault(tmp_path / "A")
        monkeypatch.chdir(tmp_path)
        resolved = resolve_vault(str(vault_a))
        assert resolved is not None
        path, source = resolved
        assert path == vault_a.resolve()
        assert source == "explicit path"

    def test_env_used_when_cwd_has_no_vault(self, tmp_path, monkeypatch):
        vault_a = _make_vault(tmp_path / "A")
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setenv("OAR_VAULT", str(vault_a))
        monkeypatch.chdir(empty)
        resolved = resolve_vault(None)
        assert resolved is not None
        path, source = resolved
        assert path == vault_a.resolve()
        assert source == "OAR_VAULT env"

    def test_registry_default_is_last_resort(self, tmp_path, monkeypatch):
        vault_a = _make_vault(tmp_path / "A")
        vault_registry.add("a", vault_a)  # becomes default
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.chdir(empty)
        resolved = resolve_vault(None)
        assert resolved is not None
        path, source = resolved
        assert path == vault_a.resolve()
        assert source == "registry default"

    def test_explicit_invalid_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert resolve_vault("/does/not/exist") is None

    def test_no_vault_anywhere_returns_none(self, tmp_path, monkeypatch):
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.chdir(empty)
        assert resolve_vault(None) is None


class TestVaultCLI:
    def test_add_and_list(self, tmp_path, monkeypatch):
        vault_a = _make_vault(tmp_path / "A")
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["vault", "add", "work", str(vault_a)])
        assert result.exit_code == 0
        assert "work" in result.output

        result = runner.invoke(app, ["vault", "list"])
        assert result.exit_code == 0
        assert "work" in result.output
        # The registry data itself records the resolved absolute path.
        assert vault_registry.load()["vaults"]["work"] == str(vault_a.resolve())

    def test_default_and_remove(self, tmp_path, monkeypatch):
        vault_a = _make_vault(tmp_path / "A")
        vault_b = _make_vault(tmp_path / "B")
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["vault", "add", "a", str(vault_a)])
        runner.invoke(app, ["vault", "add", "b", str(vault_b)])
        result = runner.invoke(app, ["vault", "default", "b"])
        assert result.exit_code == 0
        assert vault_registry.default_name() == "b"

        result = runner.invoke(app, ["vault", "remove", "a"])
        assert result.exit_code == 0
        assert "a" not in vault_registry.load()["vaults"]

    def test_remove_unknown_errors(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["vault", "remove", "ghost"])
        assert result.exit_code == 1

    def test_default_unknown_errors(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["vault", "default", "ghost"])
        assert result.exit_code == 1

    def test_list_shows_resolution(self, tmp_path, monkeypatch):
        vault_a = _make_vault(tmp_path / "A")
        monkeypatch.chdir(vault_a)
        runner.invoke(app, ["vault", "add", "a", str(vault_a)])
        result = runner.invoke(app, ["vault", "list"])
        assert "Resolves now" in result.output
        assert "via cwd" in result.output


class TestVaultBanner:
    """Mutating commands echo `vault: <abs path> (via <source>)` before acting."""

    def test_build_echoes_banner(self, tmp_vault, monkeypatch):
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["build"])
        assert f"vault: {Path(tmp_vault).resolve()} (via OAR_VAULT env)" in result.output

    def test_add_note_echoes_banner(self, tmp_vault, monkeypatch):
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            ["add-note", "--title", "Banner Test", "--body", "Body content here."],
        )
        assert result.exit_code == 0
        assert f"vault: {Path(tmp_vault).resolve()} (via OAR_VAULT env)" in result.output

    def test_vault_flag_reports_registry_source(self, tmp_vault, tmp_path, monkeypatch):
        monkeypatch.delenv("OAR_VAULT", raising=False)
        vault_registry.add("mine", tmp_vault)
        # cwd not a vault so --vault name must be honored.
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["add-note", "--title", "Reg", "--body", "x", "--vault", "mine"],
        )
        assert result.exit_code == 0
        assert "(via registry:mine)" in result.output
