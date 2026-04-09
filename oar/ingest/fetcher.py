"""URL fetching — download and extract readable content from web pages."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


class IngestError(Exception):
    """Raised when a fetch or import operation fails."""


@dataclass
class FetchResult:
    title: str
    content: str  # Markdown-converted content
    url: str
    author: str = ""
    published_date: str = ""
    word_count: int = 0
    language: str = "en"


class URLFetcher:
    """Fetch a URL and extract readable content as plain text."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch(self, url: str) -> FetchResult:
        """Fetch URL and extract readable content as markdown."""
        try:
            response = self.client.get(url)
        except httpx.TimeoutException as exc:
            raise IngestError(f"Timeout fetching {url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise IngestError(f"HTTP error fetching {url}: {exc}") from exc

        if response.status_code >= 400:
            raise IngestError(f"HTTP {response.status_code} fetching {url}")

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Extract title: prefer <title>, fall back to <h1>.
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        if not title:
            title = url

        # Extract author from <meta name="author">.
        author = ""
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()

        # Extract published date from common meta tags.
        published_date = ""
        for attr_name in ("property", "name"):
            for attr_val in (
                "article:published_time",
                "datePublished",
                "date",
            ):
                tag = soup.find("meta", attrs={attr_name: attr_val})
                if tag and tag.get("content"):
                    published_date = tag["content"].strip()
                    break
            if published_date:
                break

        # Extract body content: prefer <article>, then <main>, then <body>.
        content_container = soup.find("article")
        if content_container is None:
            content_container = soup.find("main")
        if content_container is None:
            content_container = soup.find("body")
        if content_container is None:
            content_container = soup

        # Strip HTML tags and normalize whitespace.
        text = content_container.get_text(separator="\n")
        # Collapse excessive blank lines.
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        word_count = len(text.split()) if text else 0

        return FetchResult(
            title=title,
            content=text,
            url=url,
            author=author,
            published_date=published_date,
            word_count=word_count,
        )
