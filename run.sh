#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"
REQUIREMENTS="requirements.txt"

# --- Usage ---
if [[ $# -lt 1 ]]; then
  echo "Usage: ./run.sh <TICKER> [extra args...]"
  echo "  e.g. ./run.sh RELIANCE.NS"
  echo "  e.g. ./run.sh RELIANCE.NS --output report.csv"
  exit 1
fi

# --- Virtual env ---
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[setup] Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# --- Install / sync dependencies ---
echo "[setup] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$REQUIREMENTS"

# --- Run screener ---
_SUBCOMMANDS="screen|scan|sync-sheet|clear-cache|version"
if [[ "$1" =~ ^(scan|sync-sheet|clear-cache|version)$ ]]; then
  echo "[run] Running $1..."
  echo "---"
  python -m screener "$@"
else
  echo "[run] Screening $1..."
  echo "---"
  python -m screener screen "$@"
fi
