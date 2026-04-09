"""Tests for oar.core.hashing — Content hashing utilities."""

from pathlib import Path

from oar.core.hashing import content_hash, content_hash_string, has_content_changed


class TestContentHash:
    """content_hash function."""

    def test_content_hash_deterministic(self, tmp_path):
        f = tmp_path / "stable.txt"
        f.write_text("Deterministic content")
        h1 = content_hash(f)
        h2 = content_hash(f)
        assert h1 == h2

    def test_content_hash_different_for_different_content(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("Content A")
        f2.write_text("Content B")
        assert content_hash(f1) != content_hash(f2)

    def test_content_hash_format(self, tmp_path):
        f = tmp_path / "fmt.txt"
        f.write_text("Check format")
        h = content_hash(f)
        assert h.startswith("sha256:")
        hex_part = h[len("sha256:") :]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)


class TestContentHashString:
    """content_hash_string function."""

    def test_content_hash_string_format(self):
        h = content_hash_string("hello world")
        assert h.startswith("sha256:")
        hex_part = h[len("sha256:") :]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)


class TestHasContentChanged:
    """has_content_changed function."""

    def test_has_content_changed_true(self, tmp_path):
        f = tmp_path / "changed.txt"
        f.write_text("Version 1")
        old_hash = content_hash(f)
        f.write_text("Version 2 — modified!")
        assert has_content_changed(f, old_hash) is True

    def test_has_content_changed_false(self, tmp_path):
        f = tmp_path / "unchanged.txt"
        f.write_text("Same content")
        current_hash = content_hash(f)
        assert has_content_changed(f, current_hash) is False
