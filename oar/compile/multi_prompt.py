"""Multi-article compile prompt — for merging multiple sources into one wiki article."""

MULTI_COMPILE_PROMPT = """\
You are merging multiple source documents about related topics into a single \
comprehensive wiki article.

## Source Documents

{content}

## Instructions

Create ONE comprehensive wiki article that synthesizes all the source material:
1. Starts with a **TL;DR** (1-2 sentences in a blockquote)
2. Has an **Overview** synthesizing all sources
3. Lists **Key Ideas** as bullet points
4. Explains **How It Works** in detail
5. Links to related concepts using [[wikilinks]]
6. Includes a **References** section listing all sources

## Output Format

Respond with ONLY a JSON object (no markdown fences):
- "frontmatter": {{type, domain, tags, related, complexity, confidence}}
- "body": the full markdown article body
"""
