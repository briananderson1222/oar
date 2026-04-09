"""Tests for oar.lint.structural — StructuralChecker."""

from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.core.frontmatter import FrontmatterManager
from oar.lint.structural import StructuralChecker, LintIssue


class TestCheckMissingFrontmatter:
    """check_missing_frontmatter."""

    def test_check_missing_frontmatter_clean(self, tmp_vault):
        """No issues on valid articles with proper frontmatter."""
        ops = VaultOps(Vault(tmp_vault))
        # Write a valid compiled article.
        ops.write_compiled_article(
            "concepts",
            "test-article.md",
            {
                "id": "test-article",
                "title": "Test",
                "type": "concept",
                "status": "draft",
            },
            "Body text here.",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_missing_frontmatter()
        assert issues == []

    def test_check_missing_frontmatter_finds_empty(self, tmp_vault):
        """Article with no frontmatter flagged."""
        # Write a .md file with no frontmatter directly.
        article_path = tmp_vault / "02-compiled" / "concepts" / "no-fm.md"
        article_path.write_text("Just some text with no frontmatter.\n")
        ops = VaultOps(Vault(tmp_vault))
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_missing_frontmatter()
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].category == "missing-field"
        assert "no YAML frontmatter" in issues[0].message


class TestCheckRequiredFields:
    """check_required_fields."""

    def test_check_required_fields_valid(self, tmp_vault):
        """No issues when all required fields present."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "complete.md",
            {
                "id": "complete",
                "title": "Complete",
                "type": "concept",
                "status": "draft",
            },
            "Some body text.",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_required_fields()
        assert issues == []

    def test_check_required_fields_missing_id(self, tmp_vault):
        """Error for missing id field."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "no-id.md",
            {"title": "No ID", "type": "concept", "status": "draft"},
            "Body text.",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_required_fields()
        assert any(i.message == "Missing required field: id" for i in issues)

    def test_check_required_fields_missing_type(self, tmp_vault):
        """Error for missing type field."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "no-type.md",
            {"id": "no-type", "title": "No Type", "status": "draft"},
            "Body text.",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_required_fields()
        assert any("type" in i.message for i in issues)


class TestCheckEmptySections:
    """check_empty_sections."""

    def test_check_empty_sections_clean(self, tmp_vault):
        """No issues on article with content in all sections."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "full.md",
            {"id": "full", "title": "Full", "type": "concept", "status": "draft"},
            "# Title\n\n## Overview\n\nSome content here.\n",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_empty_sections()
        assert issues == []

    def test_check_empty_sections_finds_empty(self, tmp_vault):
        """Empty section flagged."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "empty-sec.md",
            {
                "id": "empty-sec",
                "title": "Empty Section",
                "type": "concept",
                "status": "draft",
            },
            "# Title\n\n## Overview\n\nSome content.\n\n## Details\n\n",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_empty_sections()
        assert len(issues) >= 1
        assert any(i.category == "stub" for i in issues)


class TestCheckWordCounts:
    """check_word_counts."""

    def test_check_word_counts_match(self, tmp_vault):
        """No issue when counts match."""
        ops = VaultOps(Vault(tmp_vault))
        body = "one two three four five"
        ops.write_compiled_article(
            "concepts",
            "matched.md",
            {
                "id": "matched",
                "title": "Matched",
                "type": "concept",
                "status": "draft",
                "word_count": 5,
            },
            body,
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_word_counts()
        assert issues == []

    def test_check_word_counts_mismatch(self, tmp_vault):
        """Warning when frontmatter count != actual."""
        ops = VaultOps(Vault(tmp_vault))
        body = "one two three"
        ops.write_compiled_article(
            "concepts",
            "mismatch.md",
            {
                "id": "mismatch",
                "title": "Mismatch",
                "type": "concept",
                "status": "draft",
                "word_count": 100,
            },
            body,
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_word_counts()
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].category == "inconsistent"
        assert "mismatch" in issues[0].message.lower()


class TestCheckAll:
    """check_all aggregation."""

    def test_check_all_aggregates(self, tmp_vault):
        """Returns combined issues from all checks."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "ok.md",
            {"id": "ok", "title": "OK", "type": "concept", "status": "draft"},
            "Valid article body text.",
        )
        checker = StructuralChecker(Vault(tmp_vault), ops)
        issues = checker.check_all()
        # Should return a list (may be empty or have items depending on checks).
        assert isinstance(issues, list)
        assert all(isinstance(i, LintIssue) for i in issues)
