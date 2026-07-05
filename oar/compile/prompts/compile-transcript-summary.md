You are compiling a raw transcript into a structured knowledge note for OAR (Obsidian Agentic RAG).

## Input Document

Title: {{ title }}
Source Type: {{ source_type }}

Transcript:
{{ content }}

{% if extra_context %}
## Additional Context
{{ extra_context }}
{% endif %}

## Goal

Turn the transcript into a categorized, connection-rich research note. OAR's value is synthesis, categorization, and linking, not verbatim reproduction.

## Instructions

Produce a note that:
1. Opens with a concise **Summary**
2. Lists **Key Takeaways**
3. Extracts **Notable Quotes** with speaker attribution when possible
4. Adds **Connections** to related concepts, methods, or entities using [[wikilinks]]
5. Optionally includes a short **Transcript Notes** section if raw transcript details matter

Default compiled type: `{{ default_type }}`

## Output Contract
{{ output_schema }}

Respond with ONLY a JSON object (no markdown fences) with keys:
- "frontmatter"
- "body"
