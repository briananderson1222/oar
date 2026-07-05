You are compiling meeting or conversational source material into a structured brief for OAR.

## Input Document

Title: {{ title }}
Source Type: {{ source_type }}

Meeting Content:
{{ content }}

{% if extra_context %}
## Additional Context
{{ extra_context }}
{% endif %}

## Instructions

Create a decision-oriented brief with:
1. **Summary**
2. **Decisions**
3. **Action Items**
4. **Risks**
5. **Follow-ups**
6. **References**

Default compiled type: `{{ default_type }}`

## Output Contract
{{ output_schema }}

Respond with ONLY a JSON object (no markdown fences) with keys:
- "frontmatter"
- "body"
