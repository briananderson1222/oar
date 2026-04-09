"""Metadata generation — build raw article frontmatter dicts."""

from __future__ import annotations

from datetime import datetime, timezone

from oar.core.slug import slugify


def generate_raw_metadata(
    title: str,
    source_url: str = "",
    source_type: str = "file",
    author: str = "",
    published: str = "",
    content: str = "",
) -> dict:
    """Generate complete raw article frontmatter dict.

    Returns dict with all fields per RawArticleMeta schema:
    id, title, source_url, source_type, author, published, clipped,
    compiled (False), compiled_into ([]), word_count, language
    """
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y-%m-%d")
    slug = slugify(title)
    article_id = f"{date_prefix}-{slug}"

    word_count = len(content.split()) if content.strip() else 0

    return {
        "id": article_id,
        "title": title,
        "source_url": source_url,
        "source_type": source_type,
        "author": author,
        "published": published,
        "clipped": now.isoformat(),
        "compiled": False,
        "compiled_into": [],
        "word_count": word_count,
        "language": "en",
    }
