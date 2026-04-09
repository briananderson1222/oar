"""Slug generation — convert text to URL-safe slugs."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str) -> str:
    """Convert *text* to a URL-safe slug.

    Normalises unicode to ASCII, lowercases, replaces non-alphanumeric
    characters with hyphens, and collapses consecutive hyphens.

    Examples::

        >>> slugify("Hello World")
        'hello-world'
        >>> slugify("C++ & Python!")
        'c-python'
        >>> slugify("Transformer Architecture")
        'transformer-architecture'
    """
    # Decompose unicode characters and strip diacritics.
    normalised = unicodedata.normalize("NFKD", text)
    ascii_text = normalised.encode("ascii", "ignore").decode("ascii")
    # Lowercase.
    ascii_text = ascii_text.lower()
    # Replace non-alphanumeric characters with hyphens.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    # Collapse multiple hyphens and strip leading/trailing hyphens.
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug
