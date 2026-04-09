"""Tests for oar.core.models — Pydantic data models."""

from oar.core.models import RawArticleMeta, CompiledArticleMeta


class TestRawArticleMeta:
    """RawArticleMeta model."""

    def test_raw_article_meta_defaults(self):
        meta = RawArticleMeta(id="r1", title="Test")
        assert meta.source_url == ""
        assert meta.source_type == "file"
        assert meta.author == ""
        assert meta.published == ""
        assert meta.clipped == ""
        assert meta.compiled is False
        assert meta.compiled_into == []
        assert meta.word_count == 0
        assert meta.language == "en"

    def test_raw_article_meta_from_dict(self):
        data = {
            "id": "r2",
            "title": "Dict Test",
            "source_type": "paper",
            "word_count": 500,
        }
        meta = RawArticleMeta.model_validate(data)
        assert meta.id == "r2"
        assert meta.source_type == "paper"
        assert meta.word_count == 500

    def test_raw_article_meta_serialization(self):
        original = RawArticleMeta(id="r3", title="Serial Test", word_count=42)
        data = original.model_dump()
        restored = RawArticleMeta.model_validate(data)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.word_count == original.word_count
        assert restored.compiled is False


class TestCompiledArticleMeta:
    """CompiledArticleMeta model."""

    def test_compiled_article_meta_defaults(self):
        meta = CompiledArticleMeta(id="c1", title="Compiled Test")
        assert meta.aliases == []
        assert meta.created == ""
        assert meta.updated == ""
        assert meta.version == 1
        assert meta.type == "concept"
        assert meta.domain == []
        assert meta.tags == []
        assert meta.status == "draft"
        assert meta.confidence == 0.0
        assert meta.sources == []
        assert meta.source_count == 0
        assert meta.related == []
        assert meta.prerequisite_for == []
        assert meta.see_also == []
        assert meta.word_count == 0
        assert meta.read_time_min == 0
        assert meta.backlink_count == 0
        assert meta.complexity == "intermediate"

    def test_compiled_article_meta_serialization(self):
        original = CompiledArticleMeta(
            id="c2",
            title="Serial Compiled",
            type="method",
            status="mature",
            confidence=0.95,
            tags=["test", "serialization"],
        )
        data = original.model_dump()
        restored = CompiledArticleMeta.model_validate(data)
        assert restored.id == original.id
        assert restored.type == "method"
        assert restored.status == "mature"
        assert restored.confidence == 0.95
        assert restored.tags == ["test", "serialization"]
