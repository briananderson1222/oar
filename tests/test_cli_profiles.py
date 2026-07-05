"""Tests for `oar profiles` CLI command."""

from typer.testing import CliRunner

from oar.cli.main import app

runner = CliRunner()


class TestProfilesCLI:
    def test_profiles_list(self, tmp_vault, monkeypatch):
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["profiles"])
        assert result.exit_code == 0
        assert "Compile Profiles" in result.output
        assert "default" in result.output

    def test_profiles_show(self, tmp_vault, monkeypatch):
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["profiles", "--show", "repo-architecture"])
        assert result.exit_code == 0
        assert "Compile Profile: repo-architecture" in result.output
        assert "default_type" in result.output
