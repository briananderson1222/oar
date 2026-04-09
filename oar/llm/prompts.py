"""Prompt loader — read and render Jinja2 prompt templates from the vault."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class PromptLoader:
    """Load prompt templates from the ``.oar/prompts/`` directory."""

    def __init__(self, prompts_dir: Path) -> None:
        self.prompts_dir = prompts_dir
        self.env = Environment(loader=FileSystemLoader(str(prompts_dir)))

    def load(self, template_name: str, **kwargs) -> str:
        """Load and render a prompt template with the given variables."""
        template = self.env.get_template(template_name)
        return template.render(**kwargs)

    def load_raw(self, template_name: str) -> str:
        """Load a prompt template without rendering."""
        return (self.prompts_dir / template_name).read_text()
