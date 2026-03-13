#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  J.A.R.V.I.S. Setup — Always-On Background Service
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  After running this script JARVIS starts automatically
#  on every login. Just double-clap or say "Hey Jarvis."
#  You never need to open a terminal again.
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PARENT_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
PLIST_NAME="com.bigbrodie.jarvis"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
JARVIS_HOME="$HOME/.jarvis"

echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   J.A.R.V.I.S. — Always-On Setup"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Ensure venv exists ──────────────────────────
echo "  [1/4] Checking Python environment..."
if [ ! -f "$VENV_PYTHON" ]; then
    echo "  ⟫ Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi
echo "  ✓ Using Python: $VENV_PYTHON"
echo ""

# ── Step 2: Install dependencies ────────────────────────
echo "  [2/4] Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet 2>/dev/null || true
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet 2>/dev/null || \
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

if command -v brew &> /dev/null; then
    brew install portaudio 2>/dev/null || true
    "$VENV_DIR/bin/pip" install pyaudio 2>/dev/null && \
        echo "  ✓ PyAudio installed (real-time mic)" || \
        echo "  ⚠ PyAudio skipped (sounddevice fallback works fine)"
fi
echo "  ✓ All dependencies ready"
echo ""

# ── Step 3: Run first-time setup if needed ──────────────
echo "  [3/4] Configuration..."
if [ ! -f "$JARVIS_HOME/config.json" ]; then
    "$VENV_PYTHON" "$SCRIPT_DIR/Jarvis.py" --setup
else
    echo "  ✓ Config already exists at $JARVIS_HOME/config.json"
fi
echo ""

# ── Step 4: Install macOS LaunchAgent ───────────────────
echo "  [4/4] Installing always-on background service..."
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$JARVIS_HOME"

# Stop any existing instance
launchctl stop "$PLIST_NAME" 2>/dev/null || true
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Kill any leftover JARVIS processes
pkill -f "Jarvis.py --daemon" 2>/dev/null || true
sleep 1

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PYTHON}</string>
        <string>${SCRIPT_DIR}/Jarvis.py</string>
        <string>--daemon</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>${JARVIS_HOME}/daemon-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${JARVIS_HOME}/daemon-stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:${VENV_DIR}/bin</string>
        <key>VIRTUAL_ENV</key>
        <string>${VENV_DIR}</string>
    </dict>
</dict>
</plist>
PLIST

launchctl load "$PLIST_PATH"
launchctl start "$PLIST_NAME"

sleep 2
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "  ✓ Background service installed and running"
else
    echo "  ⚠ Service installed but may need a logout/login to start"
fi

echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   J.A.R.V.I.S. is LIVE"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  JARVIS is now running in the background."
echo "  It starts automatically every time you log in."
echo ""
echo "  Wake him up:"
echo "    *clap* *clap*     — Double-clap (like Tony Stark)"
echo "    \"Hey Jarvis\"      — Voice wake word"
echo "    \"Wake Up\"         — Voice wake word"
echo ""
echo "  Management:"
echo "    Stop:      launchctl stop $PLIST_NAME"
echo "    Start:     launchctl start $PLIST_NAME"
echo "    Restart:   launchctl kickstart -k gui/\$(id -u)/$PLIST_NAME"
echo "    Uninstall: launchctl unload $PLIST_PATH && rm $PLIST_PATH"
echo "    Logs:      tail -f ~/.jarvis/jarvis.log"
echo "    Config:    python3 Jarvis.py --setup"
echo ""
echo "  Interactive mode (instead of background):"
echo "    source \"$VENV_DIR/bin/activate\" && python3 Jarvis.py"
echo ""
