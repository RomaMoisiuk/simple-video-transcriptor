# Transcribe

A local web app for transcribing YouTube videos using [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [OpenAI Whisper](https://github.com/openai/whisper).

## Prerequisites

Install all required external tools before running the app.

### 1. ffmpeg (required by yt-dlp for audio conversion)

```bash
brew install ffmpeg
```

> Without ffmpeg, yt-dlp downloads the audio but cannot convert it to MP3 and the transcription will fail.

### 2. yt-dlp

```bash
pip install yt-dlp
# or: brew install yt-dlp
```

### 3. OpenAI Whisper

```bash
pip install openai-whisper
```

### 4. Fix numba/coverage incompatibility

After installing Whisper, uninstall the `coverage` package. Whisper pulls in `numba`, which crashes on import when `coverage` 7.x is present (a known upstream bug — `coverage.types.Tracer` was removed in version 7):

```bash
pip uninstall coverage -y
```

This is safe: nothing in the transcription pipeline needs code-coverage tooling at runtime.

## Setup

Install the Flask server dependencies:

```bash
pip install -r requirements.txt
```

## Run

### Option A — Auto-start on login (recommended, one-time setup)

```bash
python install_service.py
```

This registers the server as a **macOS LaunchAgent**. After this runs once, the server starts automatically every time you log in. You can then open `templates/index.html` directly in your browser (or bookmark `http://localhost:5000`) — no terminal needed, ever.

To remove the auto-start:

```bash
python uninstall_service.py
```

### Option B — On-demand (start + open browser in one command)

```bash
python launch.py
```

Checks if the server is already running, starts it in the background if not, and opens `http://localhost:5000` automatically.

### Option C — Manual

```bash
python app.py
```

## Features

- Paste a YouTube URL, pick a language and Whisper model, choose an output format (plain text, SRT subtitles, or both), and hit **Start Transcription**.
- Language dropdown includes a custom "Other (type it…)" option for any language Whisper supports.
- Real-time progress streamed via Server-Sent Events — no page reloads.
- Collapsible raw log for full yt-dlp / Whisper output, with inline error details when something goes wrong.
- Output saved to a folder of your choice (default: `~/transcripts`).

## Models

| Model    | Speed       | Accuracy |
|----------|-------------|----------|
| tiny     | Fastest     | Basic    |
| base     | Fast        | Good     |
| small    | Balanced    | Better   |
| medium   | Slow        | Great    |
| large-v3 | Very slow   | Best     |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ffmpeg not found` | `brew install ffmpeg` |
| `yt-dlp not found` | `pip install yt-dlp` |
| `whisper not found` | `pip install openai-whisper` |
| `AttributeError: module 'coverage.types' has no attribute 'Tracer'` | `pip uninstall coverage -y` |
| Server did not start within 20s (LaunchAgent) | Check `server.log` in the project folder for details |

## Project structure

```
video-transcriptor/
├── app.py                  # Flask backend (SSE streaming)
├── templates/
│   └── index.html          # Frontend — works served by Flask or as file://
├── install_service.py      # Register server as macOS LaunchAgent (run once)
├── uninstall_service.py    # Remove the LaunchAgent
├── launch.py               # On-demand: start server + open browser
├── requirements.txt
└── README.md
```
