#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

echo "[drgnu-speaker] Installing Ubuntu packages..."
chmod +x scripts/install_ubuntu_deps.sh
./scripts/install_ubuntu_deps.sh

echo "[drgnu-speaker] Creating Python virtual environment..."
python3 -m venv .venv

echo "[drgnu-speaker] Installing Python requirements..."
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[drgnu-speaker] Creating .env from .env.example..."
  cp .env.example .env
fi

chmod +x run_speaker.sh

echo
echo "[drgnu-speaker] Setup complete."
echo "Next steps:"
echo "  1. Copy your Google service account JSON to this Jetson."
echo "  2. Edit .env and set DRGNU_API_KEY and DRGNU_GOOGLE_SERVICE_ACCOUNT_JSON."
echo "  3. Run: ./run_speaker.sh"
echo "  4. After manual testing works, run: ./scripts/install_autostart.sh"
