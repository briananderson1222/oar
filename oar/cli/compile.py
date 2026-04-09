"""CLI compile command — compile raw articles into wiki articles via LLM."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oar.cli._shared import find_vault_path, build_router
from oar.compile.compiler import Compiler, CompileResult
from oar.compile.incremental import IncrementalCompiler
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

console = Console()


def _print_results(results: list[CompileResult], cost_tracker: CostTracker) -> None:
    """Display compilation results via Rich."""
    if not results:
        console.print("[yellow]No articles compiled.[/yellow]")
        return

    table = Table(title="Compilation Results", show_header=True)
    table.add_column("Article ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right", style="green")

    for r in results:
        status = "[green]✓[/green]" if r.success else f"[red]✗ {r.error}[/red]"
        table.add_row(
            r.raw_id,
            status,
            str(r.tokens_used),
            f"${r.cost_usd:.4f}",
        )

    console.print(table)
    console.print(
        f"Session cost: [bold green]${cost_tracker.get_session_cost():.4f}[/bold green]"
    )


def compile_cmd(
    article: Optional[str] = typer.Option(
        None, "--article", "-a", help="Specific raw article ID to compile."
    ),
    articles: Optional[str] = typer.Option(
        None,
        "--articles",
        help="Comma-separated list of raw article IDs to merge and compile.",
    ),
    cascade: bool = typer.Option(
        False,
        "--cascade",
        help="After compilation, find related articles that may need recompilation.",
    ),
    all: bool = typer.Option(False, "--all", help="Compile all uncompiled articles."),
    pending: bool = typer.Option(
        False,
        "--pending",
        help="Show articles needing compilation (incremental detection).",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override default LLM model."
    ),
    max_cost: float = typer.Option(
        5.00, "--max-cost", help="Maximum spend in USD for --all."
    ),
) -> None:
    """Compile raw articles into wiki articles using LLM."""
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    router, cost_tracker, config = build_router(vault_path, model)
    vault = Vault(vault_path)
    ops = VaultOps(vault)
    state_mgr = StateManager(vault.oar_dir)
    compiler = Compiler(vault, ops, router, state_mgr)

    # --pending: show what needs incremental compilation.
    if pending:
        ic = IncrementalCompiler(vault, ops, state_mgr, compiler)
        work = ic.detect_pending_work()

        if not work:
            console.print(
                "[green]Nothing to compile — all articles are up to date.[/green]"
            )
            return

        table = Table(title="Pending Compilation", show_header=True)
        table.add_column("Article ID", style="cyan")
        table.add_column("Type", style="bold yellow")
        table.add_column("Path", style="dim")

        for w in work:
            table.add_row(w.article_id, w.work_type, str(w.path.name))

        console.print(table)
        console.print(f"[bold]{len(work)} article(s) pending.[/bold]")
        return

    if articles:
        # Multi-article merge compilation.
        article_ids = [aid.strip() for aid in articles.split(",")]
        try:
            result = compiler.compile_multi(article_ids)
        except Exception as exc:
            console.print(f"[bold red]Compile error:[/bold red] {exc}")
            console.print(
                "[dim]Hint: Set ANTHROPIC_API_KEY or configure an offline model.[/dim]"
            )
            raise typer.Exit(code=1)
        if result.success:
            console.print(
                Panel(
                    f"[bold green]Compiled (merged)[/bold green]\n"
                    f"Sources: {result.raw_id}\n"
                    f"Compiled: {result.compiled_id}\n"
                    f"Path: {result.compiled_path}\n"
                    f"Tokens: {result.tokens_used}\n"
                    f"Cost: ${result.cost_usd:.4f}",
                    title="oar compile --articles",
                    border_style="green",
                )
            )
            if cascade:
                related = compiler.cascade_update(result.compiled_id)
                if related:
                    console.print(
                        f"[yellow]Cascade:[/yellow] {len(related)} article(s) "
                        f"may need recompilation: {', '.join(related)}"
                    )
                else:
                    console.print("[dim]No cascade updates needed.[/dim]")
        else:
            console.print(f"[bold red]Compile failed:[/bold red] {result.error}")
            raise typer.Exit(code=1)

    elif article:
        # Compile a single article by ID.
        try:
            result = compiler.compile_single(article)
        except Exception as exc:
            console.print(f"[bold red]Compile error:[/bold red] {exc}")
            console.print(
                "[dim]Hint: Set ANTHROPIC_API_KEY or configure an offline model.[/dim]"
            )
            raise typer.Exit(code=1)
        if result.success:
            console.print(
                Panel(
                    f"[bold green]Compiled[/bold green]\n"
                    f"Raw: {result.raw_id}\n"
                    f"Compiled: {result.compiled_id}\n"
                    f"Path: {result.compiled_path}\n"
                    f"Tokens: {result.tokens_used}\n"
                    f"Cost: ${result.cost_usd:.4f}",
                    title="oar compile",
                    border_style="green",
                )
            )
            if cascade:
                related = compiler.cascade_update(result.compiled_id)
                if related:
                    console.print(
                        f"[yellow]Cascade:[/yellow] {len(related)} article(s) "
                        f"may need recompilation: {', '.join(related)}"
                    )
                else:
                    console.print("[dim]No cascade updates needed.[/dim]")
        else:
            console.print(f"[bold red]Compile failed:[/bold red] {result.error}")
            raise typer.Exit(code=1)

    elif all:
        # Compile all uncompiled.
        try:
            results = compiler.compile_all(max_cost=max_cost)
        except Exception as exc:
            console.print(f"[bold red]Compile error:[/bold red] {exc}")
            console.print(
                "[dim]Hint: Set ANTHROPIC_API_KEY or configure an offline model.[/dim]"
            )
            raise typer.Exit(code=1)
        if not results:
            console.print(
                "[yellow]No uncompiled articles found. Nothing to do.[/yellow]"
            )
            return
        _print_results(results, cost_tracker)

    else:
        # Default: compile all uncompiled (same as --all with default limit).
        state_mgr = StateManager(vault_path / ".oar")
        uncompiled = state_mgr.get_uncompiled()
        if not uncompiled:
            console.print(
                "[yellow]No uncompiled articles found. Nothing to do.[/yellow]"
            )
            return
        try:
            results = compiler.compile_all(max_cost=max_cost)
        except Exception as exc:
            console.print(f"[bold red]Compile error:[/bold red] {exc}")
            console.print(
                "[dim]Hint: Set ANTHROPIC_API_KEY or configure an offline model.[/dim]"
            )
            raise typer.Exit(code=1)
        _print_results(results, cost_tracker)
