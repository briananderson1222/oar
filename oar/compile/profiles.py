"""Built-in compile profiles and helpers."""

from __future__ import annotations

from dataclasses import dataclass

from oar.core.config import OarConfig


@dataclass(frozen=True)
class CompileProfile:
    name: str
    description: str
    prompt_template: str
    output_schema: str
    default_type: str
    source_types: tuple[str, ...]
    context_strategy: str = "default"
    max_context_chars: int = 32000


BUILTIN_COMPILE_PROFILES: dict[str, CompileProfile] = {
    "default": CompileProfile(
        name="default",
        description="Generic knowledge article compilation with reusable wiki structure.",
        prompt_template="compile-default.md",
        output_schema=(
            "Return JSON with frontmatter and body. Body should include TL;DR, Overview, "
            "Key Ideas, How It Works, and References when relevant."
        ),
        default_type="concept",
        source_types=("article", "file", "url"),
        context_strategy="default",
        max_context_chars=32000,
    ),
    "transcript-summary": CompileProfile(
        name="transcript-summary",
        description="Turn a raw transcript into a categorized research summary with quotes and connections.",
        prompt_template="compile-transcript-summary.md",
        output_schema=(
            "Return JSON with frontmatter and body. Body should include Summary, Key Takeaways, "
            "Notable Quotes, Connections, and an optional Transcript Notes section."
        ),
        default_type="summary",
        source_types=("transcript", "video"),
        context_strategy="transcript_excerpt",
        max_context_chars=24000,
    ),
    "paper-summary": CompileProfile(
        name="paper-summary",
        description="Summarize a paper into a concise research-oriented note.",
        prompt_template="compile-paper-summary.md",
        output_schema=(
            "Return JSON with frontmatter and body. Body should include TL;DR, Problem, "
            "Approach, Findings, Limitations, and References."
        ),
        default_type="summary",
        source_types=("paper",),
        context_strategy="default",
        max_context_chars=32000,
    ),
    "repo-architecture": CompileProfile(
        name="repo-architecture",
        description="Compile repository source material into an architecture-oriented brief.",
        prompt_template="compile-repo-architecture.md",
        output_schema=(
            "Return JSON with frontmatter and body. Body should include Overview, Key Components, "
            "Architecture, Interfaces, and Open Questions."
        ),
        default_type="brief",
        source_types=("repo",),
        context_strategy="default",
        max_context_chars=32000,
    ),
    "meeting-brief": CompileProfile(
        name="meeting-brief",
        description="Condense meeting or conversational source material into a structured brief.",
        prompt_template="compile-meeting-brief.md",
        output_schema=(
            "Return JSON with frontmatter and body. Body should include Summary, Decisions, "
            "Action Items, Risks, and Follow-ups."
        ),
        default_type="brief",
        source_types=("meeting",),
        context_strategy="default",
        max_context_chars=20000,
    ),
}


def list_profiles(config: OarConfig | None = None) -> dict[str, dict]:
    """Return merged built-in and config-defined profile metadata."""
    profiles: dict[str, dict] = {
        name: {
            "name": profile.name,
            "description": profile.description,
            "prompt_template": profile.prompt_template,
            "output_schema": profile.output_schema,
                "default_type": profile.default_type,
                "source_types": list(profile.source_types),
                "context_strategy": profile.context_strategy,
                "max_context_chars": profile.max_context_chars,
                "builtin": True,
            }
        for name, profile in BUILTIN_COMPILE_PROFILES.items()
    }
    if config:
        for name, meta in config.compile.profiles.items():
            profiles[name] = {
                "name": name,
                "description": meta.get("description", ""),
                "prompt_template": meta.get("prompt_template"),
                "output_schema": meta.get("output_schema"),
                "default_type": meta.get("default_type", config.compile.default_type),
                "source_types": meta.get("source_types", []),
                "context_strategy": meta.get("context_strategy", "default"),
                "max_context_chars": meta.get("max_context_chars", 32000),
                "builtin": False,
            }
    return profiles
