"""Session manager — ties together audio capture, transcription and summarization,
and writes the final outputs to disk.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .audio_capture import AudioRecorder
from .browser_driver import ConferenceBrowser
from .config import config
from .summarizer import Summarizer, Summary
from .transcriber import Transcript, Transcriber

logger = logging.getLogger(__name__)


class Session:
    """Manages the full lifecycle of a single conference recording session.

    Steps:
      1. Browser joins the meeting URL.
      2. AudioRecorder captures system audio in fixed-length chunks.
      3. Each chunk is transcribed by Whisper as it becomes available
         (streaming mode) or all at once after the session ends (batch mode).
      4. Claude produces a structured summary.
      5. Transcript + summary are saved to ``output_dir/<slug>/``.
    """

    def __init__(
        self,
        url: str,
        display_name: Optional[str] = None,
        context: str = "",
        output_dir: Optional[str] = None,
        headless: bool = False,
        language: Optional[str] = None,
        audio_device: Optional[int] = None,
        stream_transcription: bool = True,
    ):
        self.url = url
        self.display_name = display_name or config.bot_display_name
        self.context = context
        self.output_dir = Path(output_dir or config.output_dir)
        self.headless = headless
        self.language = language
        self.audio_device = audio_device
        self.stream_transcription = stream_transcription

        # Sub-components (created in run())
        self._browser: Optional[ConferenceBrowser] = None
        self._recorder: Optional[AudioRecorder] = None
        self._transcriber: Optional[Transcriber] = None
        self._summarizer: Optional[Summarizer] = None

        self._session_dir: Optional[Path] = None
        self._transcript = Transcript()
        self._summary: Optional[Summary] = None
        self._start_time: float = 0.0
        self._stop_requested = False
        self._transcribed_chunks: set[int] = set()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Run the full session (async).  Blocks until the meeting ends
        or ``stop()`` is called from another thread/task.
        """
        self._session_dir = self._make_session_dir()
        logger.info("Session directory: %s", self._session_dir)

        self._transcriber = Transcriber(language=self.language)
        self._summarizer = Summarizer()

        # Start the audio recorder
        self._recorder = AudioRecorder(
            output_dir=self._session_dir / "audio",
            device=self.audio_device,
        )
        self._recorder.start()
        self._start_time = time.time()

        # Start the browser and join the meeting
        self._browser = ConferenceBrowser(headless=self.headless)
        await self._browser.start()

        joined = await self._browser.join_meeting(self.url, self.display_name)
        if not joined:
            logger.warning("Failed to join meeting — continuing to record audio")

        # Main loop: stay in the meeting until it ends or stop() is called
        await self._monitor_loop()

        # Meeting over — stop recording
        chunk_paths = self._recorder.stop()
        await self._browser.stop()

        # Transcribe any remaining un-transcribed chunks
        await self._transcribe_remaining(chunk_paths)

        # Generate summary
        logger.info("Generating summary…")
        self._summary = self._summarizer.summarize(
            self._transcript, context=self.context
        )

        # Save outputs
        self._save_outputs()
        logger.info("Session complete. Outputs saved to %s", self._session_dir)

    def stop(self):
        """Request the session to stop (can be called from any thread)."""
        logger.info("Stop requested")
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _monitor_loop(self):
        """Poll: transcribe new chunks and detect meeting end."""
        while not self._stop_requested:
            await asyncio.sleep(5)

            # Check if the browser is still in a meeting
            if self._browser and not await self._browser.is_in_meeting():
                logger.info("Meeting appears to have ended")
                break

            # Stream transcription: pick up newly flushed chunks
            if self.stream_transcription:
                await self._transcribe_new_chunks()

    async def _transcribe_new_chunks(self):
        """Transcribe any chunks that have been flushed but not yet transcribed."""
        chunks = self._recorder.chunks
        for i, path in enumerate(chunks):
            if i not in self._transcribed_chunks:
                try:
                    time_offset = i * config.chunk_seconds
                    segments = self._transcriber.transcribe_file(
                        path,
                        chunk_index=i,
                        time_offset=float(time_offset),
                        prompt=self.context or None,
                    )
                    self._transcript.append_segments(segments)
                    self._transcribed_chunks.add(i)

                    # Save rolling transcript
                    self._save_transcript()
                except Exception as exc:
                    logger.error("Stream transcription error for chunk %d: %s", i, exc)

    async def _transcribe_remaining(self, chunk_paths: list[Path]):
        """Batch-transcribe any chunks not yet transcribed."""
        for i, path in enumerate(chunk_paths):
            if i not in self._transcribed_chunks:
                try:
                    time_offset = i * config.chunk_seconds
                    segments = self._transcriber.transcribe_file(
                        path,
                        chunk_index=i,
                        time_offset=float(time_offset),
                        prompt=self.context or None,
                    )
                    self._transcript.append_segments(segments)
                    self._transcribed_chunks.add(i)
                except Exception as exc:
                    logger.error("Batch transcription error for chunk %d: %s", i, exc)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _make_session_dir(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.output_dir / timestamp
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def _save_transcript(self):
        """Save the current rolling transcript to disk."""
        if not self._session_dir:
            return
        path = self._session_dir / "transcript.md"
        content = [
            "# Conference Transcript",
            "",
            f"**URL:** {self.url}",
            f"**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            self._transcript.timestamped_text,
        ]
        path.write_text("\n".join(content), encoding="utf-8")

    def _save_outputs(self):
        """Write the final transcript and summary files."""
        if not self._session_dir:
            return

        # Final transcript
        self._save_transcript()
        logger.info("Transcript saved: %s/transcript.md", self._session_dir)

        # Summary
        if self._summary:
            summary_path = self._session_dir / "summary.md"
            summary_path.write_text(self._summary.to_markdown(), encoding="utf-8")
            logger.info("Summary saved: %s/summary.md", self._session_dir)

        # Session metadata
        meta_path = self._session_dir / "session_info.txt"
        duration = time.time() - self._start_time
        meta_lines = [
            f"URL:          {self.url}",
            f"Display name: {self.display_name}",
            f"Context:      {self.context}",
            f"Duration:     {int(duration // 60)}m {int(duration % 60)}s",
            f"Segments:     {len(self._transcript)}",
            f"Words:        {self._transcript.word_count()}",
            f"Audio chunks: {len(self._transcribed_chunks)}",
        ]
        meta_path.write_text("\n".join(meta_lines), encoding="utf-8")
