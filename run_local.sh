#!/usr/bin/env bash
set -euo pipefail

FRONTEND_PORT=5500
BACKEND_PORT=8000

while getopts ":f:b:h" opt; do
  case "$opt" in
    f) FRONTEND_PORT="$OPTARG" ;;
    b) BACKEND_PORT="$OPTARG" ;;
    h) echo "Usage: $0 [-f FRONTEND_PORT] [-b BACKEND_PORT]"; exit 0 ;;
    *) exit 1 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

os_name() {
  case "$(uname -s)" in
    Darwin) echo "mac" ;;
    Linux) echo "linux" ;;
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
    *) echo "unknown" ;;
  esac
}

assert_command() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 1; }; }

echo "Repo: $REPO"
echo "Using:"
echo "  RabbitMQ: localhost:5672 (UI http://localhost:15672 test/test)"
echo "  Backend : http://127.0.0.1:${BACKEND_PORT}"
echo "  Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo

START_TERM() {
  local title="$1"
  local workdir="$2"
  local cmd="$3"
  local os; os="$(os_name)"

  if [[ "$os" == "windows" ]]; then
    assert_command powershell.exe
    assert_command cygpath
    local workdir_w venv_w
    workdir_w="$(cygpath -w "$workdir")"
    venv_w="$(cygpath -w "$REPO/.venv/Scripts/Activate.ps1")"

    local ps_cmd="& { Set-Location -LiteralPath '$workdir_w'; if (Test-Path -LiteralPath '$venv_w') { . '$venv_w' }; $cmd }"
    powershell.exe -NoProfile -Command "Start-Process powershell -WindowStyle Normal -ArgumentList '-NoExit','-Command',\"$ps_cmd\""
    return
  fi

  if [[ "$os" == "mac" ]]; then
    assert_command osascript
    # venv on mac/linux:
    local wrapped="cd \"$workdir\"; if [ -f \"$REPO/.venv/bin/activate\" ]; then source \"$REPO/.venv/bin/activate\"; fi; $cmd"

    # --- FIX START ---
    # Escape backslashes and double quotes so AppleScript accepts the string
    local esc_wrapped="${wrapped//\\/\\\\}"
    esc_wrapped="${esc_wrapped//\"/\\\"}"

    osascript <<EOF
tell application "Terminal"
  do script "$esc_wrapped"
  set custom title of front window to "$title"
  activate
end tell
EOF
    # --- FIX END ---

#     osascript <<EOF
# tell application "Terminal"
#   do script $(printf "%q" "$wrapped")
#   set custom title of front window to "$title"
#   activate
# end tell
# EOF
    return
  fi

  # linux terminals (best effort)
  local wrapped="cd \"$workdir\"; if [ -f \"$REPO/.venv/bin/activate\" ]; then source \"$REPO/.venv/bin/activate\"; fi; $cmd; exec bash"
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --title="$title" -- bash -lc "$wrapped" >/dev/null 2>&1 &
  elif command -v konsole >/dev/null 2>&1; then
    konsole --new-tab -p tabtitle="$title" -e bash -lc "$wrapped" >/dev/null 2>&1 &
  elif command -v xterm >/dev/null 2>&1; then
    xterm -T "$title" -e bash -lc "$wrapped" >/dev/null 2>&1 &
  else
    echo "No terminal emulator found; running in background: $title" >&2
    ( bash -lc "$wrapped" ) &
  fi
}

# Commands per OS
OS="$(os_name)"
assert_command docker

if [[ "$OS" == "windows" ]]; then
  assert_command py
  BACKEND_CMD="py -m uv run --active social-api"
  FRONTEND_CMD="py -m http.server ${FRONTEND_PORT}"
else
  assert_command python3
  BACKEND_CMD="python3 -m uv run --active social-api"
  FRONTEND_CMD="python3 -m http.server ${FRONTEND_PORT}"
fi

# RabbitMQ: ohne -it ist es robuster (keine TTY-Probleme)
RABBIT_CMD="docker run --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management"

START_TERM "RabbitMQ"      "$REPO"           "$RABBIT_CMD"
START_TERM "Backend"       "$REPO/backend"   "$BACKEND_CMD"
START_TERM "Image-Resizer" "$REPO"           "social-resizer"
START_TERM "Frontend"      "$REPO/frontend"  "$FRONTEND_CMD"

echo "✅ Started all services."
