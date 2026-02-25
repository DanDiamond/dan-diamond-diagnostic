# Conference Transcription Bot — Setup Guide

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python --version` |
| OpenAI API key | For Whisper transcription |
| Anthropic API key | For Claude summarization |
| Linux (recommended) | PulseAudio for system-audio capture |

---

## 1. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

---

## 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY and ANTHROPIC_API_KEY
```

---

## 3. (Linux) Enable system-audio capture

The bot records **what you hear** from the conference (not just your mic).
On Linux with PulseAudio this is done automatically via the monitor source.

Verify it's available:

```bash
python run_bot.py devices
# Look for an entry like: [3] IN  alsa_output.pci-0000_00_1f.Monitor
```

On **macOS** install [BlackHole](https://github.com/ExistentialAudio/BlackHole)
(free) and set it as the system audio output device, then select it with
`--device <index>`.

---

## 4. Run

### Join a live conference

```bash
# Google Meet (browser window visible)
python run_bot.py join https://meet.google.com/abc-def-ghi

# Zoom (headless, with topic context)
python run_bot.py join https://zoom.us/j/1234567890 \
    --headless \
    --context "Machine Learning lecture — transformers"

# Microsoft Teams
python run_bot.py join "https://teams.microsoft.com/l/meetup-join/..."

# Any web conference
python run_bot.py join https://my-conference.example.com/room/xyz
```

Press **Ctrl+C** to stop the bot; it will finish transcribing and save outputs.

### Transcribe previously recorded audio

```bash
python run_bot.py transcribe ./sessions/20240315_143000/audio/
```

### List audio devices

```bash
python run_bot.py devices
```

---

## 5. Output files

Each session creates a timestamped directory under `./sessions/`:

```
sessions/
└── 20240315_143000/
    ├── audio/
    │   ├── chunk_0000.wav
    │   ├── chunk_0001.wav
    │   └── ...
    ├── transcript.md      ← timestamped full transcript
    ├── summary.md         ← Claude-generated structured summary
    └── session_info.txt   ← metadata (duration, word count, …)
```

`summary.md` contains:
- Session title
- Executive summary
- Key points
- Action items
- Decisions made
- Q&A highlights

---

## CLI reference

```
conference-bot join URL [OPTIONS]

  --name / -n       Display name shown in the meeting
  --context / -c    Topic hint for better transcription accuracy
  --output / -o     Output directory  (default: ./sessions)
  --headless        Run browser without a visible window
  --language / -l   ISO 639-1 language hint, e.g. 'en', 'fr'
  --device / -d     Audio device index (from 'bot devices')
  --no-stream       Transcribe all at once at the end (vs. rolling)

conference-bot transcribe AUDIO_DIR [OPTIONS]

  --context / -c    Topic hint
  --output / -o     Output directory
  --language / -l   Language hint

conference-bot devices
  List audio input devices and their indices.
```

---

## Platform notes

| Platform | Join method | Notes |
|---|---|---|
| Google Meet | Browser (Playwright) | Optional Google sign-in via `.env` |
| Zoom | Web client (`/wc/join/`) | No Zoom app required |
| Microsoft Teams | Browser (`launchAgent=false`) | Works without the Teams app |
| Webex | Browser | Guest join supported |
| Generic | Browser | Works with any web-based conference |
