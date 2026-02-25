"""Main CLI for the YouTube Transcript Bot.

Usage examples:

  # Print a transcript to stdout (default: timestamped format)
  python -m youtube_bot.bot fetch https://www.youtube.com/watch?v=dQw4w9WgXcQ

  # Save as a Markdown file
  python -m youtube_bot.bot fetch https://youtu.be/dQw4w9WgXcQ \\
      --format markdown --output transcript.md

  # Save as SRT subtitles in Spanish
  python -m youtube_bot.bot fetch https://youtu.be/dQw4w9WgXcQ \\
      --language es --format srt --output subtitles.srt

  # Plain text, piped to another command
  python -m youtube_bot.bot fetch https://youtu.be/dQw4w9WgXcQ --format plain | wc -w
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .formatter import format_markdown, format_plain, format_srt, format_timestamped
from .transcript import TranscriptFetcher

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("youtube_bot")

# ---------------------------------------------------------------------------
# Format registry
# ---------------------------------------------------------------------------

_FORMATTERS = {
    "plain": format_plain,
    "timestamped": format_timestamped,
    "markdown": format_markdown,
    "srt": format_srt,
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """YouTube Transcript Bot — fetch and save transcripts from YouTube videos."""


@cli.command()
@click.argument("url")
@click.option(
    "--language", "-l",
    default=None,
    help="Preferred language code (e.g. 'en', 'es', 'fr'). "
         "Falls back to any available transcript if not found.",
)
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(list(_FORMATTERS), case_sensitive=False),
    default="timestamped",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output", "-o",
    default=None,
    help="File path to save the transcript. Prints to stdout if omitted.",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress progress messages (useful when piping output).",
)
def fetch(
    url: str,
    language: Optional[str],
    fmt: str,
    output: Optional[str],
    quiet: bool,
):
    """Fetch the transcript for a YouTube URL.

    URL can be any standard YouTube link:
      https://www.youtube.com/watch?v=VIDEO_ID
      https://youtu.be/VIDEO_ID
      https://www.youtube.com/shorts/VIDEO_ID
    """
    if not quiet:
        click.echo(f"Fetching transcript for: {url}", err=True)

    fetcher = TranscriptFetcher(preferred_language=language)

    try:
        transcript = fetcher.fetch(url)
    except ValueError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        # Covers TranscriptsDisabled, VideoUnavailable, NoTranscriptFound, etc.
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(1)

    if not quiet:
        click.echo(
            f"Fetched {transcript.word_count:,} words "
            f"({len(transcript.segments)} segments, language: {transcript.language})",
            err=True,
        )

    formatter = _FORMATTERS[fmt]
    text = formatter(transcript)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        if not quiet:
            click.echo(f"Saved to: {out_path}", err=True)
    else:
        click.echo(text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    cli()


if __name__ == "__main__":
    main()
