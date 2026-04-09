"""Tests for advanced lint — coverage, quality scoring, web augmentation."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.lint.coverage import CoverageAnalyzer, ConceptGap
from oar.lint.quality_scorer import QualityScorer
from oar.lint.web_augmenter import WebAugmenter

runner = CliRunner()


def _write_compiled(ops, subdir, filename, article_id, title, body, **meta_extra):
    metadata = {
        "id": article_id,
        "title": title,
        "type": "concept",
        "status": "draft",
        **meta_extra,
    }
    return ops.write_compiled_article(subdir, filename, metadata, body)


class TestCoverageAnalyzer:
    """CoverageAnalyzer — concept gap detection."""

    def test_find_concept_gaps_empty_vault(self, tmp_vault):
        """No articles → no gaps."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        analyzer = CoverageAnalyzer(vault, ops)
        assert analyzer.find_concept_gaps() == []

    def test_find_concept_gaps_detects_broken_links(self, tmp_vault):
        """Wikilinks to non-existent articles are concept gaps."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "a.md",
            "alpha",
            "Alpha",
            "Content with [[beta]] and [[gamma]].",
            tags=["test"],
        )

        analyzer = CoverageAnalyzer(vault, ops)
        gaps = analyzer.find_concept_gaps()

        assert len(gaps) >= 2
        gap_concepts = {g.concept for g in gaps}
        assert "beta" in gap_concepts
        assert "gamma" in gap_concepts

    def test_find_concept_gaps_excludes_existing(self, tmp_vault):
        """Links to existing articles are NOT gaps."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "a.md",
            "alpha",
            "Alpha",
            "Content with [[beta]].",
        )
        _write_compiled(
            ops,
            "concepts",
            "b.md",
            "beta",
            "Beta",
            "Content with [[alpha]].",
        )

        analyzer = CoverageAnalyzer(vault, ops)
        gaps = analyzer.find_concept_gaps()
        assert gaps == []

    def test_coverage_score_perfect(self, tmp_vault):
        """All links resolved → 1.0."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(ops, "concepts", "a.md", "a", "A", "See [[b]].")
        _write_compiled(ops, "concepts", "b.md", "b", "B", "See [[a]].")

        analyzer = CoverageAnalyzer(vault, ops)
        assert analyzer.coverage_score() == 1.0

    def test_coverage_score_with_gaps(self, tmp_vault):
        """Some unresolved links → score < 1.0."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(ops, "concepts", "a.md", "a", "A", "See [[b]] and [[missing]].")
        _write_compiled(ops, "concepts", "b.md", "b", "B", "See [[a]].")

        analyzer = CoverageAnalyzer(vault, ops)
        assert 0.0 < analyzer.coverage_score() < 1.0


class TestQualityScorer:
    """QualityScorer — article quality assessment."""

    def test_score_perfect_article(self, tmp_vault):
        """Well-structured article with complete metadata scores high."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "good.md",
            "good",
            "Good Article",
            "# Good Article\n\n## Overview\n\nDetailed content here. " * 20,
            tags=["test", "quality"],
            domain=["general"],
            confidence=0.9,
            complexity="intermediate",
            related=["other"],
        )

        scorer = QualityScorer(vault, ops)
        report = scorer.score_article("good")
        assert report.score >= 0.6  # Should be reasonably high

    def test_score_stub_article(self, tmp_vault):
        """Minimal article scores low."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "stub.md",
            "stub",
            "Stub",
            "Short.",
        )

        scorer = QualityScorer(vault, ops)
        report = scorer.score_article("stub")
        assert report.score < 0.5

    def test_score_factors_populated(self, tmp_vault):
        """All quality factors are populated."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "test.md",
            "test",
            "Test",
            "Some content about [[links]].",
            tags=["test"],
        )

        scorer = QualityScorer(vault, ops)
        report = scorer.score_article("test")
        assert "frontmatter" in report.factors
        assert "content_depth" in report.factors
        assert "links" in report.factors
        assert "tags" in report.factors
        assert "structure" in report.factors

    def test_score_all(self, tmp_vault):
        """score_all returns reports for all articles."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(ops, "concepts", "a.md", "a", "A", "Content.")
        _write_compiled(ops, "concepts", "b.md", "b", "B", "Content.")

        scorer = QualityScorer(vault, ops)
        reports = scorer.score_all()
        assert len(reports) == 2


class TestWebAugmenter:
    """WebAugmenter — missing metadata detection and web search."""

    def test_find_missing_metadata(self, tmp_vault):
        """Detects articles missing author, published, or source_url."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "no-meta.md",
            "no-meta",
            "No Metadata",
            "Content.",
        )

        augmenter = WebAugmenter(vault, ops)
        missing = augmenter.find_missing_metadata()

        assert len(missing) >= 1
        item = next(m for m in missing if m["article_id"] == "no-meta")
        assert "author" in item["missing_fields"]

    def test_find_no_missing_when_complete(self, tmp_vault):
        """Article with all metadata has no missing fields."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "complete.md",
            "complete",
            "Complete",
            "Content.",
            author="Author",
            published="2024-01-01",
            source_url="https://example.com",
        )

        augmenter = WebAugmenter(vault, ops)
        missing = augmenter.find_missing_metadata()
        complete_items = [m for m in missing if m["article_id"] == "complete"]
        assert complete_items == []

    def test_augment_article_no_results(self, tmp_vault):
        """When web search returns nothing, returns info issue."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)

        _write_compiled(
            ops,
            "concepts",
            "test.md",
            "test",
            "Test Article",
            "Content.",
        )

        augmenter = WebAugmenter(vault, ops)
        with patch.object(augmenter, "_search", return_value=[]):
            issues = augmenter.augment_article("test")

        assert len(issues) >= 1
        assert issues[0].category == "web-augment"


class TestLintCLICoverage:
    """CLI --coverage flag tests."""

    def test_lint_coverage_shows_score(self, tmp_vault, monkeypatch):
        """oar lint --coverage shows coverage score."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["lint", "--coverage", "--quick"])
        assert result.exit_code == 0
        assert "Coverage" in result.output or "coverage" in result.output.lower()


class TestLintCLIQuality:
    """CLI --quality flag tests."""

    def test_lint_quality_shows_scores(self, tmp_vault, monkeypatch):
        """oar lint --quality shows quality scores."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        ops = VaultOps(Vault(tmp_vault))
        _write_compiled(
            ops,
            "concepts",
            "test.md",
            "test",
            "Test",
            "Some content.",
        )

        result = runner.invoke(app, ["lint", "--quality", "--quick"])
        assert result.exit_code == 0
        assert "Quality" in result.output or "quality" in result.output.lower()
