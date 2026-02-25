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

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    "Please provide a thorough, structured summary of the following YouTube "
                    "transcript. Format your response in Markdown with these sections:\n\n"
                    "## Overview\n"
                    "3-5 sentences describing what the video is about and its purpose.\n\n"
                    "## Key Topics\n"
                    "Detailed bullet points of the main subjects covered, with a brief explanation of each.\n\n"
                    "## Main Takeaways\n"
                    "Detailed bullet points of the most important points or conclusions.\n\n"
                    "## Action Items\n"
                    "Bullet points of any specific recommendations, steps, or things the viewer should do.\n\n"
                    "## Notable Quotes\n"
                    "2-4 direct quotes that best capture the key ideas.\n\n"
                    f"Transcript:\n{plain_text}"
                ),
            }
        ],
    )

    return message.content[0].text
