"""Tests for oar.core.frontmatter — FrontmatterManager."""

from pathlib import Path

from oar.core.frontmatter import FrontmatterManager


class TestFrontmatterRead:
    """Reading frontmatter from files."""

    def test_read_frontmatter_from_valid_file(self, tmp_path):
        fm = FrontmatterManager()
        f = tmp_path / "article.md"
        f.write_text(
            "---\n"
            "id: test-123\n"
            "title: Test Article\n"
            "compiled: false\n"
            "---\n"
            "\n"
            "Body text here.\n"
        )
        meta, body = fm.read(f)
        assert meta["id"] == "test-123"
        assert meta["title"] == "Test Article"
        assert meta["compiled"] is False
        assert "Body text here." in body

    def test_read_frontmatter_from_no_frontmatter_file(self, tmp_path):
        fm = FrontmatterManager()
        f = tmp_path / "plain.md"
        f.write_text("Just plain text.\nNo frontmatter.\n")
        meta, body = fm.read(f)
        assert meta == {}
        assert "Just plain text." in body
        assert "No frontmatter." in body


class TestFrontmatterWrite:
    """Writing frontmatter to files."""

    def test_write_frontmatter_creates_valid_yaml(self, tmp_path):
        fm = FrontmatterManager()
        f = tmp_path / "out.md"
        meta = {"id": "write-test", "title": "Written Article"}
        body = "This is the body."
        fm.write(f, meta, body)

        # Re-read and verify round-trip.
        result_meta, result_body = fm.read(f)
        assert result_meta["id"] == "write-test"
        assert result_meta["title"] == "Written Article"
        assert "This is the body." in result_body


class TestFrontmatterUpdate:
    """Updating frontmatter in-place."""

    def test_update_metadata_preserves_body(self, tmp_path):
        fm = FrontmatterManager()
        f = tmp_path / "update.md"
        f.write_text("---\nid: orig\ntitle: Original\n---\n\nOriginal body.\n")
        fm.update_metadata(f, {"title": "Updated"})
        _, body = fm.read(f)
        assert "Original body." in body

    def test_update_metadata_merges_dicts(self, tmp_path):
        fm = FrontmatterManager()
        f = tmp_path / "merge.md"
        f.write_text("---\nid: orig\ntitle: Original\n---\n\nBody.\n")
        fm.update_metadata(f, {"title": "New Title", "new_key": "new_val"})
        meta, _ = fm.read(f)
        assert meta["id"] == "orig"  # existing key preserved
        assert meta["title"] == "New Title"  # existing key overwritten
        assert meta["new_key"] == "new_val"  # new key added


class TestFrontmatterValidateRaw:
    """Validation of raw article metadata."""

    def test_validate_raw_valid(self):
        fm = FrontmatterManager()
        meta = {
            "id": "test-1",
            "title": "Valid Article",
            "source_type": "article",
            "compiled": False,
            "word_count": 100,
        }
        errors = fm.validate_raw(meta)
        assert errors == []

    def test_validate_raw_missing_id(self):
        fm = FrontmatterManager()
        meta = {"title": "No ID", "source_type": "article"}
        errors = fm.validate_raw(meta)
        assert any("id" in e for e in errors)

    def test_validate_raw_missing_title(self):
        fm = FrontmatterManager()
        meta = {"id": "has-id", "source_type": "article"}
        errors = fm.validate_raw(meta)
        assert any("title" in e for e in errors)


class TestFrontmatterValidateCompiled:
    """Validation of compiled article metadata."""

    def test_validate_compiled_valid(self):
        fm = FrontmatterManager()
        meta = {
            "id": "concept-1",
            "title": "Valid Compiled",
            "type": "concept",
            "status": "draft",
            "confidence": 0.8,
        }
        errors = fm.validate_compiled(meta)
        assert errors == []

    def test_validate_compiled_invalid_type(self):
        fm = FrontmatterManager()
        meta = {
            "id": "bad-type",
            "title": "Bad Type",
            "type": "invalid_type",
            "status": "draft",
        }
        errors = fm.validate_compiled(meta)
        assert any("type" in e for e in errors)

    def test_validate_compiled_invalid_status(self):
        fm = FrontmatterManager()
        meta = {
            "id": "bad-status",
            "title": "Bad Status",
            "type": "concept",
            "status": "unknown",
        }
        errors = fm.validate_compiled(meta)
        assert any("status" in e for e in errors)
