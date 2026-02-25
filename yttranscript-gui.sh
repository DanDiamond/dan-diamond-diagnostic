#!/bin/bash
# yttranscript-gui.sh
# Run this from macOS Shortcuts (or double-click) to fetch a YouTube transcript
# with GUI prompts for URL and output filename.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python3"

# ── 1. Ask for the YouTube URL ────────────────────────────────────────────────
URL=$(osascript <<'EOF'
  set result to display dialog "Enter YouTube URL:" ¬
    default answer "" ¬
    with title "YouTube Transcript" ¬
    buttons {"Cancel", "Fetch"} default button "Fetch"
  return text returned of result
EOF
)
[ $? -ne 0 ] || [ -z "$URL" ] && exit 0   # user cancelled

# ── 2. Ask for the output filename ───────────────────────────────────────────
FILENAME=$(osascript <<'EOF'
  set result to display dialog "Save transcript as (filename):" ¬
    default answer "transcript.md" ¬
    with title "YouTube Transcript" ¬
    buttons {"Cancel", "Save"} default button "Save"
  return text returned of result
EOF
)
[ $? -ne 0 ] || [ -z "$FILENAME" ] && exit 0   # user cancelled

# Ensure .md extension
[[ "$FILENAME" != *.md ]] && FILENAME="${FILENAME}.md"

# ── 3. Fetch the transcript ───────────────────────────────────────────────────
"$PYTHON" "$SCRIPT_DIR/run_youtube_bot.py" fetch "$URL" \
  --format markdown \
  --output "$HOME/Desktop/$FILENAME" 2>&1

STATUS=$?
if [ $STATUS -eq 0 ]; then
  osascript -e "display notification \"Saved to Desktop/$FILENAME\" with title \"YouTube Transcript\" sound name \"Glass\""
else
  osascript -e "display alert \"YouTube Transcript\" message \"Failed to fetch transcript. Check the URL and try again.\" as critical"
fi
