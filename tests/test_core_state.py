"""Tests for oar.core.state — StateManager."""

import json
from pathlib import Path

from oar.core.state import StateManager


class TestStateManagerInit:
    """Loading empty / missing state."""

    def test_state_init_creates_empty_state(self, tmp_path):
        mgr = StateManager(tmp_path / ".oar")
        state = mgr.load()
        assert state["version"] == "0.1.0"
        assert state["stats"]["raw_articles"] == 0
        assert state["articles"] == {}


class TestStateManagerRegister:
    """register_article behaviour."""

    def test_state_register_article(self, tmp_path):
        mgr = StateManager(tmp_path / ".oar")
        mgr.register_article("art-1", "01-raw/articles/art-1.md", "sha256:aaa")
        state = mgr.load()
        assert "art-1" in state["articles"]
        assert state["articles"]["art-1"]["compiled"] is False
        assert state["stats"]["raw_articles"] == 1


class TestStateManagerCompile:
    """mark_compiled behaviour."""

    def test_state_mark_compiled(self, tmp_path):
        mgr = StateManager(tmp_path / ".oar")
        mgr.register_article("art-1", "01-raw/articles/art-1.md", "sha256:aaa")
        mgr.mark_compiled("art-1", ["concept-transformer"])
        state = mgr.load()
        assert state["articles"]["art-1"]["compiled"] is True
        assert state["articles"]["art-1"]["compiled_into"] == ["concept-transformer"]
        assert state["stats"]["raw_articles"] == 0
        assert state["stats"]["compiled_articles"] == 1

    def test_state_mark_compiled_updates_last_compile(self, tmp_path):
        mgr = StateManager(tmp_path / ".oar")
        mgr.register_article("art-1", "01-raw/articles/art-1.md", "sha256:aaa")
        mgr.mark_compiled("art-1", ["concept-x"])
        state = mgr.load()
        assert state["last_compile"] is not None
        assert state["articles"]["art-1"]["last_compiled"] is not None


class TestStateManagerUncompiled:
    """get_uncompiled behaviour."""

    def test_state_get_uncompiled(self, tmp_path):
        mgr = StateManager(tmp_path / ".oar")
        mgr.register_article("art-1", "01-raw/articles/art-1.md", "sha256:aaa")
        mgr.register_article("art-2", "01-raw/articles/art-2.md", "sha256:bbb")
        assert mgr.get_uncompiled() == ["art-1", "art-2"]

        mgr.mark_compiled("art-1", ["concept-x"])
        assert mgr.get_uncompiled() == ["art-2"]


class TestStateManagerPersistence:
    """State is actually written to disk."""

    def test_state_persists_to_disk(self, tmp_path):
        oar_dir = tmp_path / ".oar"
        mgr = StateManager(oar_dir)
        mgr.register_article("art-1", "01-raw/articles/art-1.md", "sha256:aaa")

        # Verify the file on disk contains the right data.
        state_file = oar_dir / "state.json"
        assert state_file.exists()
        disk_state = json.loads(state_file.read_text())
        assert "art-1" in disk_state["articles"]
