"""Format a Transcript into various output styles."""

from __future__ import annotations

import datetime

from .summarizer import generate_summary
from .transcript import Transcript


def format_plain(transcript: Transcript) -> str:
    """Continuous text without timestamps."""
    return transcript.plain_text


def format_timestamped(transcript: Transcript) -> str:
    """Each segment on its own line, prefixed with [MM:SS]."""
    return transcript.timestamped_text


def format_markdown(transcript: Transcript) -> str:
    """Markdown document: AI-generated frontmatter + summary, then full transcript."""
    today = datetime.date.today().isoformat()
    summary = generate_summary(transcript.plain_text, transcript.video_id, today)

    full_transcript_section = (
        "\n\n---\n\n"
        "## Full Transcript\n\n"
        f"*Language: {transcript.language} — {transcript.word_count:,} words*\n\n"
        + transcript.plain_text
    )

    if summary:
        return summary + full_transcript_section

    # Fallback when no API key is available
    header = (
        f"# YouTube Transcript\n\n"
        f"**Video ID:** `{transcript.video_id}`  \n"
        f"**Language:** {transcript.language}  \n"
        f"**Words:** {transcript.word_count:,}\n\n"
        f"---\n\n"
    )
    return header + full_transcript_section


def format_srt(transcript: Transcript) -> str:
    """SubRip (.srt) format."""
    lines = []
    for i, seg in enumerate(transcript.segments, start=1):
        start_ts = _ms_to_srt(seg.start)
        end_ts = _ms_to_srt(seg.start + seg.duration)
        lines.append(f"{i}\n{start_ts} --> {end_ts}\n{seg.text.strip()}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ms_to_srt(seconds: float) -> str:
    """Convert fractional seconds to SRT timestamp HH:MM:SS,mmm."""
    ms = int(round(seconds * 1000))
    h, remainder = divmod(ms, 3_600_000)
    m, remainder = divmod(remainder, 60_000)
    s, ms = divmod(remainder, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
