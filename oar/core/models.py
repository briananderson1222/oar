"""Pydantic data models and shared enums for OAR article metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

VALID_RAW_SOURCE_TYPES = (
    "article",
    "paper",
    "repo",
    "file",
    "url",
    "transcript",
    "video",
    "meeting",
)

COMPILED_TYPE_TO_DIR = {
    "concept": "concepts",
    "entity": "entities",
    "method": "methods",
    "comparison": "comparisons",
    "tutorial": "tutorials",
    "timeline": "timelines",
    "summary": "summaries",
    "brief": "briefs",
    "note": "notes",
}

VALID_COMPILED_TYPES = tuple(COMPILED_TYPE_TO_DIR.keys())


def compiled_subdir_for(article_type: str) -> str:
    """Return the compiled subdirectory for a compiled article type."""
    return COMPILED_TYPE_TO_DIR.get(article_type, "concepts")


class RawArticleMeta(BaseModel):
    """Metadata for a raw (uncompiled) source article."""

    id: str
    title: str
    source_url: str = ""
    source_type: str = "file"
    author: str = ""
    published: str = ""
    clipped: str = ""
    compiled: bool = False
    compiled_into: list[str] = Field(default_factory=list)
    word_count: int = 0
    language: str = "en"


class CompiledArticleMeta(BaseModel):
    """Metadata for a compiled knowledge note."""

    id: str
    title: str
    aliases: list[str] = Field(default_factory=list)
    created: str = ""
    updated: str = ""
    version: int = 1
    type: str = "concept"
    domain: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)
    source_count: int = 0
    related: list[str] = Field(default_factory=list)
    prerequisite_for: list[str] = Field(default_factory=list)
    see_also: list[str] = Field(default_factory=list)
    word_count: int = 0
    read_time_min: int = 0
    backlink_count: int = 0
    complexity: str = "intermediate"
