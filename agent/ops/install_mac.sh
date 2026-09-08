#!/bin/bash
# Install the agent as a scheduled job on a Mac (mini or otherwise).
#
#   ./ops/install_mac.sh            # install / reinstall
#   ./ops/install_mac.sh --uninstall
#
# Everything here is reversible and stays in your user account -- no sudo,
# no system-wide daemons.

set -euo pipefail

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.business.agent"
PLIST_SRC="$AGENT_DIR/ops/com.business.agent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "Uninstalled $LABEL. Nothing is scheduled any more."
  exit 0
fi

if [ ! -f "$AGENT_DIR/config.json" ]; then
  echo "No config.json yet. Copy config.example.json to config.json and fill it in first." >&2
  exit 1
fi

echo "Checking the agent runs at all before scheduling it..."
if ! bash "$AGENT_DIR/ops/run_cycle.sh"; then
  echo "The agent failed on a manual run -- fix that before scheduling it." >&2
  echo "See $AGENT_DIR/logs/agent.log" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$AGENT_DIR/logs"
sed "s|__AGENT_DIR__|$AGENT_DIR|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST_DST"
launchctl enable "$DOMAIN/$LABEL"

cat <<SUMMARY

Installed. The agent now runs at 7am, midday and 5pm.

  Run it right now:     launchctl kickstart -k $DOMAIN/$LABEL
  Check it is loaded:   launchctl print $DOMAIN/$LABEL | head -20
  Watch what it does:   tail -f $AGENT_DIR/logs/agent.log
  Read the latest:      open $AGENT_DIR/out/latest_brief.md
  Stop it:              ./ops/install_mac.sh --uninstall

One more thing on a Mac mini you never log into: System Settings ->
Energy, turn OFF "Put hard disks to sleep" and turn ON "Start up
automatically after a power failure". A sleeping Mac runs no agents.
SUMMARY
