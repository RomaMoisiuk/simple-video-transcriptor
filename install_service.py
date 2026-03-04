#!/usr/bin/env python3
"""
Install the Transcribe server as a macOS LaunchAgent.

Run this script ONCE.  The Flask server will then start automatically
every time you log in.  You can open http://27.0.0.1:5000 (or the
index.html file directly) without ever touching a terminal again.

Usage:
    python install_service.py      # install, start, open browser
    python uninstall_service.py    # stop and remove
"""

import os
import sys
import time
import plistlib
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

LABEL = "com.transcribe.app"
PORT  = 5000
# Use 127.0.0.1 explicitly — on modern macOS "27.0.0.1" can resolve to ::1
# (IPv6) while Flask binds to 127.0.0.1 (IPv4), causing spurious failures.
HEALTH_URL = f"http://127.0.0.1:{PORT}/health"
OPEN_URL   = f"http://27.0.0.1:{PORT}"


def server_up() -> bool:
    try:
        urllib.request.urlopen(HEALTH_URL, timeout=1)
        return True
    except Exception:
        return False


def main() -> None:
    script_dir = Path(__file__).parent.resolve()
    app_py     = script_dir / "app.py"
    python     = sys.executable
    log_file   = script_dir / "server.log"

    if not app_py.exists():
        print(f"ERROR: app.py not found at {app_py}")
        sys.exit(1)

    # ── Build the LaunchAgent plist ───────────────────────────────────
    plist_data = {
        "Label": LABEL,
        "ProgramArguments": [python, str(app_py)],
        # Inherit PATH so yt-dlp / whisper are found; disable the Werkzeug
        # stat reloader so launchd's KeepAlive doesn't fight with it.
        "EnvironmentVariables": {
            "PATH":         os.environ.get(
                "PATH",
                "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            ),
            "FLASK_DEBUG":  "0",
        },
        "WorkingDirectory": str(script_dir),
        "RunAtLoad":  True,   # start immediately when loaded
        "KeepAlive":  True,   # restart automatically if it crashes
        "StandardOutPath":  str(log_file),
        "StandardErrorPath": str(log_file),
    }

    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = agents_dir / f"{LABEL}.plist"

    with open(plist_path, "wb") as fh:
        plistlib.dump(plist_data, fh)

    print(f"Plist written → {plist_path}")

    # ── Load the service (unload first in case it was already installed) ──
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)

    result = subprocess.run(
        ["launchctl", "load", "-w", str(plist_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Non-fatal: print the warning but keep going
        print(f"launchctl: {result.stderr.strip()}")

    # ── Wait for the server to be ready ──────────────────────────────
    print("Waiting for server to start", end="", flush=True)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        time.sleep(0.5)
        print(".", end="", flush=True)
        if server_up():
            print(" ready!")
            break
    else:
        print()
        print(f"\nServer did not respond within 20 s.")
        print(f"Check the log for errors: {log_file}")
        sys.exit(1)

    webbrowser.open(OPEN_URL)

    print()
    print("═" * 56)
    print("  Transcribe service installed successfully!")
    print("═" * 56)
    print(f"  URL:       {OPEN_URL}")
    print(f"  Log:       {log_file}")
    print(f"  Auto-start: yes (runs on every login)")
    print()
    print("  You can now open  templates/index.html  directly")
    print("  in your browser — no terminal needed.")
    print()
    print("  To uninstall:  python uninstall_service.py")
    print("═" * 56)


if __name__ == "__main__":
    main()
