#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="vosk-model-small-ko-0.22"
MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODEL_DIR="${PROJECT_DIR}/models"
ZIP_PATH="${MODEL_DIR}/${MODEL_NAME}.zip"

mkdir -p "${MODEL_DIR}"

if [ -d "${MODEL_DIR}/${MODEL_NAME}" ]; then
  echo "${MODEL_NAME} already exists at ${MODEL_DIR}/${MODEL_NAME}"
  exit 0
fi

echo "Downloading ${MODEL_URL}"
wget -O "${ZIP_PATH}" "${MODEL_URL}"
unzip "${ZIP_PATH}" -d "${MODEL_DIR}"
rm -f "${ZIP_PATH}"
echo "Installed ${MODEL_DIR}/${MODEL_NAME}"
