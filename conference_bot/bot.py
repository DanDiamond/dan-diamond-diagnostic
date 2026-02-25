"""Main CLI for the Conference Transcription Bot.

Usage examples:

  # Join a Google Meet lecture (visible browser window)
  python -m conference_bot.bot join https://meet.google.com/abc-def-ghi

  # Join headlessly, provide context, save to custom directory
  python -m conference_bot.bot join https://zoom.us/j/123456 \\
      --headless \\
      --context "Python conference — async IO talk" \\
      --output ./my-sessions

  # Transcribe + summarize previously recorded audio chunks
  python -m conference_bot.bot transcribe ./sessions/20240315_143000/audio/

  # List available audio input devices
  python -m conference_bot.bot devices
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import click

from .audio_capture import list_audio_devices
from .config import config
from .session import Session
from .transcriber import Transcriber
from .summarizer import Summarizer

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("conference_bot")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Conference Transcription Bot — join, record, transcribe, and summarize
    online lectures automatically."""


# ------------------------------------------------------------------
# join
# ------------------------------------------------------------------


@cli.command()
@click.argument("url")
@click.option("--name", "-n", default=None, help="Display name shown in the conference")
@click.option("--context", "-c", default="", help="Topic/context hint for better transcription accuracy")
@click.option("--output", "-o", default=None, help="Directory to save outputs (default: ./sessions)")
@click.option("--headless/--no-headless", default=False, help="Run browser in headless mode")
@click.option("--language", "-l", default=None, help="Language code hint for Whisper (e.g. 'en', 'fr')")
@click.option("--device", "-d", default=None, type=int, help="Audio device index (see 'bot devices')")
@click.option("--no-stream", is_flag=True, default=False, help="Disable streaming transcription (batch at end)")
def join(
    url: str,
    name: Optional[str],
    context: str,
    output: Optional[str],
    headless: bool,
    language: Optional[str],
    device: Optional[int],
    no_stream: bool,
):
    """Join a conference at URL and record/transcribe/summarize the session.

    Supports Google Meet, Zoom, Microsoft Teams, Webex, or any web-based
    conference URL.
    """
    # Validate config
    errors = config.validate()
    if errors:
        for e in errors:
            click.echo(f"[ERROR] {e}", err=True)
        click.echo("Set missing keys in your .env file (see .env.example)", err=True)
        sys.exit(1)

    click.echo(f"Joining: {url}")
    if context:
        click.echo(f"Context: {context}")

    session = Session(
        url=url,
        display_name=name,
        context=context,
        output_dir=output,
        headless=headless,
        language=language,
        audio_device=device,
        stream_transcription=not no_stream,
    )

    # Allow Ctrl+C / SIGTERM to gracefully stop the session
    def _handle_signal(sig, frame):
        click.echo("\nStop signal received — finishing up…")
        session.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    asyncio.run(session.run())
    click.echo("Done.  Check the session directory for transcript and summary.")


# ------------------------------------------------------------------
# transcribe  (offline, from existing audio files)
# ------------------------------------------------------------------


@cli.command()
@click.argument("audio_dir")
@click.option("--context", "-c", default="", help="Topic/context hint")
@click.option("--output", "-o", default=None, help="Output directory (defaults to audio_dir parent)")
@click.option("--language", "-l", default=None, help="Language hint for Whisper")
def transcribe(audio_dir: str, context: str, output: Optional[str], language: Optional[str]):
    """Transcribe and summarize previously recorded WAV chunk files.

    AUDIO_DIR should contain chunk_NNNN.wav files produced by a previous
    recording session.
    """
    errors = config.validate()
    if errors:
        for e in errors:
            click.echo(f"[ERROR] {e}", err=True)
        sys.exit(1)

    audio_path = Path(audio_dir)
    if not audio_path.exists():
        click.echo(f"[ERROR] Directory not found: {audio_dir}", err=True)
        sys.exit(1)

    chunks = sorted(audio_path.glob("chunk_*.wav"))
    if not chunks:
        click.echo(f"[ERROR] No chunk_NNNN.wav files found in {audio_dir}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(chunks)} audio chunk(s) in {audio_dir}")

    t = Transcriber(language=language)
    transcript = t.transcribe_chunks(chunks, prompt=context or None)

    click.echo(f"Transcribed {transcript.word_count()} words in {len(transcript)} segments")
    click.echo("Generating summary…")

    s = Summarizer()
    summary = s.summarize(transcript, context=context)

    out_dir = Path(output) if output else audio_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "transcript.md").write_text(
        "# Conference Transcript\n\n" + transcript.timestamped_text, encoding="utf-8"
    )
    (out_dir / "summary.md").write_text(summary.to_markdown(), encoding="utf-8")

    click.echo(f"Saved transcript.md and summary.md to {out_dir}")


# ------------------------------------------------------------------
# devices
# ------------------------------------------------------------------


@cli.command()
def devices():
    """List available audio input devices and exit."""
    list_audio_devices()
    click.echo("\nPass the device index to 'join' with --device <index>")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    cli()


if __name__ == "__main__":
    main()
