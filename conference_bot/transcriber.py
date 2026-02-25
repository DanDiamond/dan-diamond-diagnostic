"""Whisper transcription module.

Sends WAV audio chunks to the OpenAI Whisper API and returns timestamped
transcript segments.  Chunks are processed in order and the running
transcript is kept in memory.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from openai import OpenAI

from .config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Segment:
    """A single transcribed segment with optional timing info."""
    start: float       # seconds from start of the chunk
    end: float
    text: str
    chunk_index: int   # which audio chunk this came from


@dataclass
class Transcript:
    """Accumulated transcript for an entire session."""
    segments: list[Segment] = field(default_factory=list)

    def append_segments(self, new_segments: list[Segment]):
        self.segments.extend(new_segments)

    @property
    def full_text(self) -> str:
        """Plain text, one segment per line."""
        return "\n".join(s.text.strip() for s in self.segments if s.text.strip())

    @property
    def timestamped_text(self) -> str:
        """Text with [HH:MM:SS] timestamps prepended to each segment."""
        lines = []
        for seg in self.segments:
            h = int(seg.start // 3600)
            m = int((seg.start % 3600) // 60)
            s = int(seg.start % 60)
            lines.append(f"[{h:02d}:{m:02d}:{s:02d}] {seg.text.strip()}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.segments)

    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.segments)


# ---------------------------------------------------------------------------
# Transcriber
# ---------------------------------------------------------------------------


class Transcriber:
    """Wraps the OpenAI Whisper API for audio transcription.

    Usage::

        t = Transcriber()
        segments = t.transcribe_file(Path("chunk_0000.wav"), chunk_index=0)
    """

    def __init__(self, model: Optional[str] = None, language: Optional[str] = None):
        """
        Args:
            model:    Whisper model name (default: config.whisper_model = "whisper-1")
            language: ISO 639-1 language code hint, e.g. "en".  Leave None for
                      auto-detection.
        """
        self.model = model or config.whisper_model
        self.language = language
        self._client = OpenAI(api_key=config.openai_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe_file(
        self,
        path: Path,
        chunk_index: int = 0,
        time_offset: float = 0.0,
        prompt: Optional[str] = None,
    ) -> list[Segment]:
        """Transcribe a single WAV file.

        Args:
            path:        Path to the WAV file.
            chunk_index: Sequence number of this chunk (for ordering).
            time_offset: Seconds to add to all segment timestamps (running
                         total from the session start).
            prompt:      Optional context prompt to improve accuracy (e.g.
                         topic keywords, speaker names).

        Returns:
            List of Segment objects.
        """
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        logger.info("Transcribing chunk %d: %s", chunk_index, path.name)

        kwargs = dict(model=self.model, response_format="verbose_json")
        if self.language:
            kwargs["language"] = self.language
        if prompt:
            kwargs["prompt"] = prompt

        with open(path, "rb") as audio_file:
            response = self._client.audio.transcriptions.create(
                file=audio_file,
                **kwargs,
            )

        segments = []
        raw_segments = getattr(response, "segments", None)
        if raw_segments:
            for seg in raw_segments:
                segments.append(
                    Segment(
                        start=float(seg.get("start", 0)) + time_offset,
                        end=float(seg.get("end", 0)) + time_offset,
                        text=seg.get("text", ""),
                        chunk_index=chunk_index,
                    )
                )
        else:
            # Fallback: treat the whole response as a single segment
            text = getattr(response, "text", "") or ""
            if text.strip():
                segments.append(
                    Segment(
                        start=time_offset,
                        end=time_offset + config.chunk_seconds,
                        text=text,
                        chunk_index=chunk_index,
                    )
                )

        logger.info(
            "Chunk %d: %d segments, ~%d words",
            chunk_index,
            len(segments),
            sum(len(s.text.split()) for s in segments),
        )
        return segments

    def transcribe_chunks(
        self,
        chunk_paths: list[Path],
        prompt: Optional[str] = None,
    ) -> Transcript:
        """Transcribe a list of WAV chunk files in order.

        Returns a fully assembled Transcript.
        """
        transcript = Transcript()
        time_offset = 0.0

        for i, path in enumerate(chunk_paths):
            try:
                segments = self.transcribe_file(
                    path,
                    chunk_index=i,
                    time_offset=time_offset,
                    prompt=prompt,
                )
                transcript.append_segments(segments)
                # Advance the time offset by the actual chunk duration
                time_offset += config.chunk_seconds
            except Exception as exc:
                logger.error("Failed to transcribe chunk %d (%s): %s", i, path.name, exc)

        logger.info(
            "Transcription complete: %d segments, %d words total",
            len(transcript),
            transcript.word_count(),
        )
        return transcript
