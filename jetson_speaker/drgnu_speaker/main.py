from __future__ import annotations

import traceback

from .api_client import DrgnuApiClient
from .audio_io import AudioRecorder
from .config import load_config
from .status import SpeakerState, StatusReporter
from .tts import TextToSpeech
from .wake_word import build_wake_detector


def main() -> None:
    config = load_config()
    wake_detector = build_wake_detector(config)
    recorder = AudioRecorder(config)
    api_client = DrgnuApiClient(config)
    tts = TextToSpeech(config.tts_command)
    status = StatusReporter()

    tts.speak("지누 스피커를 시작합니다.")

    while True:
        try:
            status.set_state(SpeakerState.IDLE)
            wake_detector.wait_for_wake()

            status.set_state(SpeakerState.LISTENING)
            tts.speak("네, 말씀해 주세요.")

            status.set_state(SpeakerState.RECORDING)
            audio_path = recorder.record_once()

            status.set_state(SpeakerState.THINKING)
            result = api_client.analyze_audio(audio_path)

            status.set_state(SpeakerState.SPEAKING)
            tts.speak(result.spoken_summary())
        except KeyboardInterrupt:
            tts.speak("지누 스피커를 종료합니다.")
            break
        except Exception as error:
            status.set_state(SpeakerState.ERROR)
            print(traceback.format_exc(), flush=True)
            tts.speak(f"처리 중 오류가 발생했습니다. {error}")


if __name__ == "__main__":
    main()

