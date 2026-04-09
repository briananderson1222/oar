"""oar lint — Run health checks and maintenance on the wiki."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from oar.cli._shared import find_vault_path, build_router
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.lint.reporter import LintReporter
from oar.lint.structural import StructuralChecker

console = Console()


def lint_cmd(
    quick: bool = typer.Option(
        False, "--quick", help="Structural checks only (no LLM)"
    ),
    articles: Optional[str] = typer.Option(
        None, "--articles", help="Specific article IDs (comma-separated)"
    ),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues"),
    report: bool = typer.Option(False, "--report", help="Generate report file"),
    coverage: bool = typer.Option(
        False, "--coverage", help="Analyze concept coverage gaps."
    ),
    quality: bool = typer.Option(False, "--quality", help="Score article quality."),
    web_search: bool = typer.Option(
        False, "--web-search", help="Search web for missing metadata."
    ),
) -> None:
    """Run health checks and maintenance on the wiki."""
    # Locate vault.
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    vault = Vault(vault_path)
    ops = VaultOps(vault)

    # Parse article IDs if specified.
    article_ids: list[str] | None = None
    if articles:
        article_ids = [a.strip() for a in articles.split(",") if a.strip()]

    # Run structural checks.
    checker = StructuralChecker(vault, ops)
    issues = checker.check_all()

    # Run consistency checks unless --quick.
    if not quick:
        try:
            from oar.lint.consistency import ConsistencyChecker

            router, cost_tracker, config = build_router(vault_path)
            checker = ConsistencyChecker(vault, ops, router)
            consistency_issues = checker.check_consistency(article_ids)
            issues.extend(consistency_issues)
        except Exception:
            # LLM checks are optional — don't fail the whole command.
            console.print(
                "[dim]Skipping LLM consistency checks (not configured).[/dim]"
            )

    # Coverage analysis.
    if coverage:
        from oar.lint.coverage import CoverageAnalyzer

        analyzer = CoverageAnalyzer(vault, ops)
        gaps = analyzer.find_concept_gaps()
        score = analyzer.coverage_score()
        console.print(f"\n[bold]Coverage Score:[/bold] {score:.0%}")
        if gaps:
            table = Table(title="Concept Gaps", show_header=True)
            table.add_column("Concept", style="cyan")
            table.add_column("Frequency", justify="right")
            table.add_column("Mentioned In", style="dim")
            for gap in gaps[:20]:
                table.add_row(
                    gap.concept,
                    str(gap.frequency),
                    ", ".join(gap.mentioned_in[:3]),
                )
            console.print(table)

    # Quality scoring.
    if quality:
        from oar.lint.quality_scorer import QualityScorer

        scorer = QualityScorer(vault, ops)
        reports = scorer.score_all()
        if reports:
            avg = sum(r.score for r in reports) / len(reports)
            console.print(f"\n[bold]Average Quality Score:[/bold] {avg:.2f}")
            table = Table(title="Article Quality", show_header=True)
            table.add_column("Article", style="cyan")
            table.add_column("Score", justify="right")
            table.add_column("Top Factor", style="dim")
            for r in sorted(reports, key=lambda x: x.score):
                worst = min(r.factors, key=r.factors.get) if r.factors else "n/a"
                table.add_row(r.article_id, f"{r.score:.2f}", worst)
            console.print(table)

    # Web augmentation.
    if web_search:
        from oar.lint.web_augmenter import WebAugmenter

        augmenter = WebAugmenter(vault, ops)
        missing = augmenter.find_missing_metadata()
        if missing:
            console.print(
                f"\n[bold]Articles with missing metadata:[/bold] {len(missing)}"
            )
            for item in missing[:10]:
                console.print(
                    f"  • {item['article_id']}: missing {', '.join(item['missing_fields'])}"
                )
        else:
            console.print("\n[green]All articles have complete metadata.[/green]")

    # Display results.
    reporter = LintReporter(vault_path / "05-logs" / "lint-reports")
    reporter.print_report(issues)

    # Optionally write report file.
    if report:
        report_path = reporter.generate_report(issues)
        console.print(f"\n[dim]Report saved to: {report_path}[/dim]")

    # Exit with error code if errors found.
    error_count = sum(1 for i in issues if i.severity == "error")
    if error_count > 0:
        raise typer.Exit(code=1)
