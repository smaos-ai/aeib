#!/bin/bash
# claude-alert.sh — Run Claude with sound + desktop notification on HITL/permission/input pause
# Usage: claude-alert.sh [claude args]
# Pairs with: set -g bell-action any (tmux config)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect OS for audio playback
OS="$(uname -s)"
AUDIO_PLAY=""

case "$OS" in
  Darwin)
    AUDIO_PLAY="afplay"
    ;;
  Linux)
    AUDIO_PLAY="paplay"
    ;;
  *)
    AUDIO_PLAY="" # Graceful fallback
    ;;
esac

# Glass ding sound (base64-encoded WAV, ~100ms)
# Fallback: printf '\a' if audio fails or OS unsupported
play_alert() {
  if command -v "$AUDIO_PLAY" &>/dev/null; then
    # Try to play glass ding via system audio (bypasses muted terminal)
    if [[ "$OS" == "Darwin" ]]; then
      afplay /System/Library/Sounds/Glass.aiff 2>/dev/null || printf '\a'
    elif [[ "$OS" == "Linux" ]]; then
      paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null || printf '\a'
    fi
  else
    # Fallback: terminal bell (respects terminal settings, but may be silent)
    printf '\a'
  fi
}

# Send desktop notification (macOS + Linux)
notify_desktop() {
  local title="$1"
  local message="$2"

  if [[ "$OS" == "Darwin" ]]; then
    osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
  elif [[ "$OS" == "Linux" ]]; then
    if command -v notify-send &>/dev/null; then
      notify-send "$title" "$message" 2>/dev/null || true
    fi
  fi
}

# Pattern matching: detect HITL, permissions, input requests
detect_pause_patterns() {
  local line="$1"

  # Explicit pause triggers (Claude uses these for HITL)
  if [[ "$line" =~ "permission prompt" ]] || \
     [[ "$line" =~ "Approve\?" ]] || \
     [[ "$line" =~ "Confirm before" ]] || \
     [[ "$line" =~ "Use this tool" ]] || \
     [[ "$line" =~ "Deny\?" ]] || \
     [[ "$line" =~ "Permission" ]] || \
     [[ "$line" =~ "approve\|deny" ]] || \
     [[ "$line" =~ "Send notification" ]]; then
    return 0  # Match found
  fi
  return 1  # No match
}

# Main: Run Claude with alert wrapping
main() {
  echo -e "${GREEN}[claude-alert]${NC} Starting Claude with alert detection..."

  # Run Claude in raw TTY mode, capture output, detect pauses
  # Using script -q to suppress script overhead on raw TTY
  script -q /dev/null claude "$@" 2>&1 | while IFS= read -r line; do
    echo "$line"

    # Detect pause patterns and trigger alert
    if detect_pause_patterns "$line"; then
      echo -e "${YELLOW}[claude-alert]${NC} HITL/permission detected!"
      play_alert
      notify_desktop "Claude Input Needed" "$(echo "$line" | head -c 80)..."
    fi
  done &

  # Disown the background process
  disown

  echo -e "${GREEN}[claude-alert]${NC} Claude running in background. You'll hear a ding on input pause."
}

# Hook mode: Notification / Stop / TaskCompleted (no claude args)
if [[ $# -eq 0 ]]; then
  title="Claude"
  message="Check terminal — your input may be needed"
  if command -v jq &>/dev/null; then
    json="$(cat 2>/dev/null || true)"
    if [[ -n "$json" ]]; then
      title="$(echo "$json" | jq -r '.title // .notification_type // "Claude"' 2>/dev/null | head -1)"
      message="$(echo "$json" | jq -r '.message // "Check terminal"' 2>/dev/null | head -c 120)"
    fi
  fi
  play_alert
  notify_desktop "$title" "$message"
  exit 0
fi

main "$@"
