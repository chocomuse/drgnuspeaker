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

## Pair With The Android App

### Option A: Nearby Speaker Discovery

This is the recommended screenless setup path. The speaker advertises itself on the local Wi-Fi network through mDNS:

```text
_drgnu-speaker._tcp.local.
```

Keep this enabled in `.env`:

```env
DRGNU_LOCAL_PAIRING_ENABLED=true
DRGNU_LOCAL_PAIRING_PORT=8765
```

Then open the Android app:

```text
Manage -> AI Speaker -> Link AI speaker -> Find nearby speaker
```

Select the discovered speaker and tap `Link found speaker`. The Android app sends the logged-in user info to the speaker over local Wi-Fi, and the speaker asks the backend to link `device_id` to that user.

Backend endpoint required:

```text
POST /api/devices/link-local
```

### Option B: Spoken Pairing Code

When `DRGNU_PAIRING_ENABLED=true` and no device token exists, the speaker calls:

```text
POST /api/devices/pairing-code
```

It reads the pairing code aloud, then polls:

```text
POST /api/devices/pairing-status
```

In the Android app, open:

```text
Manage -> AI Speaker -> Link AI speaker
```

Enter the spoken pairing code. Once the backend returns `device_access_token`, the speaker saves it to `.device-token` and uses it for later analysis calls.

For backend pairing, set:

```env
DRGNU_PAIRING_ENABLED=true
```

## Run In Development

```bash
python -m drgnu_speaker.main
```

The default `DRGNU_WAKE_MODE=keyboard` waits for Enter instead of a real wake word. This is useful while testing on a desktop or before the wake word model is trained.

## App-Controlled Speaker Settings

After pairing, the Android app can manage basic speaker settings through the backend:

- speaker name
- TTS on/off
- microphone mute on/off
- recording length

The Jetson polls:

```text
GET {DRGNU_BASE_URL}/api/devices/{DRGNU_DEVICE_ID}/settings
```

and applies the returned settings while it is running. Configure polling with:

```env
DRGNU_SETTINGS_SYNC_ENABLED=true
DRGNU_SETTINGS_SYNC_SECONDS=30
```

Expected response:

```json
{
  "settings": {
    "device_name": "Living Room Jinu",
    "wake_mode": "phrase",
    "record_seconds": 7,
    "tts_enabled": true,
    "mic_muted": false,
    "local_pairing_enabled": true,
    "active_voice_profile_id": "vp_123"
  }
}
```

When `active_voice_profile_id` is present, the Jetson includes it in `POST /api/stt-analyze` so the backend can use the selected user's voice profile to improve STT recognition.

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

After the app runs manually, install the systemd autostart service:

```bash
cd jetson_speaker
chmod +x scripts/install_autostart.sh
./scripts/install_autostart.sh
```

The installer detects the current folder and Linux user, writes `/etc/systemd/system/drgnu-speaker.service`, enables it, and starts it immediately.

Check the service:

```bash
sudo systemctl status drgnu-speaker
```

Watch logs:

```bash
journalctl -u drgnu-speaker -f
```

After this, the speaker starts automatically whenever the Jetson Nano boots. Make sure Wi-Fi, microphone, speaker output, `.env`, and `.venv` are already configured before installing autostart.

To disable boot autostart:

```bash
chmod +x scripts/uninstall_autostart.sh
./scripts/uninstall_autostart.sh
```

If you prefer manual setup, copy `systemd/drgnu-speaker.service` to `/etc/systemd/system/` and adjust `User=`, `WorkingDirectory=`, `EnvironmentFile=`, and `ExecStart=` for your Jetson path.

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
  voice_profile_id: optional voice profile id
```

It accepts the same broad response fields used by the Android app:

- `answer`, `response`, or `ai_answer`
- `session_score`, `score_total`, or `total_score`
- `risk`, `risk_level`, or `riskStatus`
- `reason`
