"""Incremental compiler — detect changes and perform diff-based updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from oar.compile.compiler import Compiler, CompileResult
from oar.core.hashing import content_hash, has_content_changed
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


@dataclass
class PendingWork:
    """Represents an article that needs processing."""

    article_id: str
    path: Path
    work_type: str  # "NEW", "UPDATED", "UNCOMPILED", "REFRESH"
    previous_hash: str = ""


class IncrementalCompiler:
    """Detect and perform incremental compilation updates."""

    def __init__(
        self,
        vault: Vault,
        ops: VaultOps,
        state: StateManager,
        compiler: Compiler,
    ) -> None:
        self.vault = vault
        self.ops = ops
        self.state = state
        self.compiler = compiler

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_pending_work(self) -> list[PendingWork]:
        """Scan vault for articles needing compilation.

        Checks:
        1. Raw articles not in state → NEW
        2. Raw articles with changed content hash → UPDATED
        3. Raw articles with compiled=False → UNCOMPILED
        """
        state = self.state.load()
        pending: list[PendingWork] = []

        for raw_path in self.ops.list_raw_articles():
            fm, _ = self.ops.read_article(raw_path)
            article_id: str = fm.get("id", raw_path.stem)
            current_hash = content_hash(raw_path)

            if article_id not in state.get("articles", {}):
                pending.append(PendingWork(article_id, raw_path, "NEW"))
            else:
                entry = state["articles"][article_id]
                if has_content_changed(raw_path, entry.get("content_hash", "")):
                    pending.append(
                        PendingWork(
                            article_id,
                            raw_path,
                            "UPDATED",
                            entry.get("content_hash", ""),
                        )
                    )
                elif not entry.get("compiled", False):
                    pending.append(PendingWork(article_id, raw_path, "UNCOMPILED"))

        return pending

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    def compile_pending(self, max_cost: float = 5.00) -> list[CompileResult]:
        """Compile all pending articles respecting budget.

        For each pending article:
        1. If NEW/UNCOMPILED → full compile
        2. If UPDATED → recompile (existing article overwritten)
        3. Check budget before each compile
        """
        pending = self.detect_pending_work()
        results: list[CompileResult] = []
        session_cost = 0.0

        for work in pending:
            # Check budget before each call.
            if session_cost >= max_cost:
                break

            result = self.compiler.compile_article(work.path)
            results.append(result)
            session_cost += result.cost_usd

        return results

    def update_changed_article(self, article_id: str) -> CompileResult:
        """Recompile a specific article whose source has changed.

        1. Read current compiled article (if exists)
        2. Read updated raw source
        3. Compile with context of existing article
        4. Write updated compiled article (increment version)
        """
        return self.compiler.compile_single(article_id)

    def cascade_recompile(
        self,
        compiled_id: str,
        max_depth: int = 2,
        max_cost: float = 2.00,
    ) -> list[str]:
        """Find and recompile articles affected by a change to compiled_id.

        Uses Compiler.cascade_update to find dependents, then
        recompiles them if their sources are still valid.

        Returns list of recompiled article IDs.
        """
        dependents = self.compiler.cascade_update(compiled_id)
        recompiled: list[str] = []
        session_cost = 0.0

        for dep_id in dependents:
            if session_cost >= max_cost:
                break

            result = self.compiler.compile_single(dep_id)
            session_cost += result.cost_usd

            if result.success:
                recompiled.append(dep_id)

        return recompiled
