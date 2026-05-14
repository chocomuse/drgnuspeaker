#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
  python3-venv \
  python3-pip \
  libportaudio2 \
  libsndfile1 \
  alsa-utils \
  speech-dispatcher \
  unzip \
  wget
