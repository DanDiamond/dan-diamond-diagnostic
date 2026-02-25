"""Generate an AI summary of a transcript using the Anthropic API."""

from __future__ import annotations

import os

import anthropic


def generate_summary(plain_text: str) -> str:
    """Call Claude to produce a structured summary of the transcript text.

    Requires the ANTHROPIC_API_KEY environment variable to be set.
    Returns an empty string if the API key is missing or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    client = anthropic.Anthropic(api_key=api_key)

    # Trim to ~8 000 chars so we stay well within token limits for long videos
    text_snippet = plain_text[:8000]

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Please provide a structured summary of the following YouTube "
                    "transcript. Format your response in Markdown with these sections:\n\n"
                    "## Overview\n"
                    "2-3 sentences describing what the video is about.\n\n"
                    "## Key Topics\n"
                    "Bullet points of the main subjects covered.\n\n"
                    "## Main Takeaways\n"
                    "Bullet points of the most important points or conclusions.\n\n"
                    f"Transcript:\n{text_snippet}"
                ),
            }
        ],
    )

    return message.content[0].text
