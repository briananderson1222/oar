"""CLI query command — ask questions against the wiki knowledge base."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from oar.cli._shared import find_vault_path, build_router
from oar.core.link_resolver import LinkResolver
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.moc_builder import MocBuilder
from oar.query.context_manager import ContextManager
from oar.query.engine import QueryEngine
from oar.query.tools import ToolExecutor
from oar.search.indexer import SearchIndexer
from oar.search.searcher import Searcher

console = Console()


def _get_or_build_index(vault_path: Path) -> Path:
    """Return path to search.db, building the index if needed."""
    db_path = vault_path / ".oar" / "search-index" / "search.db"
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        vault = Vault(vault_path)
        ops = VaultOps(vault)
        indexer = SearchIndexer(db_path)
        indexer.index_vault(vault, ops)
        indexer.close()
    return db_path


def query_cmd(
    question: str = typer.Argument(None, help="Question to ask"),
    save: bool = typer.Option(False, "--save", help="Save output to vault"),
    format: str = typer.Option("answer", "--format", help="Output: answer|json"),
    stdout: bool = typer.Option(False, "--stdout", help="Print to stdout"),
    max_cost: float = typer.Option(2.00, "--max-cost", help="Max cost for this query"),
    interactive: bool = typer.Option(False, "--interactive", help="Interactive mode"),
) -> None:
    """Ask questions against the wiki knowledge base."""
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    if question is None:
        console.print("[bold red]Error:[/bold red] Please provide a question.")
        raise typer.Exit(code=1)

    # Build components.
    router, cost_tracker, config = build_router(vault_path)
    vault = Vault(vault_path)
    ops = VaultOps(vault)
    link_resolver = LinkResolver(vault, ops)
    moc_builder = MocBuilder(vault, ops)
    context_manager = ContextManager(vault, ops, link_resolver)

    # Ensure search index exists.
    db_path = _get_or_build_index(vault_path)
    searcher = Searcher(db_path)

    tool_executor = ToolExecutor(vault, ops, searcher, link_resolver, moc_builder)
    engine = QueryEngine(context_manager, tool_executor, router)

    # Check budget.
    if not cost_tracker.check_budget(max_cost):
        console.print(
            f"[bold red]Error:[/bold red] Session cost exceeds --max-cost ${max_cost:.2f}"
        )
        raise typer.Exit(code=1)

    try:
        result = engine.query(question)
    except Exception as exc:
        console.print(f"[bold red]Query error:[/bold red] {exc}")
        console.print(
            "[dim]Hint: Set ANTHROPIC_API_KEY or configure an offline model via `oar config`.[/dim]"
        )
        raise typer.Exit(code=1)

    if format == "json":
        data = {
            "answer": result.answer,
            "sources_consulted": result.sources_consulted,
            "tool_calls": result.tool_calls,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
        }
        console.print_json(json.dumps(data, indent=2))
    else:
        console.print(
            Panel(
                Markdown(result.answer),
                title="oar query",
                border_style="blue",
            )
        )
        if result.sources_consulted:
            console.print(f"[dim]Sources: {', '.join(result.sources_consulted)}[/dim]")
        console.print(
            f"[dim]Tools: {result.tool_calls} | "
            f"Tokens: {result.tokens_used} | "
            f"Cost: ${result.cost_usd:.4f}[/dim]"
        )

    # Save to vault if requested.
    if save:
        from oar.query.output_filer import OutputFiler

        filer = OutputFiler(vault, ops)
        filed = filer.file_answer(question, result)
        console.print(f"[dim]Saved to {filed.path}[/dim]")
