#!/usr/bin/env bash
# setup_linux.sh - one-shot, idempotent setup for the Arduino Desktop Financial Ticker.
#
#   ./setup_linux.sh [--flash] [--fqbn arduino:avr:uno|arduino:avr:nano[:cpu=atmega328old]]
#                    [--port /dev/ttyACM0] [--service] [--no-launch] [--mock]
#
#   --flash      compile + upload ticker_firmware with arduino-cli (if installed)
#   --service    install/refresh a systemd *user* service (ticker-bridge.service)
#   --no-launch  do not start the bridge in the foreground at the end
#   --mock       launch the bridge with mock data
#   --auto N     bridge also pushes a new quote every N seconds (default: manual refresh only)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/venv"
FQBN="arduino:avr:uno"
PORT=""
DO_FLASH=0
DO_SERVICE=0
DO_LAUNCH=1
MOCK=0
AUTO=""

log()  { printf '\033[1;32m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[setup]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --flash)     DO_FLASH=1 ;;
    --service)   DO_SERVICE=1 ;;
    --no-launch) DO_LAUNCH=0 ;;
    --mock)      MOCK=1 ;;
    --fqbn)      FQBN="${2:?--fqbn needs a value}"; shift ;;
    --port)      PORT="${2:?--port needs a value}"; shift ;;
    --auto)      AUTO="${2:?--auto needs a value}"; shift ;;
    -h|--help)   sed -n '2,13p' "$0"; exit 0 ;;
    *)           die "unknown option: $1" ;;
  esac
  shift
done

# 1. serial permissions -------------------------------------------------------
if id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
  log "User $USER already in 'dialout' group"
else
  log "Adding $USER to 'dialout' group (sudo)"
  sudo usermod -a -G dialout "$USER"
  warn "Log out and back in (or run 'newgrp dialout') for the group change to apply."
fi

if dpkg -s brltty >/dev/null 2>&1; then
  warn "Package 'brltty' is installed. On Ubuntu/Zorin it can steal CH340 (clone board) serial ports."
  warn "If /dev/ttyUSB0 vanishes right after plugging in: sudo apt remove brltty"
fi

# 2. python venv ----------------------------------------------------------------
command -v python3 >/dev/null || die "python3 not found (sudo apt install python3 python3-venv)"
if [[ ! -x "${VENV}/bin/python" ]]; then
  log "Creating venv at ${VENV}"
  python3 -m venv "${VENV}" || die "venv creation failed (sudo apt install python3-venv)"
else
  log "venv already exists at ${VENV}"
fi
log "Installing/updating Python packages (requirements.txt)"
"${VENV}/bin/pip" install --quiet --upgrade pip
if [[ -f "${SCRIPT_DIR}/requirements.txt" ]]; then
  "${VENV}/bin/pip" install --quiet --upgrade -r "${SCRIPT_DIR}/requirements.txt"
else
  "${VENV}/bin/pip" install --quiet --upgrade pyserial yfinance
fi
"${VENV}/bin/python" -m py_compile "${SCRIPT_DIR}/ticker_bridge.py"

# 3. optional flashing ----------------------------------------------------------
ARDUINO_CLI="$(command -v arduino-cli || true)"
for cand in "$HOME/bin/arduino-cli" "${SCRIPT_DIR}/../bin/arduino-cli"; do
  [[ -z "$ARDUINO_CLI" && -x "$cand" ]] && ARDUINO_CLI="$cand"
done
if [[ "$DO_FLASH" -eq 1 ]]; then
  if [[ -z "$ARDUINO_CLI" ]]; then
    warn "arduino-cli not found; skipping flash (see README for install)"
  else
    log "Ensuring arduino:avr core + libraries"
    "$ARDUINO_CLI" core update-index
    "$ARDUINO_CLI" core install arduino:avr
    "$ARDUINO_CLI" lib install "Keypad" "LiquidCrystal"
    FLASH_PORT="$PORT"
    if [[ -z "$FLASH_PORT" ]]; then
      for dev in /dev/ttyACM* /dev/ttyUSB*; do
        if [[ -e "$dev" ]]; then FLASH_PORT="$dev"; break; fi
      done
    fi
    log "Compiling (${FQBN})"
    "$ARDUINO_CLI" compile --fqbn "$FQBN" "${SCRIPT_DIR}/ticker_firmware"
    if [[ -n "$FLASH_PORT" ]]; then
      log "Uploading to ${FLASH_PORT}"
      "$ARDUINO_CLI" upload --fqbn "$FQBN" -p "$FLASH_PORT" "${SCRIPT_DIR}/ticker_firmware"
    else
      warn "No board found on /dev/ttyACM*|/dev/ttyUSB*; compiled but not uploaded (use --port)"
    fi
  fi
fi

BRIDGE_ARGS=()
[[ -n "$PORT" ]] && BRIDGE_ARGS+=(--port "$PORT")
[[ "$MOCK" -eq 1 ]] && BRIDGE_ARGS+=(--mock)
[[ -n "$AUTO" ]] && BRIDGE_ARGS+=(--auto "$AUTO")

# 4. optional systemd user service ------------------------------------------------
if [[ "$DO_SERVICE" -eq 1 ]]; then
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  mkdir -p "$UNIT_DIR"
  log "Writing ${UNIT_DIR}/ticker-bridge.service"
  cat > "${UNIT_DIR}/ticker-bridge.service" <<UNIT
[Unit]
Description=Arduino Desktop Financial Ticker bridge
After=network-online.target

[Service]
ExecStart=${VENV}/bin/python ${SCRIPT_DIR}/ticker_bridge.py ${BRIDGE_ARGS[*]:-}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload
  systemctl --user enable --now ticker-bridge.service
  systemctl --user restart ticker-bridge.service
  log "Service running: journalctl --user -u ticker-bridge -f"
  DO_LAUNCH=0
fi

# 5. launch -------------------------------------------------------------------------
if [[ "$DO_LAUNCH" -eq 1 ]]; then
  log "Launching bridge (Ctrl+C to stop). Close the Arduino IDE Serial Monitor first!"
  exec "${VENV}/bin/python" "${SCRIPT_DIR}/ticker_bridge.py" "${BRIDGE_ARGS[@]}"
fi
log "Done."
