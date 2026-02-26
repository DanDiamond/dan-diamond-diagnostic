#!/usr/bin/env bash
# build_macos.sh
# Builds the YouTube Transcript macOS app and zips it for sharing.
# Run from the project root: ./build_macos.sh
# Requirements: macOS + Python 3.11+

set -eo pipefail

echo ""
echo "=== YouTube Transcript - macOS Build ==="
echo ""

# 1. Locate Python 3.11+
echo "==> Checking Python version..."
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" -c "import sys; print(sys.version_info.major * 100 + sys.version_info.minor)")
        if [ "$ver" -ge 311 ] 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.11 or newer is required. Install from https://www.python.org/"
    exit 1
fi
echo "==> Using $PYTHON ($($PYTHON --version))"

# 2. Build virtualenv
VENV=".venv-build"
echo "==> Creating isolated build environment in $VENV..."
"$PYTHON" -m venv "$VENV"
source "$VENV/bin/activate"

# 3. Install only the dependencies needed for the GUI app
echo "==> Installing dependencies (this may take a minute)..."
pip install -q --upgrade pip
pip install -q \
    "anthropic>=0.18.0" \
    "youtube-transcript-api>=1.0.0" \
    "python-dotenv>=1.0.0" \
    "httpx>=0.25.0" \
    "pyinstaller>=6.0.0"

# 4. Clean previous build artefacts
echo "==> Cleaning previous build output..."
rm -rf build dist

# 5. Run PyInstaller
echo "==> Building app bundle with PyInstaller..."
pyinstaller YTTranscript.spec --noconfirm

APP="dist/YTTranscript.app"
if [ ! -d "$APP" ]; then
    echo "ERROR: Build failed - $APP not found."
    exit 1
fi

# 6. Ad-hoc code sign (prevents "app is damaged" error on other Macs)
echo "==> Signing app (ad-hoc)..."
if command -v codesign >/dev/null 2>&1; then
    codesign --force --deep --sign - "$APP" && \
        echo "==> Signed successfully." || \
        echo "[warn] codesign failed - friends may need to right-click Open on first launch."
else
    echo "[warn] codesign not found - skipping."
fi

# 7. Zip for sharing
ZIP="YTTranscript.zip"
echo "==> Creating $ZIP..."
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo ""
echo "=== Done! ==="
echo ""
echo "  App: $(pwd)/$APP"
echo "  Zip: $(pwd)/$ZIP"
echo ""
echo "  Share YTTranscript.zip with your friends."
echo ""
echo "  Instructions for friends:"
echo "  1. Double-click YTTranscript.zip to unzip"
echo "  2. Drag YTTranscript.app to your Applications folder"
echo "  3. Right-click the app and choose Open (needed once for macOS security)"
echo "  4. Enter your Anthropic API key when prompted"
echo "  5. Paste a YouTube URL and click Fetch Transcript!"
echo ""
