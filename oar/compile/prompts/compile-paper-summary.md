You are compiling a paper into a structured research summary for OAR.

## Input Document

Title: {{ title }}
Source Type: {{ source_type }}

Paper Content:
{{ content }}

{% if extra_context %}
## Additional Context
{{ extra_context }}
{% endif %}

## Instructions

Create a concise research note with:
1. **TL;DR**
2. **Problem**
3. **Approach**
4. **Findings**
5. **Limitations**
6. **References**

Default compiled type: `{{ default_type }}`

## Output Contract
{{ output_schema }}

Respond with ONLY a JSON object (no markdown fences) with keys:
- "frontmatter"
- "body"
