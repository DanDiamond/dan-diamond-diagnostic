#!/bin/bash
# yttranscript-gui.sh
# Called from macOS Shortcuts with two arguments: URL and filename.
# The Shortcut uses native "Ask for Input" actions (which support paste).
#
# Usage: yttranscript-gui.sh <youtube-url> <filename>

URL="$1"
FILENAME="$2"

SCRIPT_DIR="/Users/danieldiamond/dan-diamond-diagnostic"
PYTHON="$SCRIPT_DIR/venv/bin/python3"

# Validate inputs
if [ -z "$URL" ] || [ -z "$FILENAME" ]; then
  osascript -e "display alert \"YouTube Transcript\" message \"URL or filename was empty.\" as critical"
  exit 1
fi

# Ensure .md extension
[[ "$FILENAME" != *.md ]] && FILENAME="${FILENAME}.md"

# Fetch the transcript
"$PYTHON" "$SCRIPT_DIR/run_youtube_bot.py" fetch "$URL" \
  --format markdown \
  --output "$HOME/Desktop/$FILENAME" 2>&1

STATUS=$?
if [ $STATUS -eq 0 ]; then
  osascript -e "display notification \"Saved to Desktop/$FILENAME\" with title \"YouTube Transcript\" sound name \"Glass\""
else
  osascript -e "display alert \"YouTube Transcript\" message \"Failed to fetch transcript. Check the URL and try again.\" as critical"
fi
