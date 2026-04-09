"""Tests for oar.ingest.metadata — generate_raw_metadata."""

from datetime import datetime, timezone

from oar.ingest.metadata import generate_raw_metadata


class TestGenerateRawMetadata:
    """generate_raw_metadata behaviour."""

    def test_generate_raw_metadata_has_required_fields(self):
        meta = generate_raw_metadata(title="Test Article", content="hello world")
        required = [
            "id",
            "title",
            "source_url",
            "source_type",
            "author",
            "published",
            "clipped",
            "compiled",
            "compiled_into",
            "word_count",
            "language",
        ]
        for field in required:
            assert field in meta, f"Missing field: {field}"

    def test_generate_raw_metadata_generates_id(self):
        meta = generate_raw_metadata(title="My Cool Article")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert meta["id"].startswith(today)
        assert "my-cool-article" in meta["id"]

    def test_generate_raw_metadata_compiled_false(self):
        meta = generate_raw_metadata(title="Test")
        assert meta["compiled"] is False

    def test_generate_raw_metadata_computes_word_count(self):
        content = "one two three four five"
        meta = generate_raw_metadata(title="Test", content=content)
        assert meta["word_count"] == 5

    def test_generate_raw_metadata_has_clipped_timestamp(self):
        meta = generate_raw_metadata(title="Test")
        # Should be a valid ISO 8601 string.
        clipped = meta["clipped"]
        assert clipped  # not empty
        # Parse it — will raise if invalid.
        datetime.fromisoformat(clipped)

    def test_generate_raw_metadata_compiled_into_empty(self):
        meta = generate_raw_metadata(title="Test")
        assert meta["compiled_into"] == []

    def test_generate_raw_metadata_defaults(self):
        meta = generate_raw_metadata(title="Test")
        assert meta["source_url"] == ""
        assert meta["source_type"] == "file"
        assert meta["author"] == ""
        assert meta["published"] == ""
        assert meta["language"] == "en"

    def test_generate_raw_metadata_custom_source_type(self):
        meta = generate_raw_metadata(title="Test", source_type="paper")
        assert meta["source_type"] == "paper"

    def test_generate_raw_metadata_custom_author(self):
        meta = generate_raw_metadata(title="Test", author="Jane Doe")
        assert meta["author"] == "Jane Doe"

    def test_generate_raw_metadata_custom_url(self):
        meta = generate_raw_metadata(
            title="Test", source_url="https://example.com/article"
        )
        assert meta["source_url"] == "https://example.com/article"
