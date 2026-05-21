#!/bin/bash
# claude-awake.sh — run Claude Code under caffeinate (Mac stays awake until session exits)
#
# Flags:
#   -i  prevent idle sleep
#   -d  prevent display sleep
#   -m  prevent disk idle sleep
#
# Usage:
#   ./claude-awake.sh                          # interactive claude
#   ./claude-awake.sh -p "task"                # one-shot
#   ./claude-awake.sh --channels plugin:imessage@claude-plugins-official
#   ./claude-awake.sh /path/to/claude-alert.sh -p "task"   # alert + no-sleep

set -euo pipefail

CLAUDE_BIN="${CLAUDE_BIN:-/opt/homebrew/bin/claude}"

if [[ $# -eq 0 ]]; then
  exec caffeinate -idm "$CLAUDE_BIN"
fi

# Wrapper script as first arg (e.g. claude-alert.sh)
if [[ -x "$1" ]] && [[ "$1" == *claude* ]]; then
  exec caffeinate -idm "$@"
fi

exec caffeinate -idm "$CLAUDE_BIN" "$@"
