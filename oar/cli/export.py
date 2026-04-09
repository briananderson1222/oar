"""CLI export command — export wiki content in various formats."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.export.html_exporter import HTMLExporter
from oar.export.finetune_exporter import FinetuneExporter
from oar.export.slides import SlideExporter

console = Console()


def _find_vault_path() -> Optional[Path]:
    """Resolve vault path — prefer OAR_VAULT env var, else walk up from cwd."""
    env_path = os.environ.get("OAR_VAULT")
    if env_path:
        p = Path(env_path)
        if (p / ".oar" / "state.json").exists():
            return p

    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".oar" / "state.json").exists():
            return parent
    return None


def export_cmd(
    format: str = typer.Option("html", "--format", help="html|slides|finetune"),
    output: Path = typer.Option("./oar-export", "--output", help="Output directory"),
    moc: Optional[str] = typer.Option(None, "--moc", help="Export specific MOC only"),
) -> None:
    """Export wiki content in various formats."""
    vault_path = _find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    vault = Vault(vault_path)
    ops = VaultOps(vault)

    if format == "html":
        exporter = HTMLExporter(vault, ops)
        count = exporter.export(output, include_mocs=True)
        console.print(
            Panel(
                f"[bold green]Exported {count} pages[/bold green]\nOutput: {output}",
                title="oar export --format html",
                border_style="green",
            )
        )

    elif format == "slides":
        exporter = SlideExporter(vault, ops)
        if moc:
            output.mkdir(parents=True, exist_ok=True)
            path = exporter.export_moc_as_slides(moc, output / f"{moc}-slides.md")
            console.print(
                Panel(
                    f"[bold green]Exported MOC slides[/bold green]\nOutput: {path}",
                    title="oar export --format slides",
                    border_style="green",
                )
            )
        else:
            # Export all compiled articles as slides.
            output.mkdir(parents=True, exist_ok=True)
            count = 0
            for article_path in ops.list_compiled_articles():
                fm, _ = ops.read_article(article_path)
                article_id = fm.get("id", article_path.stem)
                if article_id:
                    exporter.export_article_as_slides(
                        article_id, output / f"{article_id}-slides.md"
                    )
                    count += 1
            console.print(
                Panel(
                    f"[bold green]Exported {count} slide decks[/bold green]\n"
                    f"Output: {output}",
                    title="oar export --format slides",
                    border_style="green",
                )
            )

    elif format == "finetune":
        exporter = FinetuneExporter(vault, ops)
        output.mkdir(parents=True, exist_ok=True)

        qa_path = output / "qa-pairs.jsonl"
        qa_count = exporter.export_qa_pairs(qa_path)

        summaries_path = output / "article-summaries.jsonl"
        summaries_count = exporter.export_articles_as_summaries(summaries_path)

        console.print(
            Panel(
                f"[bold green]Exported fine-tuning data[/bold green]\n"
                f"Q&A pairs: {qa_count} ({qa_path})\n"
                f"Article summaries: {summaries_count} ({summaries_path})",
                title="oar export --format finetune",
                border_style="green",
            )
        )

    else:
        console.print(
            f"[bold red]Error:[/bold red] Unknown format '{format}'. "
            "Use html, slides, or finetune."
        )
        raise typer.Exit(code=1)
