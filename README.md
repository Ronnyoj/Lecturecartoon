# LectureCartoon Custom AI — Local Prototype

A local-first prototype for testing a custom cartoon lecture creator on a computer or tablet. It uses Python, Flask, browser-native UI, FFmpeg (optional), and a pluggable worker architecture. It does not require cloud accounts for the interface.

## Features
- Long speaker notes with no word-count cap in the UI; scripts are split into scenes for processing.
- Voice profiles and uploaded narration audio.
- Cartoon presenter choices and uploaded presenter images.
- Optional auto-slide outline (rule-based offline mode).
- MP4 export of a complete slide-and-audio video using FFmpeg if installed.
- If no narration is uploaded, an optional local system voice can be generated using `espeak`/`espeak-ng` if installed. The browser preview can use Web Speech API where supported.
- Local project settings saved as JSON.

## Requirements
- Python 3.10+
- Optional for MP4 export: FFmpeg (`ffmpeg` available in PATH)
- Optional local voice: `espeak-ng` or `espeak`
- Runs locally; no API keys required for basic use.

## Run on Windows
1. Install Python from https://www.python.org/downloads/ (check “Add Python to PATH”).
2. Extract this ZIP.
3. Open the extracted folder.
4. Double-click `run_windows.bat`.
5. Open `http://127.0.0.1:5000` if the browser does not open automatically.

## Run on macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000.

## Android tablet note
A tablet browser can open the UI only if the server runs on a computer on the same Wi-Fi network; then visit `http://COMPUTER-LAN-IP:5000`. This prototype is not a native Android app. Some Android browsers cannot run Python locally without a separate Python environment.

## MP4 export
1. Select a cartoon presenter or upload an image.
2. Add notes; choose slide mode.
3. Upload a narration audio file (MP3/WAV/M4A supported by your FFmpeg build), or select local system voice if available.
4. Click “Build lecture MP4”.
5. The app generates a slide-based video with presenter image, title, bullet text and audio. If FFmpeg is missing, the app explains how to install it.

This local prototype produces a polished slide-and-presenter video. It does not yet create advanced 3D character motion or phoneme-level lip synchronization. Those features require a dedicated animation model/engine and capable hardware or a model integration. The adapter points for a future custom AI engine are documented in `engine/README.md`.

## Privacy
The app is designed for local testing. Uploaded files and generated videos are stored in `instance/` on the machine running the app. Do not expose the development server to the public internet without authentication, upload limits, secure deployment, and a threat review.
