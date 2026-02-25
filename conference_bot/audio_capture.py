"""Audio capture module.

Captures system audio output (what you *hear* from the conference) by
recording from the default loopback / monitor source.

Strategy by OS:
  - Linux  : PulseAudio monitor source  (e.g. "alsa_output.*.monitor")
  - macOS  : virtual loopback device    (BlackHole or Soundflower)
  - Windows: WASAPI loopback device

Falls back to the default input device if no monitor source is found.
The audio is saved as raw 16-bit PCM WAV files, one per chunk, ready
for Whisper transcription.
"""

import io
import logging
import platform
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

from .config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------


def _find_monitor_device_linux() -> Optional[int]:
    """Find a PulseAudio monitor source index via sounddevice."""
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name_lower = dev["name"].lower()
            if "monitor" in name_lower and dev["max_input_channels"] > 0:
                logger.info("Found PulseAudio monitor: [%d] %s", i, dev["name"])
                return i
    except Exception as exc:
        logger.debug("Monitor search error: %s", exc)
    return None


def _find_loopback_device_macos() -> Optional[int]:
    """Find BlackHole or Soundflower on macOS."""
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name_lower = dev["name"].lower()
            if any(k in name_lower for k in ("blackhole", "soundflower", "loopback")):
                if dev["max_input_channels"] > 0:
                    logger.info("Found loopback device: [%d] %s", i, dev["name"])
                    return i
    except Exception as exc:
        logger.debug("Loopback search error: %s", exc)
    return None


def _find_wasapi_loopback_windows() -> Optional[int]:
    """Find a WASAPI loopback device on Windows."""
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name_lower = dev["name"].lower()
            if "loopback" in name_lower and dev["max_input_channels"] > 0:
                logger.info("Found WASAPI loopback: [%d] %s", i, dev["name"])
                return i
    except Exception as exc:
        logger.debug("WASAPI loopback search error: %s", exc)
    return None


def get_capture_device() -> Optional[int]:
    """Return the best audio input device index for system-audio capture."""
    os_name = platform.system()
    if os_name == "Linux":
        return _find_monitor_device_linux()
    if os_name == "Darwin":
        return _find_loopback_device_macos()
    if os_name == "Windows":
        return _find_wasapi_loopback_windows()
    return None


def list_audio_devices():
    """Print all available audio devices (useful for debugging)."""
    print("\nAvailable audio devices:")
    print("-" * 60)
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        tag = "IN" if dev["max_input_channels"] > 0 else "  "
        print(f"  [{i:2d}] {tag}  {dev['name']}")
    print("-" * 60)


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class AudioRecorder:
    """Thread-safe audio recorder that saves fixed-length WAV chunks.

    Usage::

        recorder = AudioRecorder(output_dir="/tmp/session")
        recorder.start()
        time.sleep(60)
        chunks = recorder.stop()   # list of Path objects
    """

    def __init__(
        self,
        output_dir: str | Path,
        device: Optional[int] = None,
        chunk_seconds: int = None,
        sample_rate: int = None,
        channels: int = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.device = device if device is not None else get_capture_device()
        self.chunk_seconds = chunk_seconds or config.chunk_seconds
        self.sample_rate = sample_rate or config.sample_rate
        self.channels = channels or config.channels

        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._lock = threading.Lock()
        self._buffer: list[np.ndarray] = []
        self._chunks: list[Path] = []
        self._chunk_index = 0
        self._chunk_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start recording from the audio device."""
        if self._recording:
            logger.warning("Recorder already running")
            return

        if self.device is None:
            logger.warning(
                "No loopback/monitor device found — falling back to default input. "
                "You may only capture microphone audio."
            )

        self._recording = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            device=self.device,
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.1),  # 100 ms blocks
        )
        self._stream.start()

        # Thread that flushes a chunk every `chunk_seconds` seconds
        self._chunk_thread = threading.Thread(
            target=self._chunk_flusher, daemon=True
        )
        self._chunk_thread.start()

        logger.info(
            "Recording started (device=%s, sr=%d, chunk=%ds)",
            self.device,
            self.sample_rate,
            self.chunk_seconds,
        )

    def stop(self) -> list[Path]:
        """Stop recording and flush any remaining audio.

        Returns the list of WAV chunk file paths recorded so far.
        """
        if not self._recording:
            return self._chunks

        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self._chunk_thread:
            self._chunk_thread.join(timeout=5)

        # Flush whatever is left in the buffer
        self._flush_chunk()

        logger.info("Recording stopped — %d chunks saved", len(self._chunks))
        return list(self._chunks)

    @property
    def chunks(self) -> list[Path]:
        """Paths of WAV chunks flushed so far (safe to read during recording)."""
        with self._lock:
            return list(self._chunks)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            logger.debug("Audio status: %s", status)
        with self._lock:
            self._buffer.append(indata.copy())

    def _chunk_flusher(self):
        """Background thread: flush a chunk every `chunk_seconds` seconds."""
        while self._recording:
            time.sleep(self.chunk_seconds)
            self._flush_chunk()

    def _flush_chunk(self):
        """Write buffered audio to a WAV file and clear the buffer."""
        with self._lock:
            if not self._buffer:
                return
            audio = np.concatenate(self._buffer, axis=0)
            self._buffer.clear()

        chunk_path = self.output_dir / f"chunk_{self._chunk_index:04d}.wav"
        self._chunk_index += 1

        _write_wav(chunk_path, audio, self.sample_rate, self.channels)

        with self._lock:
            self._chunks.append(chunk_path)

        logger.debug("Flushed chunk: %s (%.1f s)", chunk_path.name, len(audio) / self.sample_rate)


# ---------------------------------------------------------------------------
# WAV helper
# ---------------------------------------------------------------------------


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int, channels: int):
    """Write a numpy int16 array to a WAV file."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)           # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())


def wav_bytes(audio: np.ndarray, sample_rate: int, channels: int) -> bytes:
    """Encode a numpy int16 array as WAV bytes (for API upload)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
