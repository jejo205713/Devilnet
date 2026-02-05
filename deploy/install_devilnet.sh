#!/usr/bin/env bash
# Automatic installer for Devilnet (Linux/macOS)
# - creates a Python virtual environment
# - installs dependencies from requirements.txt
# - trains the model once
# - prints command to start the interactive UI

set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
REQ_FILE="$REPO_ROOT/requirements.txt"
TRAIN_LOG="$REPO_ROOT/devilnet_train.log"
PYTHON_BIN="python3"

err() {
  echo "[ERROR] $1" >&2
}

info() {
  echo "[INFO] $1"
}

check_command() {
  command -v "$1" >/dev/null 2>&1 || { err "Required command '$1' not found. Please install it and retry."; exit 2; }
}

trap 'err "Installer aborted."; exit 1' ERR INT TERM

info "Starting Devilnet installer..."

# 1) Check python
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  err "$PYTHON_BIN not found. Please install Python 3.8+ and retry."
  exit 2
fi

# 2) Create venv
if [ -d "$VENV_DIR" ]; then
  info "Virtualenv already exists at $VENV_DIR"
else
  info "Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR" || { err "Failed to create virtualenv"; exit 3; }
fi

# Activate venv for this script
# shellcheck source=/dev/null
. "$VENV_DIR/bin/activate"

# 3) Install pip if needed
info "Ensuring pip is available"
python -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || { err "Failed to upgrade pip"; deactivate; exit 4; }

# 4) Ensure requirements.txt exists
if [ ! -f "$REQ_FILE" ]; then
  err "Requirements file not found at $REQ_FILE"
  deactivate
  exit 5
fi

# 5) Install requirements
info "Installing Python dependencies from $REQ_FILE"
if ! python -m pip install -r "$REQ_FILE"; then
  err "Dependency installation failed. See output above."; deactivate; exit 6
fi

# 6) Platform-specific deps
OS_NAME=$(uname -s)
if [ "$OS_NAME" = "Darwin" ]; then
  info "macOS detected"
elif [ "$OS_NAME" = "Linux" ]; then
  info "Linux detected"
fi

# 7) Run training
info "Running initial model training (this may take a few minutes). Logging to: $TRAIN_LOG"
set +e
python -m devilnet --train >"$TRAIN_LOG" 2>&1
TRAIN_RC=$?
set -e

if [ "$TRAIN_RC" -ne 0 ]; then
  err "Training failed (exit $TRAIN_RC). Check $TRAIN_LOG for details."; deactivate; exit 7
fi

info "Training completed successfully. Log: $TRAIN_LOG"

# 8) Final message / suggested run command
info "Devilnet installation finished successfully. To start the interactive UI run:"
printf "\n  %s -m devilnet --ui\n\n" "$PYTHON_BIN"

info "If you prefer headless monitoring:"
printf "  %s -m devilnet --monitor\n\n" "$PYTHON_BIN"

deactivate
info "Installer finished." 
