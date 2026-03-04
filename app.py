import os
import queue
import threading
import subprocess
import tempfile
import uuid
import json
from pathlib import Path
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

app = Flask(__name__)

# In-memory job store — fine for a single-user local app
jobs: dict = {}


# ── Background worker ──────────────────────────────────────────────────────────

def run_transcription(job_id: str, url: str, language: str,
                      model: str, output_format: str, output_folder: str) -> None:
    job = jobs[job_id]
    job["status"] = "running"
    q: queue.Queue = job["queue"]
    log_buffer: list[str] = []   # rolling capture of every log line

    def emit(event_type: str, data) -> None:
        if event_type == "log":
            log_buffer.append(data)
        q.put({"type": event_type, "data": data})

    def emit_error(message: str) -> None:
        """Emit an error with the recent log tail attached for the UI."""
        job["status"] = "error"
        job["error"]  = message
        q.put({
            "type": "error",
            "data": {
                "message":  message,
                "log_tail": log_buffer[-30:],   # last 30 lines
            },
        })

    try:
        with tempfile.TemporaryDirectory() as tmpdir:

            # ── Step 1: Download audio ────────────────────────────────────────
            job["step"] = 1
            emit("step", {"step": 1, "message": "Downloading audio…"})

            dl_cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--no-playlist",
                "--output", os.path.join(tmpdir, "%(title)s.%(ext)s"),
                url,
            ]
            emit("log", "$ " + " ".join(dl_cmd))

            proc = subprocess.Popen(
                dl_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            downloaded: str | None = None
            for raw in proc.stdout:
                line = raw.rstrip()
                if line:
                    emit("log", line)
                if "[ExtractAudio] Destination:" in line:
                    downloaded = line.split("Destination:", 1)[-1].strip()

            proc.wait()

            if proc.returncode != 0:
                tail = "\n".join(log_buffer[-15:])
                if "ffprobe and ffmpeg not found" in tail or "ffmpeg not found" in tail.lower():
                    raise RuntimeError(
                        "ffmpeg not found — install it with:  brew install ffmpeg"
                    )
                raise RuntimeError("yt-dlp failed (non-zero exit code)")

            # Fallback: scan the temp dir for any audio file
            if not downloaded or not os.path.exists(downloaded):
                candidates = sorted(
                    Path(tmpdir).glob("*.mp3"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if not candidates:
                    candidates = sorted(
                        [p for p in Path(tmpdir).iterdir() if p.is_file()],
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                if not candidates:
                    raise RuntimeError("Downloaded audio file not found in temp directory.")
                downloaded = str(candidates[0])

            emit("log", f"✔ Audio ready: {Path(downloaded).name}")

            # ── Step 2: Transcribe ────────────────────────────────────────────
            job["step"] = 2
            emit("step", {"step": 2, "message": "Transcribing with Whisper…"})

            out_dir = Path(output_folder).expanduser().resolve()
            out_dir.mkdir(parents=True, exist_ok=True)

            fmt_map = {"text": "txt", "subtitles": "srt", "both": "all"}
            whisper_fmt = fmt_map.get(output_format, "txt")

            wh_cmd = [
                "whisper",
                downloaded,
                "--model", model,
                "--language", language,
                "--output_format", whisper_fmt,
                "--output_dir", str(out_dir),
            ]
            emit("log", "$ " + " ".join(wh_cmd))

            proc = subprocess.Popen(
                wh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for raw in proc.stdout:
                line = raw.rstrip()
                if line:
                    emit("log", line)
            proc.wait()

            if proc.returncode != 0:
                tail = "\n".join(log_buffer[-15:])
                if "no module named" in tail.lower() or "command not found" in tail.lower():
                    raise RuntimeError(
                        "whisper command not found — install it with:  pip install openai-whisper"
                    )
                raise RuntimeError("Whisper failed (non-zero exit code)")

            # Collect output files
            stem = Path(downloaded).stem
            want_exts = {
                "text":      ["txt"],
                "subtitles": ["srt"],
                "both":      ["txt", "srt", "vtt"],
            }.get(output_format, ["txt"])

            output_files = [
                str(out_dir / f"{stem}.{ext}")
                for ext in want_exts
                if (out_dir / f"{stem}.{ext}").exists()
            ]

            # Last-resort: show everything in the output folder
            if not output_files:
                output_files = [
                    str(f) for f in out_dir.iterdir()
                    if f.suffix in {".txt", ".srt", ".vtt", ".tsv", ".json"}
                ]

            job["status"] = "done"
            job["output_files"] = output_files
            emit("done", {"files": output_files})

    except FileNotFoundError as exc:
        tool = "yt-dlp" if "yt-dlp" in str(exc) else "whisper"
        emit_error(f"{tool} not found — make sure it is installed and on your PATH.")

    except Exception as exc:
        emit_error(str(exc))

    finally:
        q.put(None)   # sentinel — tells the SSE generator to close


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response: Response) -> Response:
    """Allow requests from file:// pages (index.html opened directly)."""
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/transcribe", methods=["POST", "OPTIONS"])
def transcribe():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status":       "queued",
        "step":         0,
        "queue":        queue.Queue(),
        "output_files": [],
        "error":        None,
    }

    threading.Thread(
        target=run_transcription,
        args=(
            job_id,
            url,
            data.get("language",      "en"),
            data.get("model",         "base"),
            data.get("format",        "text"),
            data.get("output_folder", "~/transcripts"),
        ),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id: str):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        q: queue.Queue = jobs[job_id]["queue"]
        while True:
            try:
                event = q.get(timeout=30)
                if event is None:                       # sentinel
                    yield 'data: {"type":"end"}\n\n'
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                yield 'data: {"type":"heartbeat"}\n\n'  # keep-alive ping

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


@app.route("/status/<job_id>")
def status(job_id: str):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    job = jobs[job_id]
    return jsonify({
        "status":       job["status"],
        "step":         job["step"],
        "output_files": job["output_files"],
        "error":        job["error"],
    })


if __name__ == "__main__":
    # Debug mode (with the Werkzeug stat reloader) must be OFF when running
    # as a LaunchAgent — the reloader fights with launchd's KeepAlive and
    # creates an unstable restart loop.  Set FLASK_DEBUG=1 to re-enable it
    # during active development.
    _debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=_debug, port=5000, threaded=True, use_reloader=_debug)
