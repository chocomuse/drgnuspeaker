#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=================================================="
echo "        Drgnu Jetson Speaker Client"
echo "=================================================="
echo

if [ -f ".venv/bin/activate" ]; then
  echo "[INFO] Activating virtual environment..."
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
else
  echo "[WARN] Virtual environment not found at ${SCRIPT_DIR}/.venv"
  echo "       Run ./scripts/setup_jetson.sh first, or create it manually."
fi

if [ ! -f ".env" ]; then
  echo "[ERROR] Missing .env file."
  echo "        Copy .env.example to .env and edit it for this Jetson Nano."
  exit 1
fi

echo "[INFO] Starting Speaker Client..."
exec python -m drgnu_speaker.main
