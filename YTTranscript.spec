# -*- mode: python ; coding: utf-8 -*-
#
# YTTranscript.spec
# PyInstaller spec for the YouTube Transcript macOS app.
#
# Build with:
#   pyinstaller YTTranscript.spec --noconfirm
#
# Or just run: ./build_macos.sh

a = Analysis(
    ["yttranscript_app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Include the youtube_bot package explicitly so PyInstaller
        # doesn't miss any sub-modules that are imported at runtime.
        ("youtube_bot", "youtube_bot"),
    ],
    hiddenimports=[
        # youtube-transcript-api internals
        "youtube_transcript_api",
        "youtube_transcript_api._api",
        "youtube_transcript_api._errors",
        "youtube_transcript_api._transcripts",
        "youtube_transcript_api._html_unescaping",
        "youtube_transcript_api.proxies",
        # anthropic SDK
        "anthropic",
        "anthropic._client",
        "anthropic.types",
        # httpx + transport layer used by anthropic
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
        "anyio",
        "anyio._backends._asyncio",
        "sniffio",
        # TLS / certificate chain
        "certifi",
        "ssl",
        # Standard library extras sometimes missed on frozen builds
        "email.mime.text",
        "email.mime.multipart",
        "email.generator",
        "logging.handlers",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude the heavy conference-bot dependencies we don't need
    excludes=[
        "playwright",
        "sounddevice",
        "numpy",
        "scipy",
        "pydub",
        "openai",
        "tkinter.test",
        "unittest",
        "xmlrunner",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YTTranscript",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no Terminal window
    disable_windowed_traceback=False,
    argv_emulation=True,    # macOS: handle dropped files / URL events
    target_arch=None,       # universal2 if supported; else native arch
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="YTTranscript",
)

app = BUNDLE(
    coll,
    name="YTTranscript.app",
    icon=None,              # replace with "YTTranscript.icns" if you have one
    bundle_identifier="com.danieldiamond.yttranscript",
    info_plist={
        "CFBundleName": "YouTube Transcript",
        "CFBundleDisplayName": "YouTube Transcript",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Daniel Diamond",
        # Allow outbound network connections (needed for YouTube + Anthropic API)
        "NSAppTransportSecurity": {
            "NSAllowsArbitraryLoads": True,
        },
    },
)
