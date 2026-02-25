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

# Shortcuts sometimes passes a URL wrapped in list brackets: ["https://..."] or []
# Strip the brackets and any surrounding quotes/spaces.
if [[ "$URL" == \[*\] ]]; then
  URL="${URL:1:${#URL}-2}"   # drop leading [ and trailing ]
  URL="${URL//\"/}"           # remove quote chars
  URL="${URL// /}"            # remove spaces
fi

# Validate inputs
if [ -z "$URL" ] || [ -z "$FILENAME" ]; then
  osascript -e "display alert \"YouTube Transcript\" message \"URL or filename was empty.\" as critical"
  exit 1
fi

# Ensure .md extension
[[ "$FILENAME" != *.md ]] && FILENAME="${FILENAME}.md"

# Fetch the transcript
OUT_DIR="$HOME/Transcripts"
mkdir -p "$OUT_DIR"

OUTPUT=$("$PYTHON" "$SCRIPT_DIR/run_youtube_bot.py" fetch "$URL" \
  --format markdown \
  --output "$OUT_DIR/$FILENAME" 2>&1)

STATUS=$?
if [ $STATUS -eq 0 ]; then
  osascript -e "display notification \"Saved to ~/Transcripts/$FILENAME\" with title \"YouTube Transcript\" sound name \"Glass\""
else
  osascript -e "display alert \"YouTube Transcript\" message \"${OUTPUT}\" as critical"
fi
