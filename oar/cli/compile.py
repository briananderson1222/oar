"""CLI compile command — compile raw articles into wiki articles via LLM."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oar.cli._shared import build_router, emit_vault_banner, resolve_vault
from oar.compile.compiler import Compiler, CompileOptions, CompileResult
from oar.compile.incremental import IncrementalCompiler
from oar.compile.profiles import list_profiles
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.cli._shared import VALID_PROVIDERS

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
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Compile profile to use."
    ),
    prompt_template: Optional[str] = typer.Option(
        None, "--prompt-template", help="Prompt template filename from .oar/prompts or built-in prompts."
    ),
    output_schema: Optional[str] = typer.Option(
        None, "--output-schema", help="Additional output-shape guidance passed into the compile prompt."
    ),
    context_file: Optional[str] = typer.Option(
        None, "--context-file", help="Optional file with extra authoring constraints."
    ),
    describe: bool = typer.Option(
        False, "--describe", help="Show available compile profiles and the active compile configuration."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override default LLM model."
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help=f"LLM provider to force for compile ({', '.join(sorted(VALID_PROVIDERS))}).",
    ),
    max_cost: float = typer.Option(
        5.00, "--max-cost", help="Maximum spend in USD for --all."
    ),
    vault: Optional[str] = typer.Option(
        None, "--vault", help="Vault name (from registry) or path. Overrides auto-detection."
    ),
) -> None:
    """Compile raw articles into wiki articles using LLM."""
    resolved = resolve_vault(vault)
    if resolved is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)
    vault_path, vault_source = resolved
    emit_vault_banner(console, vault_path, vault_source)

    router, cost_tracker, config = build_router(vault_path, model, provider)
    vault = Vault(vault_path)
    ops = VaultOps(vault)
    state_mgr = StateManager(vault.oar_dir)
    compiler = Compiler(vault, ops, router, state_mgr, config=config)
    extra_context = Path(context_file).read_text() if context_file else None
    compile_options = CompileOptions(
        profile=profile,
        prompt_template=prompt_template,
        output_schema=output_schema,
        context_text=extra_context,
    )

    if describe:
        profiles = list_profiles(config)
        table = Table(title="Compile Profiles", show_header=True)
        table.add_column("Profile", style="cyan")
        table.add_column("Default Type", style="green")
        table.add_column("Source Types", style="yellow")
        table.add_column("Prompt", style="magenta")
        table.add_column("Description", style="white")
        for name, meta in profiles.items():
            table.add_row(
                name,
                str(meta.get("default_type", "")),
                ", ".join(meta.get("source_types", [])),
                str(meta.get("prompt_template", "")),
                str(meta.get("description", "")),
            )
        console.print(table)
        active_profile = profile or config.compile.profile
        active_meta = profiles.get(active_profile, profiles["default"])
        console.print(
            f"[bold]Active profile:[/bold] {active_profile}\n"
            f"[bold]Prompt template:[/bold] {prompt_template or config.compile.prompt_template or active_meta.get('prompt_template')}\n"
            f"[bold]Output schema:[/bold] {output_schema or config.compile.output_schema or active_meta.get('output_schema')}"
        )
        return

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
            result = compiler.compile_single(article, options=compile_options)
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
            results = compiler.compile_all(max_cost=max_cost, options=compile_options)
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
            results = compiler.compile_all(max_cost=max_cost, options=compile_options)
        except Exception as exc:
            console.print(f"[bold red]Compile error:[/bold red] {exc}")
            console.print(
                "[dim]Hint: Set ANTHROPIC_API_KEY or configure an offline model.[/dim]"
            )
            raise typer.Exit(code=1)
        _print_results(results, cost_tracker)
