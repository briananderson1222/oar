"""Pydantic data models for OAR article metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RawArticleMeta(BaseModel):
    """Metadata for a raw (uncompiled) source article."""

    id: str
    title: str
    source_url: str = ""
    source_type: str = "file"  # article | paper | repo | file | url
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
