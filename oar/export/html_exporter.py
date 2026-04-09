"""HTML static site exporter — convert compiled wiki articles to browsable HTML."""

from __future__ import annotations

import re
from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — OAR Wiki</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; background: #1a1a2e; color: #e0e0e0; }}
        a {{ color: #64b5f6; }}
        code {{ background: #2a2a4a; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #2a2a4a; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
        blockquote {{ border-left: 3px solid #64b5f6; margin-left: 0; padding-left: 1rem; color: #aaa; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #444; padding: 8px; text-align: left; }}
        th {{ background: #2a2a4a; }}
        .nav {{ margin-bottom: 2rem; padding: 1rem; background: #2a2a4a; border-radius: 6px; }}
        .nav a {{ margin-right: 1rem; }}
        .meta {{ color: #888; font-size: 0.9em; margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <div class="nav">
        <a href="index.html">Home</a>
        <a href="mocs.html">Maps of Content</a>
    </div>
    <div class="meta">{meta}</div>
    {body}
</body>
</html>"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OAR Wiki — Index</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; background: #1a1a2e; color: #e0e0e0; }}
        a {{ color: #64b5f6; }}
        .nav {{ margin-bottom: 2rem; padding: 1rem; background: #2a2a4a; border-radius: 6px; }}
        .nav a {{ margin-right: 1rem; }}
        h1 {{ color: #fff; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ padding: 0.5rem 0; border-bottom: 1px solid #333; }}
    </style>
</head>
<body>
    <div class="nav">
        <a href="index.html">Home</a>
        <a href="mocs.html">Maps of Content</a>
    </div>
    <h1>OAR Wiki</h1>
    <ul>
        {links}
    </ul>
</body>
</html>"""


class HTMLExporter:
    """Export wiki as static HTML site."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops

    def export(self, output_dir: Path, include_mocs: bool = True) -> int:
        """Export entire wiki as static HTML. Returns count of exported pages."""
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0

        # Export compiled articles.
        for article_path in self.ops.list_compiled_articles():
            fm, body = self.ops.read_article(article_path)
            title = fm.get("title", article_path.stem)
            html_body = self._markdown_to_html(body)
            tags = fm.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            meta = (
                f"Type: {fm.get('type', '?')} | "
                f"Tags: {', '.join(tags)} | "
                f"Status: {fm.get('status', '?')}"
            )

            html = HTML_TEMPLATE.format(title=title, body=html_body, meta=meta)

            # Preserve subdirectory structure relative to 02-compiled.
            rel_dir = article_path.parent.relative_to(self.vault.compiled_dir)
            out_path = output_dir / rel_dir / f"{article_path.stem}.html"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html)
            count += 1

        # Export index page.
        self._export_index(output_dir)

        # Export MOCs if requested.
        if include_mocs:
            self._export_mocs(output_dir)

        return count

    def _markdown_to_html(self, md: str) -> str:
        """Convert basic markdown to HTML (no external deps)."""
        html = md
        # Code blocks (must be processed before other rules).
        html = re.sub(
            r"```(\w*)\n(.*?)```",
            r"<pre><code>\2</code></pre>",
            html,
            flags=re.DOTALL,
        )
        # Headers.
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        # Bold/italic.
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

        # Wikilinks [[target]] or [[target|display]].
        def _wikilink_repl(m: re.Match) -> str:
            target = m.group(1)
            display = m.group(2) if m.group(2) else target
            return f'<a href="{target}.html">{display}</a>'

        html = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _wikilink_repl, html)
        # Blockquotes.
        html = re.sub(
            r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE
        )
        # Unordered list items.
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        # Wrap loose text lines in paragraphs.
        lines = html.split("\n")
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("<")
                and not stripped.startswith("-")
            ):
                result.append(f"<p>{stripped}</p>")
            else:
                result.append(line)
        return "\n".join(result)

    def _export_index(self, output_dir: Path) -> None:
        """Create index.html with article listing."""
        links: list[str] = []
        for article_path in self.ops.list_compiled_articles():
            fm, _ = self.ops.read_article(article_path)
            title = fm.get("title", article_path.stem)
            rel_dir = article_path.parent.relative_to(self.vault.compiled_dir)
            href = f"{rel_dir}/{article_path.stem}.html"
            links.append(f'<li><a href="{href}">{title}</a></li>')

        html = INDEX_TEMPLATE.format(links="\n        ".join(links))
        (output_dir / "index.html").write_text(html)

    def _export_mocs(self, output_dir: Path) -> None:
        """Export MOC pages as a single mocs.html listing."""
        moc_dir = self.vault.indices_dir / "moc"
        moc_links: list[str] = []
        if moc_dir.is_dir():
            for moc_path in sorted(moc_dir.iterdir()):
                if (
                    moc_path.is_file()
                    and moc_path.suffix == ".md"
                    and moc_path.name != "_index.md"
                    and moc_path.name.startswith("moc-")
                ):
                    fm, _ = self.ops.read_article(moc_path)
                    title = fm.get("title", moc_path.stem)
                    moc_links.append(f"<li>{title}</li>")

        html = HTML_TEMPLATE.format(
            title="Maps of Content",
            body=f"<h1>Maps of Content</h1><ul>{''.join(moc_links)}</ul>",
            meta="",
        )
        (output_dir / "mocs.html").write_text(html)
