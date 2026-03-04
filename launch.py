#!/usr/bin/env python3
"""
Launch the Transcribe app.

Checks whether the Flask server is already running on the configured port.
If it is not, starts it as a background process, waits until it is ready,
then opens http://localhost:<PORT> in the default browser.
"""

import os
import sys
import time
import subprocess
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path

PORT       = 5000
HEALTH_URL = f"http://127.0.0.1:{PORT}/health"  # explicit IPv4, avoids macOS IPv6 resolution
OPEN_URL   = f"http://localhost:{PORT}"
TIMEOUT    = 15   # seconds to wait for the server to become ready


def server_up() -> bool:
    try:
        urllib.request.urlopen(HEALTH_URL, timeout=1)
        return True
    except Exception:
        return False


def main() -> None:
    if server_up():
        print(f"Server is already running → opening {OPEN_URL}")
        webbrowser.open(OPEN_URL)
        return

    print("Starting server…")
    app_script = Path(__file__).parent / "app.py"

    # Start Flask as a detached background process so this launcher can exit
    proc = subprocess.Popen(
        [sys.executable, str(app_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Keep the child alive after this script exits
        close_fds=True,
    )

    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(0.4)
        if server_up():
            print(f"Server ready → opening {OPEN_URL}")
            webbrowser.open(OPEN_URL)
            return
        if proc.poll() is not None:
            print("Server process exited unexpectedly. Try running:  python app.py")
            sys.exit(1)

    print(
        f"Server did not become ready within {TIMEOUT}s.  "
        "Try running manually:  python app.py"
    )
    proc.terminate()
    sys.exit(1)


if __name__ == "__main__":
    main()
