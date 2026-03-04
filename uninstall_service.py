#!/usr/bin/env python3
"""
Remove the Transcribe LaunchAgent.

Stops the server and disables auto-start on login.
The project files are left untouched.

Usage:
    python uninstall_service.py
"""

import subprocess
import sys
from pathlib import Path

LABEL = "com.transcribe.app"


def main() -> None:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    if not plist_path.exists():
        print("Service is not installed — nothing to do.")
        return

    result = subprocess.run(
        ["launchctl", "unload", "-w", str(plist_path)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("Service stopped.")
    else:
        print(f"launchctl unload: {result.stderr.strip()}")

    plist_path.unlink()
    print(f"Removed {plist_path}")
    print()
    print("Auto-start disabled.")
    print("You can still start the app manually with:  python launch.py")


if __name__ == "__main__":
    main()
