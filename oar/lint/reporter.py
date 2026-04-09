"""Lint reporter — generate and display lint reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from oar.lint.structural import LintIssue


class LintReporter:
    """Generate lint reports."""

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    def generate_report(self, issues: list[LintIssue]) -> Path:
        """Write a dated lint report to 05-logs/lint-reports/."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}-lint-report.md"
        report_path = self.reports_dir / filename

        lines: list[str] = []
        lines.append(f"# Lint Report — {date_str}")
        lines.append("")

        # Summary stats.
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        infos = sum(1 for i in issues if i.severity == "info")
        lines.append(f"**Total issues:** {len(issues)}")
        lines.append(f"- Errors: {errors}")
        lines.append(f"- Warnings: {warnings}")
        lines.append(f"- Info: {infos}")
        lines.append("")

        # Group by severity.
        for severity in ("error", "warning", "info"):
            group = [i for i in issues if i.severity == severity]
            if not group:
                continue
            lines.append(f"## {severity.capitalize()}s")
            lines.append("")
            for issue in group:
                lines.append(
                    f"- **[{issue.category}]** {issue.article_id}: {issue.message}"
                )
                if issue.suggestion:
                    lines.append(f"  - _Suggestion: {issue.suggestion}_")
            lines.append("")

        report_path.write_text("\n".join(lines))
        return report_path

    def print_report(self, issues: list[LintIssue]) -> None:
        """Print formatted report to console using Rich."""
        console = Console()

        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        infos = sum(1 for i in issues if i.severity == "info")

        console.print(f"\n[bold]Lint Report[/bold]")
        console.print(
            f"  {len(issues)} issues: "
            f"[red]{errors} errors[/red], "
            f"[yellow]{warnings} warnings[/yellow], "
            f"[blue]{infos} info[/blue]\n"
        )

        if not issues:
            console.print("[green]No issues found.[/green]")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("Severity", width=10)
        table.add_column("Category", width=15)
        table.add_column("Article", width=30)
        table.add_column("Message")
        table.add_column("Suggestion")

        for issue in issues:
            severity_style = {
                "error": "red",
                "warning": "yellow",
                "info": "blue",
            }.get(issue.severity, "white")

            table.add_row(
                f"[{severity_style}]{issue.severity}[/{severity_style}]",
                issue.category,
                issue.article_id,
                issue.message,
                issue.suggestion,
            )

        console.print(table)
