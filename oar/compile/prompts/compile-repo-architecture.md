You are compiling repository source material into an architecture brief for OAR.

## Input Document

Title: {{ title }}
Source Type: {{ source_type }}

Repository Material:
{{ content }}

{% if extra_context %}
## Additional Context
{{ extra_context }}
{% endif %}

## Instructions

Create a technical brief with:
1. **Overview**
2. **Key Components**
3. **Architecture**
4. **Interfaces**
5. **Open Questions**
6. **References**

Default compiled type: `{{ default_type }}`

## Output Contract
{{ output_schema }}

Respond with ONLY a JSON object (no markdown fences) with keys:
- "frontmatter"
- "body"
