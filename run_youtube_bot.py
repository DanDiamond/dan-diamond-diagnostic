#!/usr/bin/env python3
"""Convenience entry point — equivalent to: python -m youtube_bot fetch <URL>

Examples:
  python run_youtube_bot.py fetch https://www.youtube.com/watch?v=dQw4w9WgXcQ
  python run_youtube_bot.py fetch https://youtu.be/dQw4w9WgXcQ --format markdown --output transcript.md
  python run_youtube_bot.py fetch https://youtu.be/dQw4w9WgXcQ --language es --format srt
"""
from youtube_bot.bot import main

if __name__ == "__main__":
    main()
