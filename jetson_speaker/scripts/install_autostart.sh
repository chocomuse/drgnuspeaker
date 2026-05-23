#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="drgnu-speaker"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_USER="${SUDO_USER:-$(id -un)}"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
ENV_FILE="${PROJECT_DIR}/.env"

if [ ! -f "${PYTHON_BIN}" ]; then
  echo "[drgnu-speaker] missing virtualenv python: ${PYTHON_BIN}"
  echo "Run this first:"
  echo "  cd ${PROJECT_DIR}"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "[drgnu-speaker] missing .env file: ${ENV_FILE}"
  echo "Run this first:"
  echo "  cd ${PROJECT_DIR}"
  echo "  cp .env.example .env"
  echo "  nano .env"
  exit 1
fi

echo "[drgnu-speaker] installing systemd service"
echo "  user: ${RUN_USER}"
echo "  project: ${PROJECT_DIR}"
echo "  env: ${ENV_FILE}"

sudo tee "${SERVICE_PATH}" >/dev/null <<SERVICE
[Unit]
Description=Drgnu Jetson AI Speaker
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
Environment=PYTHONUNBUFFERED=1
Environment=PATH=${PROJECT_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${PYTHON_BIN} -m drgnu_speaker.main
Restart=always
RestartSec=5
SupplementaryGroups=audio

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "[drgnu-speaker] autostart enabled"
echo "Check status:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "Watch logs:"
echo "  journalctl -u ${SERVICE_NAME} -f"
