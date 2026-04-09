"""CLI search command — search the compiled wiki via FTS5."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.search.indexer import SearchIndexer
from oar.search.ranker import rank_results
from oar.search.searcher import Searcher

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


def search_cmd(
    query: str = typer.Argument(None, help="Search query"),
    type: str = typer.Option(None, "--type", help="Filter by article type"),
    domain: str = typer.Option(None, "--domain", help="Filter by domain"),
    limit: int = typer.Option(10, "--limit", help="Max results"),
    format: str = typer.Option("table", "--format", help="Output: table|json|detailed"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Rebuild search index"),
    serve: bool = typer.Option(False, "--serve", help="Start the web search UI"),
    port: int = typer.Option(3232, "--port", help="Port for the web UI"),
) -> None:
    """Search the compiled wiki."""
    vault_path = _find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    if serve:
        from oar.search.server import create_app

        create_app(str(vault_path))
        console.print(
            f"[green]Starting OAR search UI on http://localhost:{port}[/green]"
        )
        uvicorn.run(app="oar.search.server:app", host="0.0.0.0", port=port)
        return

    if query is None:
        console.print("[bold red]Error:[/bold red] Please provide a search query.")
        raise typer.Exit(code=1)

    if rebuild:
        db_path = vault_path / ".oar" / "search-index" / "search.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        vault = Vault(vault_path)
        ops = VaultOps(vault)
        indexer = SearchIndexer(db_path)
        count = indexer.index_vault(vault, ops)
        indexer.close()
        console.print(f"[green]Rebuilt search index with {count} articles.[/green]")

    db_path = _get_or_build_index(vault_path)
    searcher = Searcher(db_path)

    results = searcher.search(
        query,
        limit=limit,
        type_filter=type,
        domain_filter=domain,
    )

    # Apply re-ranking.
    results = rank_results(results, query)

    searcher.close()

    if not results:
        console.print(f"[yellow]No results found for '{query}'.[/yellow]")
        return

    if format == "json":
        data = [
            {
                "article_id": r.article_id,
                "title": r.title,
                "type": r.type,
                "score": round(r.score, 4),
                "snippet": r.snippet,
                "path": r.path,
                "tags": r.tags,
            }
            for r in results
        ]
        console.print_json(json.dumps(data, indent=2))

    elif format == "detailed":
        for r in results:
            console.print(
                Panel(
                    f"[bold]{r.title}[/bold]\n"
                    f"[dim]ID:[/dim] {r.article_id}  [dim]Type:[/dim] {r.type}  "
                    f"[dim]Score:[/dim] {r.score:.2f}\n"
                    f"[dim]Path:[/dim] {r.path}\n"
                    f"[dim]Tags:[/dim] {', '.join(r.tags)}\n\n"
                    f"{r.snippet}",
                    border_style="blue",
                )
            )

    else:
        # Table format (default).
        table = Table(title=f"Search: {query}", show_header=True)
        table.add_column("Title", style="cyan")
        table.add_column("Type", style="bold yellow")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Snippet", style="dim", max_width=50)

        for r in results:
            table.add_row(
                r.title,
                r.type,
                f"{r.score:.2f}",
                r.snippet[:50] + "..." if len(r.snippet) > 50 else r.snippet,
            )

        console.print(table)
        console.print(f"[dim]{len(results)} result(s) found.[/dim]")
