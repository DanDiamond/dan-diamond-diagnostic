"""Generate an AI summary of a transcript using the Anthropic API."""

from __future__ import annotations

import os

import anthropic


def generate_summary(plain_text: str, video_id: str = "", date: str = "") -> str:
    """Call Claude to produce a full markdown document summarising the transcript.

    The returned string includes YAML frontmatter, an H1 title, content-adaptive
    sections, and a Key Takeaways section.  It is intended to be the first block
    of the final markdown file.

    Requires the ANTHROPIC_API_KEY environment variable to be set.
    Returns an empty string if the API key is missing or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    client = anthropic.Anthropic(api_key=api_key)

    source_url = (
        f"https://www.youtube.com/watch?v={video_id}" if video_id else "YouTube"
    )

    prompt = (
        "You are summarising a YouTube video transcript. "
        "Generate a complete, detailed markdown document.\n\n"
        "STRUCTURE REQUIREMENTS\n"
        "======================\n"
        "1. Start with a YAML frontmatter block (---) containing:\n"
        "   - title: (create a descriptive title from the content)\n"
        "   - type: transcript-summary\n"
        "   - topics: (5–10 key topic tags as a YAML list)\n"
        "   - speakers: (identify any speakers/interviewers as a YAML list)\n"
        f"   - source: \"{source_url}\"\n"
        f"   - created: {date}\n"
        "2. An H1 heading matching the frontmatter title.\n"
        "3. ## Overview — 3–5 sentences.\n"
        "4. Content-adaptive sections that follow the video's actual structure:\n"
        "   - Use ## for main sections, ### for sub-sections.\n"
        "   - **Bold** key terms and concepts on first use.\n"
        "   - Capture specific frameworks, models, sequences, and definitions.\n"
        "   - Use bullet lists and numbered steps as appropriate.\n"
        "   - Separate major sections with a --- divider.\n"
        "5. ## Key Takeaways — the most portable, actionable insights.\n\n"
        "Be thorough. Favour depth over brevity. Capture the specific language "
        "and structure of the content rather than generic summaries.\n\n"
        f"Transcript:\n{plain_text}"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
