"""Tests for oar add-note — structural note writer."""

from pathlib import Path

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

runner = CliRunner()


class TestAddNote:
    """oar add-note command."""

    def test_add_note_basic(self, tmp_vault, monkeypatch):
        """Add a basic note with title and body."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            [
                "add-note",
                "--title",
                "Test Concept",
                "--body",
                "This is a test concept about testing.",
            ],
        )
        assert result.exit_code == 0
        assert "Note added" in result.output
        assert "test-concept" in result.output

        # Verify the file was created.
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        path = ops.get_article_by_id("test-concept")
        assert path is not None

        # Verify frontmatter.
        fm = FrontmatterManager()
        meta, body = fm.read(path)
        assert meta["id"] == "test-concept"
        assert meta["title"] == "Test Concept"
        assert meta["type"] == "concept"
        assert meta["status"] == "draft"
        assert "testing" in body

    def test_add_note_with_tags(self, tmp_vault, monkeypatch):
        """Add a note with tags."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            [
                "add-note",
                "--title",
                "Tagged Note",
                "--tags",
                "testing,unit-test,oar",
                "--body",
                "Tagged content.",
            ],
        )
        assert result.exit_code == 0

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        path = ops.get_article_by_id("tagged-note")
        fm = FrontmatterManager()
        meta, _ = fm.read(path)
        assert "testing" in meta["tags"]
        assert "unit-test" in meta["tags"]

    def test_add_note_with_type(self, tmp_vault, monkeypatch):
        """Add a note with a specific type."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            [
                "add-note",
                "--title",
                "How to Test",
                "--type",
                "method",
                "--body",
                "Step 1: Write tests. Step 2: Run tests.",
            ],
        )
        assert result.exit_code == 0

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        path = ops.get_article_by_id("how-to-test")
        fm = FrontmatterManager()
        meta, _ = fm.read(path)
        assert meta["type"] == "method"
        assert "methods" in str(path)

    def test_add_note_with_related(self, tmp_vault, monkeypatch):
        """Add a note with related article links."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            [
                "add-note",
                "--title",
                "Related Note",
                "--related",
                "some-other-note,another-note",
                "--body",
                "Content with related articles.",
            ],
        )
        assert result.exit_code == 0

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        path = ops.get_article_by_id("related-note")
        fm = FrontmatterManager()
        meta, _ = fm.read(path)
        assert "[[some-other-note]]" in meta["related"]

    def test_add_note_from_file(self, tmp_vault, monkeypatch, tmp_path):
        """Add a note from a file."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Write a temp file with content.
        content_file = tmp_path / "note-content.md"
        content_file.write_text("# My File Note\n\nContent from a file.")

        result = runner.invoke(
            app,
            ["add-note", "--title", "File Note", "--file", str(content_file)],
        )
        assert result.exit_code == 0

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        path = ops.get_article_by_id("file-note")
        assert path is not None
        fm = FrontmatterManager()
        _, body = fm.read(path)
        assert "Content from a file" in body

    def test_add_note_invalid_type(self, tmp_vault, monkeypatch):
        """Invalid type exits with error."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            ["add-note", "--title", "Bad Type", "--type", "invalid", "--body", "x"],
        )
        assert result.exit_code == 1
        assert "Invalid type" in result.output

    def test_add_note_no_vault(self, tmp_path, monkeypatch):
        """No vault found exits with error."""
        monkeypatch.delenv("OAR_VAULT", raising=False)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["add-note", "--title", "No Vault", "--body", "x"],
        )
        assert result.exit_code == 1

    def test_add_note_updates_state(self, tmp_vault, monkeypatch):
        """Adding a note updates state.json stats."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        runner.invoke(
            app,
            ["add-note", "--title", "State Test", "--body", "Testing state update."],
        )

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        compiled = ops.list_compiled_articles()
        assert len(compiled) >= 1

    def test_add_note_generates_correct_slug(self, tmp_vault, monkeypatch):
        """Title with special characters generates a clean slug."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            [
                "add-note",
                "--title",
                "C++ & Python! Best Practices",
                "--body",
                "Content.",
            ],
        )
        assert result.exit_code == 0
        assert "c-python-best-practices" in result.output

    def test_add_note_with_all_options(self, tmp_vault, monkeypatch):
        """All options together work correctly."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(
            app,
            [
                "add-note",
                "--title",
                "Full Featured Note",
                "--type",
                "method",
                "--tags",
                "testing,full-featured",
                "--related",
                "other-note",
                "--status",
                "mature",
                "--confidence",
                "0.95",
                "--body",
                "A fully specified note.",
            ],
        )
        assert result.exit_code == 0

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        path = ops.get_article_by_id("full-featured-note")
        fm = FrontmatterManager()
        meta, _ = fm.read(path)
        assert meta["type"] == "method"
        assert meta["status"] == "mature"
        assert meta["confidence"] == 0.95
        assert "full-featured" in meta["tags"]
