#!/bin/bash
#
# FaceFusion · Simple Face Swap — one double-click launcher for macOS.
#
# The first run installs everything and downloads the app automatically.
# Every run after that just starts the app and opens it in your browser.
# You never have to type anything.
#

REPO_URL="https://github.com/theguroos/facefusion.git"
BRANCH="claude/gallant-cray-nc8a2v"
REPO_DIR="$HOME/facefusion"
PORT=7870

# If anything fails, keep this window open so the message stays readable.
on_error() {
	echo ""
	echo "------------------------------------------------------------------"
	echo "  Something went wrong above — nothing on your Mac was harmed."
	echo "  Copy the last few lines and send them to Claude to fix it."
	echo "------------------------------------------------------------------"
	read -r -p "  Press Return to close this window… " _
}
trap on_error ERR
set -e

clear
echo "=================================================="
echo "   FaceFusion · Simple Face Swap"
echo "   Getting things ready — this is automatic."
echo "=================================================="
echo ""

# 1) Homebrew — the standard installer for Mac software.
if ! command -v brew >/dev/null 2>&1; then
	echo "▸ Installing Homebrew (one-time; it may ask for your Mac password)…"
	NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
# Make brew usable in this window (works on both Apple Silicon and Intel Macs).
[ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
[ -x /usr/local/bin/brew ] && eval "$(/usr/local/bin/brew shellenv)"

# 2) The three tools the app needs: Python, ffmpeg (video), git (download).
command -v python3 >/dev/null 2>&1 || { echo "▸ Installing Python…"; brew install python; }
command -v ffmpeg  >/dev/null 2>&1 || { echo "▸ Installing ffmpeg…"; brew install ffmpeg; }
command -v git     >/dev/null 2>&1 || { echo "▸ Installing git…"; brew install git; }

# 3) Download (or update) the app itself.
if [ ! -d "$REPO_DIR/.git" ]; then
	echo "▸ Downloading the app to $REPO_DIR …"
	echo "  (If it asks you to sign in to GitHub, do so — it's your own repo.)"
	git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"
echo "▸ Updating to the latest version…"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH" || true

# 4) A private Python environment + the app's dependencies.
if [ ! -d venv ]; then
	echo "▸ Creating a Python environment…"
	python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo "▸ Installing dependencies (quick after the first time)…"
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r requirements.txt

# 5) Start the app and open it in the browser.
echo ""
echo "=================================================="
echo "   Starting the app…"
echo "   Your browser will open at http://127.0.0.1:$PORT"
echo ""
echo "   The FIRST face swap downloads the AI models"
echo "   (about 1.4 GB) — that one is slow, the rest are fast."
echo ""
echo "   Keep this window open while you use the app."
echo "   Close it (or press Ctrl+C) when you're done."
echo "=================================================="
echo ""

python3 swap_app.py --no-browser --port "$PORT" &
APP_PID=$!

# Wait until the app is actually serving, then open the browser.
for _ in $(seq 1 90); do
	if curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then break; fi
	sleep 1
done
open "http://127.0.0.1:$PORT/" || true

trap - ERR
wait "$APP_PID"
