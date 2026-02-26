#!/usr/bin/env bash
# build_macos.sh
#
# Builds the YouTube Transcript macOS app and zips it for sharing.
#
# Run from the project root:
#   chmod +x build_macos.sh
#   ./build_macos.sh
#
# Output: dist/YTTranscript.app   (and optionally YTTranscript.zip)
#
# Requirements: macOS + Python 3.11+

set -euo pipefail

# ── Colours ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}==>${NC} $*"; }
warning() { echo -e "${YELLOW}[warn]${NC} $*"; }
error()   { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   YouTube Transcript – macOS Build    ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ── 1. Locate Python 3.11+ ──────────────────────────────────────────────────
info "Checking Python version…"
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')")
        if [ "$ver" -ge 311 ] 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && error "Python 3.11 or newer is required. Install from https://www.python.org/"
info "Using $PYTHON ($(${PYTHON} --version))"

# ── 2. Build virtualenv ──────────────────────────────────────────────────────
VENV=".venv-build"
info "Creating isolated build environment in $VENV…"
"$PYTHON" -m venv "$VENV"
source "$VENV/bin/activate"

# ── 3. Install only the dependencies needed for the GUI app ─────────────────
info "Installing dependencies (this may take a minute)…"
pip install -q --upgrade pip
pip install -q \
    "anthropic>=0.18.0" \
    "youtube-transcript-api>=1.0.0" \
    "python-dotenv>=1.0.0" \
    "httpx>=0.25.0" \
    "pyinstaller>=6.0.0"

# ── 4. Clean previous build artefacts ───────────────────────────────────────
info "Cleaning previous build output…"
rm -rf build dist

# ── 5. Run PyInstaller ───────────────────────────────────────────────────────
info "Building app bundle with PyInstaller…"
pyinstaller YTTranscript.spec --noconfirm

APP="dist/YTTranscript.app"
[ -d "$APP" ] || error "Build failed – $APP not found."

# ── 6. Ad-hoc code sign ─────────────────────────────────────────────────────
# This prevents the "app is damaged" Gatekeeper error on other Macs.
# (A free Apple Developer certificate would enable full notarization.)
info "Signing app (ad-hoc)…"
if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "$APP" && \
        info "Signed successfully." || \
        warning "codesign failed – friends may need to right-click → Open on first launch."
else
    warning "codesign not found – skipping. Friends may need to right-click → Open."
fi

# ── 7. Zip for sharing ───────────────────────────────────────────────────────
ZIP="YTTranscript.zip"
info "Creating $ZIP for sharing…"
# Use ditto to preserve macOS metadata / resource forks
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo ""
info "Build complete!"
echo ""
echo "  App:  $(pwd)/$APP"
echo "  Zip:  $(pwd)/$ZIP"
echo ""
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  Share YTTranscript.zip with your friends.                  │"
echo "  │                                                             │"
echo "  │  First-time install for your friends:                       │"
echo "  │  1. Double-click YTTranscript.zip to unzip                 │"
echo "  │  2. Drag YTTranscript.app to /Applications                 │"
echo "  │  3. Right-click the app → Open  (needed once for Gatekeeper)│"
echo "  │  4. Enter their Anthropic API key when prompted             │"
echo "  │  5. Paste a YouTube URL and click Fetch Transcript!         │"
echo "  └─────────────────────────────────────────────────────────────┘"
echo ""
