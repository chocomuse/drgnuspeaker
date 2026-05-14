from __future__ import annotations

import traceback
from dataclasses import replace

from .api_client import DrgnuApiClient
from .audio_io import AudioRecorder
from .config import load_config
from .pairing import DevicePairingClient
from .status import SpeakerState, StatusReporter
from .tts import TextToSpeech
from .wake_word import build_wake_detector


START_MESSAGE = "\uc9c0\ub204 \uc2a4\ud53c\ucee4\ub97c \uc2dc\uc791\ud569\ub2c8\ub2e4."
READY_MESSAGE = "\ub124, \ub9d0\uc500\ud574 \uc8fc\uc138\uc694."
STOP_MESSAGE = "\uc9c0\ub204 \uc2a4\ud53c\ucee4\ub97c \uc885\ub8cc\ud569\ub2c8\ub2e4."
ERROR_PREFIX = "\ucc98\ub9ac \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4."


def main() -> None:
    config = load_config()
    tts = TextToSpeech(config.tts_command)
    device_token = DevicePairingClient(config).ensure_device_token(tts)
    if device_token:
        config = replace(config, device_token=device_token)
    wake_detector = build_wake_detector(config)
    recorder = AudioRecorder(config)
    api_client = DrgnuApiClient(config)
    status = StatusReporter()

    tts.speak(START_MESSAGE)

    while True:
        try:
            status.set_state(SpeakerState.IDLE)
            wake_detector.wait_for_wake()

            status.set_state(SpeakerState.LISTENING)
            tts.speak(READY_MESSAGE)

            status.set_state(SpeakerState.RECORDING)
            audio_path = recorder.record_once()

            status.set_state(SpeakerState.THINKING)
            result = api_client.analyze_audio(audio_path)

            status.set_state(SpeakerState.SPEAKING)
            tts.speak(result.spoken_summary())
        except KeyboardInterrupt:
            tts.speak(STOP_MESSAGE)
            break
        except Exception as error:
            status.set_state(SpeakerState.ERROR)
            print(traceback.format_exc(), flush=True)
            tts.speak(f"{ERROR_PREFIX} {error}")


if __name__ == "__main__":
    main()
