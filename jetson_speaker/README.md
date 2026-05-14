# Drgnu Jetson AI Speaker

Headless Jetson Nano client for a Drgnu-style AI speaker.

The first MVP flow is:

1. Wait for an activation event.
2. Play a short ready prompt.
3. Record the user's voice.
4. Upload the audio to the existing Drgnu analysis API.
5. Read the answer and score aloud through local TTS.

The client is intentionally small and pluggable. Wake word, LED, STT, and TTS can be swapped without changing the server contract.

## Hardware Target

- Jetson Nano running Ubuntu
- USB microphone or USB microphone array
- Speaker through USB, 3.5 mm, HDMI audio, or Bluetooth
- Optional button for mute/pairing
- Optional RGB LED for state feedback

## Install

```bash
cd jetson_speaker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

- `DRGNU_BASE_URL`
- `DRGNU_API_KEY`
- `DRGNU_DEVICE_ID`
- `DRGNU_SESSION_ID`

## Run In Development

```bash
python -m drgnu_speaker.main
```

The default `DRGNU_WAKE_MODE=keyboard` waits for Enter instead of a real wake word. This is useful while testing on a desktop or before the wake word model is trained.

## Run On Boot

Copy the systemd unit:

```bash
sudo cp systemd/drgnu-speaker.service /etc/systemd/system/drgnu-speaker.service
sudo systemctl daemon-reload
sudo systemctl enable drgnu-speaker
sudo systemctl start drgnu-speaker
```

Adjust paths and the `User=` value in the unit file for your Jetson user.

## Wake Word Roadmap

The custom phrases are:

- `jinuya`
- `hey jinu`

Recommended production path:

1. Start with `keyboard` mode for API and audio validation.
2. Add a physical button mode for reliable early prototypes.
3. Train or integrate a wake word engine such as openWakeWord or Porcupine.
4. Route wake events into `WakeDetector.wait_for_wake()`.

## Server Contract

The client currently posts multipart audio to:

```text
POST {DRGNU_BASE_URL}/api/stt-analyze
Header: X-API-Key: {DRGNU_API_KEY}
Fields:
  audio: wav file
  audiostt_result: wav file
  device_id: string
  session_id: string
```

It accepts the same broad response fields used by the Android app:

- `answer`, `response`, or `ai_answer`
- `session_score`, `score_total`, or `total_score`
- `risk`, `risk_level`, or `riskStatus`
- `reason`

