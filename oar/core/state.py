"""State management — persistence layer for vault metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class StateManager:
    """Reads and writes the ``.oar/state.json`` manifest."""

    def __init__(self, oar_dir: Path) -> None:
        self.state_path = oar_dir / "state.json"

    # ------------------------------------------------------------------
    # Core I/O
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """Load state from JSON.

        Returns a minimal empty state when the file is missing or cannot be
        parsed.
        """
        if not self.state_path.exists():
            return self._empty_state()
        try:
            return json.loads(self.state_path.read_text())
        except (json.JSONDecodeError, OSError):
            return self._empty_state()

    def save(self, state: dict) -> None:
        """Persist *state* to disk with pretty JSON formatting."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2) + "\n")

    # ------------------------------------------------------------------
    # Domain operations
    # ------------------------------------------------------------------

    def register_article(self, article_id: str, path: str, content_hash: str) -> None:
        """Add a new article to the state manifest."""
        state = self.load()
        state.setdefault("articles", {})[article_id] = {
            "path": path,
            "content_hash": content_hash,
            "compiled": False,
            "compiled_into": [],
            "last_compiled": None,
        }
        # Update the raw count.
        state.setdefault("stats", {})["raw_articles"] = len(
            [a for a in state["articles"].values() if not a.get("compiled")]
        )
        self.save(state)

    def mark_compiled(self, article_id: str, compiled_ids: list[str]) -> None:
        """Mark *article_id* as compiled, linking to the compiled note IDs."""
        state = self.load()
        article = state.get("articles", {}).get(article_id)
        if article is None:
            return
        article["compiled"] = True
        article["compiled_into"] = list(compiled_ids)
        article["last_compiled"] = datetime.now(timezone.utc).isoformat()
        state["last_compile"] = datetime.now(timezone.utc).isoformat()
        # Recalculate stats.
        articles = state.get("articles", {})
        state.setdefault("stats", {})
        state["stats"]["raw_articles"] = len(
            [a for a in articles.values() if not a.get("compiled")]
        )
        state["stats"]["compiled_articles"] = len(
            [a for a in articles.values() if a.get("compiled")]
        )
        self.save(state)

    def get_uncompiled(self) -> list[str]:
        """Return article IDs that have not yet been compiled."""
        state = self.load()
        return [
            aid
            for aid, meta in state.get("articles", {}).items()
            if not meta.get("compiled", False)
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_state() -> dict:
        return {
            "version": "0.1.0",
            "vault_path": "",
            "last_compile": None,
            "last_lint": None,
            "stats": {
                "raw_articles": 0,
                "compiled_articles": 0,
                "total_words": 0,
            },
            "articles": {},
        }
