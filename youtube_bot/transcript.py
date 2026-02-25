"""Fetch transcripts from YouTube videos using the YouTube Transcript API."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TranscriptSegment:
    text: str
    start: float   # seconds from video start
    duration: float


@dataclass
class Transcript:
    video_id: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)

    # -----------------------------------------------------------------------
    # Convenience properties
    # -----------------------------------------------------------------------

    @property
    def plain_text(self) -> str:
        """All segments joined into one continuous block of text."""
        return " ".join(s.text.strip() for s in self.segments)

    @property
    def timestamped_text(self) -> str:
        """Segments prefixed with [MM:SS] timestamps."""
        lines = []
        for seg in self.segments:
            m, s = divmod(int(seg.start), 60)
            h, m = divmod(m, 60)
            if h:
                ts = f"[{h:02d}:{m:02d}:{s:02d}]"
            else:
                ts = f"[{m:02d}:{s:02d}]"
            lines.append(f"{ts} {seg.text.strip()}")
        return "\n".join(lines)

    @property
    def word_count(self) -> int:
        return len(self.plain_text.split())


# ---------------------------------------------------------------------------
# Video ID extraction
# ---------------------------------------------------------------------------

_YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}


def extract_video_id(url: str) -> str:
    """Parse a YouTube URL and return its 11-character video ID.

    Supports formats:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - Plain video ID (11 alphanumeric + dash/underscore chars)
    """
    url = url.strip()

    # Already a raw video ID?
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url

    parsed = urlparse(url)
    host = parsed.netloc.lstrip("www.").lower()

    if host not in {d.lstrip("www.") for d in _YOUTUBE_DOMAINS}:
        raise ValueError(f"Not a recognised YouTube URL: {url!r}")

    # youtu.be/<ID>
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return video_id

    # /watch?v=<ID>
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]

    # /embed/<ID>  or  /shorts/<ID>  or  /v/<ID>
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in ("embed", "shorts", "v", "e"):
        return path_parts[1]

    raise ValueError(f"Could not extract video ID from URL: {url!r}")


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


class TranscriptFetcher:
    """Fetch the best-available transcript for a YouTube video."""

    def __init__(self, preferred_language: Optional[str] = None):
        self.preferred_language = preferred_language  # e.g. "en", "fr"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> Transcript:
        """Fetch transcript for *url* and return a :class:`Transcript`.

        Raises:
            ValueError: bad URL.
            TranscriptsDisabled: captions are off for this video.
            NoTranscriptFound: no transcript in requested language.
            VideoUnavailable: video does not exist / is private.
        """
        video_id = extract_video_id(url)

        try:
            transcript_list = YouTubeTranscriptApi().list_transcripts(video_id)
        except VideoUnavailable as exc:
            raise VideoUnavailable(video_id) from exc
        except TranscriptsDisabled as exc:
            raise TranscriptsDisabled(video_id) from exc

        transcript_obj = self._select_transcript(transcript_list)
        raw = transcript_obj.fetch()

        segments = [
            TranscriptSegment(
                text=entry.text if hasattr(entry, "text") else entry.get("text", ""),
                start=entry.start if hasattr(entry, "start") else entry.get("start", 0.0),
                duration=entry.duration if hasattr(entry, "duration") else entry.get("duration", 0.0),
            )
            for entry in raw
        ]

        return Transcript(
            video_id=video_id,
            language=transcript_obj.language_code,
            segments=segments,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_transcript(self, transcript_list):
        """Pick the best transcript: prefer *preferred_language*, then any
        manually created one, then first auto-generated."""
        lang = self.preferred_language

        # 1. Explicit language requested
        if lang:
            try:
                return transcript_list.find_manually_created_transcript([lang])
            except NoTranscriptFound:
                pass
            try:
                return transcript_list.find_generated_transcript([lang])
            except NoTranscriptFound:
                pass

        # 2. Any manually-created transcript (highest quality)
        try:
            return transcript_list.find_manually_created_transcript(
                [t.language_code for t in transcript_list]
            )
        except NoTranscriptFound:
            pass

        # 3. Fall back to auto-generated
        for t in transcript_list:
            return t

        raise NoTranscriptFound(
            "No transcript available for this video.", [], []
        )
