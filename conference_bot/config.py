"""Configuration loader from environment variables and .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)


class Config:
    # API keys
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Bot identity
    bot_display_name: str = os.getenv("BOT_DISPLAY_NAME", "Transcription Bot")

    # Output
    output_dir: str = os.getenv("OUTPUT_DIR", "./sessions")

    # Audio settings
    chunk_seconds: int = int(os.getenv("CHUNK_SECONDS", "30"))
    sample_rate: int = 16000          # Whisper expects 16 kHz
    channels: int = 1                 # Mono

    # Model names
    whisper_model: str = os.getenv("WHISPER_MODEL", "whisper-1")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    # Platform credentials (all optional — bot can join as guest)
    google_email: str = os.getenv("GOOGLE_EMAIL", "")
    google_password: str = os.getenv("GOOGLE_PASSWORD", "")
    ms_email: str = os.getenv("MS_EMAIL", "")
    ms_password: str = os.getenv("MS_PASSWORD", "")
    zoom_email: str = os.getenv("ZOOM_EMAIL", "")
    zoom_password: str = os.getenv("ZOOM_PASSWORD", "")

    def validate(self) -> list[str]:
        """Return a list of validation error strings (empty = all good)."""
        errors = []
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is not set")
        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is not set")
        return errors


config = Config()
