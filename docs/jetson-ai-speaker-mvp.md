# Jetson AI Speaker MVP Plan

## Goal

Build a headless AI speaker that reacts to "jinuya" or "hey jinu", records speech, sends it to the Drgnu server, and reads the answer plus health/status score aloud. The mobile app and web dashboard should show the same account-linked history and scores.

## Phase 1: Local Device Loop

- Jetson runs `jetson_speaker`.
- Development activation uses Enter or a push-to-talk button.
- Audio is recorded as 16 kHz mono WAV.
- The device posts audio to `POST /api/stt-analyze`.
- The server response is read aloud through Ubuntu TTS.

## Phase 2: Account And Device Pairing

Required backend objects:

- `users`
- `devices`
- `device_pairing_codes`
- `analysis_sessions`
- `speaker_events`

Recommended pairing flow:

1. Jetson boots without an account.
2. Jetson says a short pairing code aloud.
3. User logs into the Android app or web app.
4. User enters the pairing code.
5. Server binds `device_id` to `user_id`.
6. Jetson receives a device token and stores it locally.

## Phase 3: Real Wake Word

Use a wake detector behind the `WakeDetector` interface.

Recommended path:

- Prototype: keyboard or GPIO button.
- First always-listening build: Vosk Korean phrase detection with `DRGNU_WAKE_MODE=phrase`.
- Beta: openWakeWord or Porcupine custom model for `jinuya` and `hey jinu`.
- Production: benchmark false accepts, missed wakes, noisy-room performance, and CPU use on Jetson Nano.

## Phase 4: App And Web Sync

The app and web dashboard should read from the same server history:

- latest answer
- latest transcript
- session score
- risk level
- score details
- device online/offline state

For near-real-time updates, add WebSocket, Server-Sent Events, Firebase Realtime, or Supabase Realtime later. Polling is enough for MVP.
