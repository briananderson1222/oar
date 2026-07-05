You are compiling a raw document into a structured wiki article for a personal knowledge base called OAR (Obsidian Agentic RAG).

## Input Document

Title: {{ title }}
Source Type: {{ source_type }}

Content:
{{ content }}

{% if extra_context %}
## Additional Context
{{ extra_context }}
{% endif %}

## Instructions

Create a comprehensive wiki article that:
1. Starts with a **TL;DR** (1-2 sentences in a blockquote)
2. Has an **Overview** section (2-3 paragraphs)
3. Lists **Key Ideas** as bullet points
4. Explains **How It Works** with clear steps or components
5. Links to related concepts using [[wikilinks]] format
6. Includes a **References** section linking back to sources

Default compiled type: `{{ default_type }}`

## Output Contract
{{ output_schema }}

Respond with ONLY a JSON object (no markdown fences) with keys:
- "frontmatter"
- "body"
