"""oar validate — Check a single article's structure and links."""

from __future__ import annotations

import re
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from oar.cli._shared import find_vault_path
from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

console = Console()


def validate_cmd(
    article_id: str = typer.Argument(..., help="Article ID to validate."),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix fixable issues."),
) -> None:
    """Validate a single article's structure, frontmatter, and links."""
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    vault = Vault(vault_path)
    ops = VaultOps(vault)
    fm = FrontmatterManager()

    # Find the article.
    path = ops.get_article_by_id(article_id)
    if path is None:
        console.print(f"[bold red]Error:[/bold red] Article not found: {article_id}")
        raise typer.Exit(code=1)

    meta, body = fm.read(path)
    issues: list[dict] = []

    # Check required fields.
    for field in ("id", "title", "type", "status"):
        if field not in meta or not meta[field]:
            issues.append({"field": field, "status": "missing", "severity": "error"})

    # Check type is valid.
    if "type" in meta and meta["type"] not in fm.VALID_COMPILED_TYPES:
        issues.append(
            {
                "field": "type",
                "status": f"invalid ({meta['type']})",
                "severity": "error",
            }
        )

    # Check status is valid.
    if "status" in meta and meta["status"] not in fm.VALID_STATUSES:
        issues.append(
            {
                "field": "status",
                "status": f"invalid ({meta['status']})",
                "severity": "error",
            }
        )

    # Check word count.
    actual_words = ops.compute_word_count(body)
    if "word_count" in meta and meta["word_count"] != actual_words:
        issues.append(
            {
                "field": "word_count",
                "status": f"mismatch (declared {meta['word_count']}, actual {actual_words})",
                "severity": "warning",
            }
        )
        if fix:
            fm.update_metadata(path, {"word_count": actual_words})

    # Check for empty body.
    if not body.strip():
        issues.append({"field": "body", "status": "empty", "severity": "warning"})

    # Check wikilinks resolve.
    wikilinks = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]", body)
    broken_links = []
    for link in set(wikilinks):
        target = ops.get_article_by_id(link.strip())
        if target is None:
            broken_links.append(link.strip())
    if broken_links:
        issues.append(
            {
                "field": "links",
                "status": f"{len(broken_links)} broken: {', '.join(broken_links[:5])}",
                "severity": "info",
            }
        )

    # Check tags exist.
    tags = meta.get("tags", [])
    if not tags:
        issues.append({"field": "tags", "status": "no tags", "severity": "info"})

    # Display results.
    if not issues:
        console.print(f"[bold green]✓[/bold green] {article_id} — all checks passed")
    else:
        table = Table(title=f"Validation: {article_id}", show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Severity", style="bold")

        for issue in issues:
            severity_style = {"error": "red", "warning": "yellow", "info": "blue"}[
                issue["severity"]
            ]
            table.add_row(
                issue["field"],
                issue["status"],
                f"[{severity_style}]{issue['severity']}[/{severity_style}]",
            )
        console.print(table)

        if fix:
            console.print("[dim]Applied auto-fixes where possible.[/dim]")

        error_count = sum(1 for i in issues if i["severity"] == "error")
        if error_count > 0:
            raise typer.Exit(code=1)
