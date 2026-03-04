#!/usr/bin/env bash
# setup.sh — Prepare the environment for the Transcribe app.
#
# Checks and installs every prerequisite:
#   • Python 3.8+
#   • Homebrew (macOS package manager)
#   • ffmpeg (audio conversion, required by yt-dlp)
#   • yt-dlp (YouTube downloader)
#   • openai-whisper (transcription engine)
#   • coverage uninstalled (fixes numba crash on import)
#   • Flask and other Python requirements (requirements.txt)
#
# Safe to re-run — already-installed tools are skipped.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()    { echo -e "  ${GREEN}✔${NC}  $*"; }
info()  { echo -e "  ${CYAN}→${NC}  $*"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "  ${RED}✖${NC}  $*" >&2; }
step()  { echo -e "\n${BOLD}── $* ${NC}"; }
die()   { err "$*"; echo ""; exit 1; }

# ── Header ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       Transcribe — Environment Setup         ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"

# ── 1. macOS check ───────────────────────────────────────────────────────────
step "Platform"
if [[ "$(uname)" != "Darwin" ]]; then
    die "This app is designed for macOS. Detected: $(uname)"
fi
ok "macOS $(sw_vers -productVersion)"

# ── 2. Python 3.8+ ───────────────────────────────────────────────────────────
step "Python"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 8 ]]; then
            PYTHON="$cmd"
            ok "Python $VER  ($(command -v "$cmd"))"
            break
        else
            warn "Python $VER at $(command -v "$cmd") — need 3.8+, skipping"
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    die "Python 3.8+ not found. Install it from https://www.python.org or via Homebrew:\n\n      brew install python@3\n"
fi

# Always drive pip through the same interpreter to avoid version mismatches
run_pip() { "$PYTHON" -m pip "$@"; }

# ── 3. pip ───────────────────────────────────────────────────────────────────
step "pip"
if ! "$PYTHON" -m pip --version &>/dev/null 2>&1; then
    info "pip not found for $PYTHON — bootstrapping with ensurepip…"
    "$PYTHON" -m ensurepip --upgrade || \
        die "Could not bootstrap pip. Try: $PYTHON -m ensurepip --upgrade"
fi
PIP_VER=$("$PYTHON" -m pip --version | awk '{print $2}')
ok "pip $PIP_VER  (python -m pip)"

# ── 4. Homebrew ──────────────────────────────────────────────────────────────
step "Homebrew"

# Look in the two standard locations in case brew isn't on PATH yet
if ! command -v brew &>/dev/null; then
    for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [[ -x "$brew_path" ]]; then
            eval "$("$brew_path" shellenv)"
            break
        fi
    done
fi

if ! command -v brew &>/dev/null; then
    echo ""
    warn "Homebrew is not installed."
    echo ""
    echo -e "  Install it with:"
    echo -e "    ${CYAN}/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
    echo ""
    die "Homebrew is required (needed to install ffmpeg)."
fi

ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"

# ── 5. ffmpeg ────────────────────────────────────────────────────────────────
step "ffmpeg"
if command -v ffmpeg &>/dev/null; then
    FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    ok "already installed  (v$FFMPEG_VER)"
else
    info "Installing ffmpeg via Homebrew (this may take a minute)…"
    brew install ffmpeg
    ok "ffmpeg installed"
fi

# ── 6. yt-dlp ────────────────────────────────────────────────────────────────
step "yt-dlp"
if command -v yt-dlp &>/dev/null; then
    ok "already installed  (v$(yt-dlp --version))"
else
    info "Installing yt-dlp…"
    run_pip install --quiet yt-dlp
    ok "yt-dlp installed"
fi

# ── 7. openai-whisper ────────────────────────────────────────────────────────
step "openai-whisper"
if "$PYTHON" -c "import whisper" &>/dev/null 2>&1; then
    WHISPER_VER=$("$PYTHON" -c "import whisper; print(getattr(whisper,'__version__','?'))" 2>/dev/null || echo "?")
    ok "already installed  (v$WHISPER_VER)"
else
    info "Installing openai-whisper (downloads several packages, please wait)…"
    run_pip install --quiet openai-whisper
    ok "openai-whisper installed"
fi

# ── 8. Fix numba / coverage incompatibility ───────────────────────────────────
step "numba / coverage compatibility"
# numba 0.64+ references coverage.types.Tracer which was never added in
# coverage 7.x.  Removing coverage makes numba skip its coverage-support
# module cleanly (sets coverage_available = False internally).
if "$PYTHON" -c "import coverage" &>/dev/null 2>&1; then
    COVERAGE_VER=$("$PYTHON" -c "import coverage; print(coverage.__version__)" 2>/dev/null || echo "?")
    info "Found coverage $COVERAGE_VER — removing it to fix numba crash…"
    run_pip uninstall --quiet -y coverage 2>/dev/null || true
    ok "coverage uninstalled"
else
    ok "coverage not installed — no conflict"
fi

# Confirm numba now imports cleanly (it's pulled in by whisper/torch)
if "$PYTHON" -c "import numba" &>/dev/null 2>&1; then
    NUMBA_VER=$("$PYTHON" -c "import numba; print(numba.__version__)" 2>/dev/null || echo "?")
    ok "numba $NUMBA_VER imports cleanly"
else
    warn "numba not yet installed (will be pulled in automatically when whisper first runs)"
fi

# ── 9. Python requirements (Flask, etc.) ─────────────────────────────────────
step "Python requirements"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

if [[ ! -f "$REQUIREMENTS" ]]; then
    warn "requirements.txt not found at $REQUIREMENTS — skipping"
else
    run_pip install --quiet -r "$REQUIREMENTS"
    # Show what was installed
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Strip comments and blank lines
        pkg=$(echo "$line" | sed 's/#.*//' | xargs)
        [[ -z "$pkg" ]] && continue
        ok "$pkg"
    done < "$REQUIREMENTS"
fi

# ── 10. Final verification ────────────────────────────────────────────────────
step "Verification"
FAILED=0

check_cmd() {
    local label="$1" cmd="$2"
    if command -v "$cmd" &>/dev/null; then
        ok "$label"
    else
        err "$label — not found in PATH"
        FAILED=1
    fi
}

check_module() {
    local label="$1" mod="$2"
    if "$PYTHON" -c "import $mod" &>/dev/null 2>&1; then
        ok "$label"
    else
        err "$label — import failed"
        FAILED=1
    fi
}

check_cmd   "ffmpeg"        ffmpeg
check_cmd   "yt-dlp"        yt-dlp
check_module "whisper"      whisper
check_module "flask"        flask

if [[ "$FAILED" -ne 0 ]]; then
    echo ""
    die "One or more checks failed. See errors above and re-run this script."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║          All checks passed!  ✔               ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Start the app with one of these commands:"
echo ""
echo -e "  ${CYAN}Option A${NC}  Auto-start on every login (recommended, run once):"
echo -e "            ${BOLD}python install_service.py${NC}"
echo ""
echo -e "  ${CYAN}Option B${NC}  On-demand (start + open browser):"
echo -e "            ${BOLD}python launch.py${NC}"
echo ""
echo -e "  ${CYAN}Option C${NC}  Manual:"
echo -e "            ${BOLD}python app.py${NC}"
echo ""
