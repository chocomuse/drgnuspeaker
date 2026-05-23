#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="drgnu-speaker"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

sudo systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
sudo systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
sudo rm -f "${SERVICE_PATH}"
sudo systemctl daemon-reload

echo "[drgnu-speaker] autostart disabled"
