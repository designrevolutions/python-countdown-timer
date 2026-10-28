#!/usr/bin/env bash
# Launch timer.py detached from the terminal (Linux equivalent of pythonw on Windows).
# The process runs in the background with no console output and the terminal
# is returned immediately for other use.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON="python3"
fi

nohup "$PYTHON" "$SCRIPT_DIR/timer.py" "$@" >/dev/null 2>&1 &
disown
