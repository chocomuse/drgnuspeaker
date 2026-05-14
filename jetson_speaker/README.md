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

## Enable Phrase Wake Detection

The first real wake mode uses Vosk offline speech recognition with a Korean model. It listens for the default phrases:

- `jinuya` / Korean "Jinuya"
- `jinwoo-ya` / Korean "Jinwoo-ya"
- `hey jinu`
- `hey ginu`

Install the model on the Jetson:

```bash
cd jetson_speaker
./scripts/download_vosk_ko_model.sh
```

Then edit `.env`:

```env
DRGNU_WAKE_MODE=phrase
DRGNU_WAKE_MODEL_PATH=models/vosk-model-small-ko-0.22
```

Run:

```bash
python -m drgnu_speaker.main
```

When the terminal shows:

```text
[drgnu-speaker] listening for wake phrase
```

say `jinuya` or `hey jinu`. If it matches, the speaker says the ready prompt and starts recording the actual user request.

You can override phrases with `DRGNU_WAKE_PHRASES`, separated by commas. Leave it unset to use the built-in Korean and romanized defaults.

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
2. Use `phrase` mode with Vosk for the first always-listening prototype.
3. Add a physical button mode for reliable hardware fallback.
4. Train or integrate a dedicated wake word engine such as openWakeWord or Porcupine.
5. Route wake events into `WakeDetector.wait_for_wake()`.

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
