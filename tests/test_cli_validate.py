"""Tests for oar validate — single article validation."""

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

runner = CliRunner()


def _write_article(ops, article_id, title, body, **extra):
    metadata = {
        "id": article_id,
        "title": title,
        "type": "concept",
        "status": "draft",
        "tags": ["test"],
        "word_count": len(body.split()),
        **extra,
    }
    return ops.write_compiled_article("concepts", f"{article_id}.md", metadata, body)


class TestValidate:
    """oar validate command."""

    def test_validate_good_article(self, tmp_vault, monkeypatch):
        """Valid article passes all checks."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        _write_article(
            ops,
            "good-article",
            "Good Article",
            "This is a well-formed article about testing.",
        )

        result = runner.invoke(app, ["validate", "good-article"])
        assert result.exit_code == 0
        assert "all checks passed" in result.output.lower()

    def test_validate_missing_fields(self, tmp_vault, monkeypatch):
        """Article with missing required fields shows errors."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        # Write an article with no type and no status.
        ops.write_compiled_article(
            "concepts",
            "bad-article.md",
            {"id": "bad-article", "title": "Bad Article"},
            "Content without proper frontmatter.",
        )

        result = runner.invoke(app, ["validate", "bad-article"])
        assert result.exit_code == 1

    def test_validate_word_count_mismatch(self, tmp_vault, monkeypatch):
        """Word count mismatch is flagged as warning."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        _write_article(ops, "count-mismatch", "Mismatch", "Short.", word_count=999)

        result = runner.invoke(app, ["validate", "count-mismatch"])
        assert (
            "mismatch" in result.output.lower() or "word_count" in result.output.lower()
        )

    def test_validate_fixes_word_count(self, tmp_vault, monkeypatch):
        """--fix auto-corrects word count mismatch."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        _write_article(ops, "fix-count", "Fix Me", "Short text.", word_count=999)

        result = runner.invoke(app, ["validate", "fix-count", "--fix"])
        assert result.exit_code == 0  # Warnings don't cause exit 1

        # Verify it was fixed.
        from oar.core.frontmatter import FrontmatterManager

        fm = FrontmatterManager()
        path = ops.get_article_by_id("fix-count")
        meta, _ = fm.read(path)
        assert meta["word_count"] == 2  # "Short text." = 2 words

    def test_validate_broken_wikilinks(self, tmp_vault, monkeypatch):
        """Broken wikilinks are reported."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        _write_article(
            ops,
            "linker",
            "Linker",
            "See [[nonexistent-thing]] and [[also-missing]] for details.",
        )

        result = runner.invoke(app, ["validate", "linker"])
        assert "broken" in result.output.lower() or "links" in result.output.lower()

    def test_validate_no_tags_info(self, tmp_vault, monkeypatch):
        """Missing tags is reported as info."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "no-tags.md",
            {
                "id": "no-tags",
                "title": "No Tags",
                "type": "concept",
                "status": "draft",
                "tags": [],
            },
            "Content without tags.",
        )

        result = runner.invoke(app, ["validate", "no-tags"])
        assert "no tags" in result.output.lower()

    def test_validate_not_found(self, tmp_vault, monkeypatch):
        """Non-existent article exits with error."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["validate", "does-not-exist"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
