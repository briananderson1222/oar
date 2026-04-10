"""oar build — One-command pipeline: compile → index → lint."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oar.cli._shared import find_vault_path, build_router
from oar.compile.compiler import Compiler
from oar.core.hashing import content_hash
from oar.core.slug import slugify
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.core.link_resolver import LinkResolver
from oar.index.moc_builder import MocBuilder
from oar.index.orphan_tracker import OrphanTracker
from oar.index.tag_builder import TagBuilder
from oar.lint.structural import StructuralChecker

console = Console()


def build_cmd(
    max_cost: float = typer.Option(
        5.00, "--max-cost", help="Maximum spend in USD for compilation."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override default LLM model."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without doing it."
    ),
    skip_lint: bool = typer.Option(False, "--skip-lint", help="Skip the lint step."),
    skip_compile: bool = typer.Option(
        False, "--skip-compile", help="Skip compilation (index + lint only)."
    ),
) -> None:
    """Build the vault: compile raw → generate indices → lint check."""
    # --- Resolve vault ------------------------------------------------
    vault_path = find_vault_path()
    if vault_path is None:
        console.print(
            "[bold red]Error:[/bold red] No OAR vault found. Run `oar init` first."
        )
        raise typer.Exit(code=1)

    vault = Vault(vault_path)
    ops = VaultOps(vault)
    state_mgr = StateManager(vault.oar_dir)

    # --- Auto-discover unregistered raw articles -----------------------
    state = state_mgr.load()
    registered = set(state.get("articles", {}).keys())
    newly_registered = 0

    for raw_path in ops.list_raw_articles():
        fm, _ = ops.read_article(raw_path)
        # Prefer frontmatter id, then slugify the title, then slugify the stem.
        article_id = fm.get("id") or slugify(fm.get("title", raw_path.stem))
        if article_id not in registered:
            h = content_hash(raw_path)
            rel = str(raw_path.relative_to(vault_path))
            state_mgr.register_article(article_id, rel, h)
            newly_registered += 1

    if newly_registered:
        console.print(
            f"[dim]Auto-registered {newly_registered} new article(s) from 01-raw/[/dim]"
        )

    uncompiled = state_mgr.get_uncompiled()

    # --- Dry-run mode --------------------------------------------------
    if dry_run:
        console.rule("[bold]oar build --dry-run[/bold]")
        if uncompiled:
            table = Table(title="Pending Articles", show_header=True)
            table.add_column("Article ID", style="cyan")
            table.add_column("Status", style="yellow")
            for aid in uncompiled:
                table.add_row(aid, "pending")
            console.print(table)
            console.print(
                f"\n[bold]{len(uncompiled)} article(s) would be compiled.[/bold]"
            )
        else:
            console.print("[green]No uncompiled articles.[/green]")
        console.print(
            "\nWould run: [cyan]compile[/cyan] → [cyan]index[/cyan] → [cyan]lint[/cyan]"
        )
        return

    # Counters for final summary.
    compiled_count = 0
    moc_count = 0
    tag_count = 0
    total_cost = 0.0
    lint_passed = True

    # --- Step 1/3: Compile ---------------------------------------------
    console.rule("[bold]Step 1/3: Compile[/bold]")

    if skip_compile or not uncompiled:
        if not uncompiled:
            console.print("[yellow]Nothing to compile.[/yellow]")
        elif skip_compile:
            console.print("[dim]Skipped (--skip-compile).[/dim]")
    else:
        try:
            router, cost_tracker, config = build_router(vault_path, model)
            compiler = Compiler(vault, ops, router, state_mgr)
            results = compiler.compile_all(max_cost=max_cost)

            if results:
                table = Table(title="Compilation Results", show_header=True)
                table.add_column("Article ID", style="cyan")
                table.add_column("Status", style="bold")
                table.add_column("Tokens", justify="right")
                table.add_column("Cost", justify="right", style="green")

                for r in results:
                    if r.success:
                        status = "[green]✓[/green]"
                        compiled_count += 1
                    else:
                        status = f"[red]✗ {r.error}[/red]"
                    table.add_row(
                        r.raw_id,
                        status,
                        str(r.tokens_used),
                        f"${r.cost_usd:.4f}",
                    )

                console.print(table)
                total_cost += cost_tracker.get_session_cost()
                console.print(
                    f"Session cost: [bold green]${cost_tracker.get_session_cost():.4f}[/bold green]"
                )
            else:
                console.print("[yellow]No articles compiled.[/yellow]")
        except Exception as exc:
            console.print(f"[bold red]Compile error:[/bold red] {exc}")
            console.print("[dim]Continuing to index and lint steps…[/dim]")

    # --- Step 2/3: Index -----------------------------------------------
    console.rule("[bold]Step 2/3: Index[/bold]")

    try:
        moc_builder = MocBuilder(vault, ops)
        tag_builder = TagBuilder(vault, ops)
        resolver = LinkResolver(vault, ops)
        orphan_tracker = OrphanTracker(vault, ops, resolver)

        mocs = moc_builder.auto_generate_mocs()
        moc_data = moc_builder.list_mocs()
        moc_builder.build_master_index(moc_data)
        moc_count = len(mocs)

        tags = tag_builder.auto_generate_tags()
        tag_count = len(tags)

        orphans = orphan_tracker.write_orphans_page()
        stubs = orphan_tracker.write_stubs_page()
        orphan_tracker.write_recent_page()

        console.print(
            f"MOCs: {moc_count}  |  Tags: {tag_count}  |  "
            f"Orphans: {len(orphans)}  |  Stubs: {len(stubs)}"
        )
    except Exception as exc:
        console.print(f"[yellow]Index warning:[/yellow] {exc}")

    # --- Step 3/3: Lint ------------------------------------------------
    console.rule("[bold]Step 3/3: Lint[/bold]")

    if skip_lint:
        console.print("[dim]Skipped (--skip-lint).[/dim]")
    else:
        try:
            checker = StructuralChecker(vault, ops)
            issues = checker.check_all()

            errors = sum(1 for i in issues if i.severity == "error")
            warnings = sum(1 for i in issues if i.severity == "warning")
            infos = sum(1 for i in issues if i.severity == "info")

            if errors:
                lint_passed = False
                console.print(
                    f"[red]{errors} error(s)[/red], "
                    f"[yellow]{warnings} warning(s)[/yellow], "
                    f"[blue]{infos} info[/blue]"
                )
            else:
                console.print(
                    f"[green]✓ Passed[/green] — {warnings} warning(s), {infos} info"
                )
        except Exception as exc:
            console.print(f"[yellow]Lint warning:[/yellow] {exc}")

    # --- Final summary -------------------------------------------------
    console.print()
    lint_status = "[green]✓ passed[/green]" if lint_passed else "[red]✗ errors[/red]"
    console.print(
        Panel(
            f"Compiled: {compiled_count}\n"
            f"MOCs: {moc_count}\n"
            f"Tag pages: {tag_count}\n"
            f"Lint: {lint_status}\n"
            f"Cost: ${total_cost:.4f}",
            title="Build Complete",
            border_style="green" if lint_passed else "red",
        )
    )

    if not lint_passed:
        raise typer.Exit(code=1)
