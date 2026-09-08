#!/bin/bash
# One agent cycle, wrapped for unattended running on a Mac mini.
#
# launchd runs this with a near-empty environment and no shell profile, which
# is the single most common reason a scheduled job "works in my terminal but
# not on a schedule". Everything it needs is therefore set explicitly here.

set -uo pipefail

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${AGENT_CONFIG:-$AGENT_DIR/config.json}"
LOG_DIR="$AGENT_DIR/logs"
LOG="$LOG_DIR/agent.log"

mkdir -p "$LOG_DIR"

# Homebrew (Apple silicon and Intel) plus the standard paths, so `python3` and
# `claude` are findable regardless of how they were installed.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

PYTHON="python3"
if [ -x "$AGENT_DIR/.venv/bin/python3" ]; then
  PYTHON="$AGENT_DIR/.venv/bin/python3"
fi

# A subshell, not a { } group: `exit` inside braces would kill this script
# before the log rotation and notification below ever ran.
(
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') starting cycle ==="
  cd "$AGENT_DIR" || exit 1
  "$PYTHON" -m business_agent.run_cycle --config "$CONFIG"
) >> "$LOG" 2>&1

status=$?
echo "=== $(date '+%Y-%m-%d %H:%M:%S') exit $status ===" >> "$LOG"

# Keep the log from growing forever on a machine nobody logs into.
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 5000000 ]; then
  tail -c 1000000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

# A visible nudge that a fresh brief is waiting. Silently skipped over SSH.
if [ "$status" -eq 0 ] && command -v osascript >/dev/null 2>&1; then
  osascript -e 'display notification "New roster brief ready" with title "Business agent"' \
    >/dev/null 2>&1 || true
fi

exit $status
