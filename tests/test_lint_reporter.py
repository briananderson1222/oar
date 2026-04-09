"""Tests for oar.lint.reporter — LintReporter."""

from pathlib import Path

from oar.lint.structural import LintIssue
from oar.lint.reporter import LintReporter


class TestGenerateReport:
    """generate_report."""

    def test_generate_report_creates_file(self, tmp_path):
        """Report file exists after generation."""
        reports_dir = tmp_path / "reports"
        reporter = LintReporter(reports_dir)

        issues = [
            LintIssue("error", "missing-field", "art-1", "Missing id"),
            LintIssue("warning", "stub", "art-2", "Empty section"),
        ]
        report_path = reporter.generate_report(issues)
        assert report_path.exists()
        assert "lint-report.md" in report_path.name

    def test_generate_report_contains_summary(self, tmp_path):
        """Has issue count by severity."""
        reports_dir = tmp_path / "reports"
        reporter = LintReporter(reports_dir)

        issues = [
            LintIssue("error", "missing-field", "art-1", "Missing id"),
            LintIssue("error", "missing-field", "art-2", "Missing title"),
            LintIssue("warning", "stub", "art-3", "Empty section"),
            LintIssue("info", "connection", "art-4", "Consider linking"),
        ]
        report_path = reporter.generate_report(issues)
        content = report_path.read_text()
        assert "Total issues:** 4" in content
        assert "Errors: 2" in content
        assert "Warnings: 1" in content
        assert "Info: 1" in content


class TestPrintReport:
    """print_report."""

    def test_print_report_no_error(self, tmp_path, capsys):
        """Runs without exception."""
        reports_dir = tmp_path / "reports"
        reporter = LintReporter(reports_dir)

        issues = [
            LintIssue("error", "missing-field", "art-1", "Missing id", "Add id field"),
        ]
        # Should not raise.
        reporter.print_report(issues)
