from __future__ import annotations

import traceback
import time
from dataclasses import replace

from .api_client import DrgnuApiClient
from .audio_io import AudioRecorder
from .config import load_config
from .local_pairing import LocalPairingServer
from .pairing import DevicePairingClient
from .runtime_settings import DeviceSettings, RuntimeSettings
from .settings_sync import SettingsSyncWorker
from .status import SpeakerState, StatusReporter
from .tts import TextToSpeech
from .wake_word import build_wake_detector
from .wifi_provisioner import WifiProvisioner
from .stt import GoogleSpeechClient



START_MESSAGE = "\uc9c0\ub204 \uc2a4\ud53c\ucee4\ub97c \uc2dc\uc791\ud569\ub2c8\ub2e4."
READY_MESSAGE = "\ub124, \ub9d0\uc500\ud574 \uc8fc\uc138\uc694."
STOP_MESSAGE = "\uc9c0\ub204 \uc2a4\ud53c\ucee4\ub97c \uc885\ub8cc\ud569\ub2c8\ub2e4."
ERROR_PREFIX = "\ucc98\ub9ac \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4."


def main() -> None:
    config = load_config()
    tts = TextToSpeech(config.tts_command)
    
    # Headless Wi-Fi setup if disconnected
    WifiProvisioner(config, tts).ensure_connected()
    
    local_pairing_server = LocalPairingServer(config)
    local_pairing_server.start()

    device_token = DevicePairingClient(config).ensure_device_token(tts)
    if device_token:
        user_info_path = config.device_token_path.parent / ".user-info"
        if user_info_path.exists():
            try:
                import json
                info = json.loads(user_info_path.read_text(encoding="utf-8"))
                if info.get("user_id"):
                    config = replace(config, device_token=device_token, session_id=info["user_id"])
                    print(f"[drgnu-speaker] Dynamic pairing update: session_id set to user_id = {info['user_id']}", flush=True)
                else:
                    config = replace(config, device_token=device_token)
            except Exception:
                config = replace(config, device_token=device_token)
        else:
            config = replace(config, device_token=device_token)
    runtime_settings = RuntimeSettings(
        DeviceSettings.defaults(
            device_name=config.device_name,
            wake_mode=config.wake_mode,
            record_seconds=config.record_seconds,
            local_pairing_enabled=config.local_pairing_enabled,
        )
    )
    settings_sync = SettingsSyncWorker(config, runtime_settings)
    if config.settings_sync_enabled:
        settings_sync.start()
    wake_detector = build_wake_detector(config)
    recorder = AudioRecorder(config)
    api_client = DrgnuApiClient(config)
    google_stt_client = GoogleSpeechClient(config)
    status = StatusReporter()

    tts.speak(START_MESSAGE)

    while True:
        try:
            status.set_state(SpeakerState.IDLE)
            current_settings = runtime_settings.get()
            if current_settings.mic_muted:
                print("[drgnu-speaker] microphone is muted by app setting", flush=True)
                time.sleep(5)
                continue
            wake_detector.wait_for_wake()
            current_settings = runtime_settings.get()
            if current_settings.mic_muted:
                continue

            status.set_state(SpeakerState.LISTENING)
            if current_settings.tts_enabled:
                tts.speak(READY_MESSAGE)

            status.set_state(SpeakerState.RECORDING)
            audio_path = recorder.record_once(current_settings.record_seconds)

            status.set_state(SpeakerState.THINKING)
            
            local_stt = google_stt_client.transcribe(audio_path)

            result = api_client.analyze_audio(
                audio_path,
                voice_profile_id=current_settings.active_voice_profile_id,
                local_stt=local_stt,
            )

            status.set_state(SpeakerState.SPEAKING)
            if runtime_settings.get().tts_enabled:
                # Speak the main answer immediately
                if result.answer:
                    tts.speak(result.answer)
                
                # Speak the score and risk level afterward (omitting the reason)
                score_details = []
                if result.score is not None:
                    score_details.append(f"상태 점수는 {result.score}점입니다.")
                if result.risk_level:
                    risk_label = result.risk_level
                    if risk_label.lower() == "normal":
                        risk_label = "정상"
                    elif risk_label.lower() == "low risk":
                        risk_label = "낮은위험"
                    elif risk_label.lower() == "caution":
                        risk_label = "주의"
                    elif risk_label.lower() == "risk":
                        risk_label = "위험"
                    elif risk_label.lower() == "high risk" or risk_label.lower() == "very risk":
                        risk_label = "매우위험"
                    score_details.append(f"위험도는 {risk_label}입니다.")
                
                if score_details:
                    tts.speak(" ".join(score_details))
        except KeyboardInterrupt:
            settings_sync.stop()
            if runtime_settings.get().tts_enabled:
                tts.speak(STOP_MESSAGE)
            local_pairing_server.stop()
            break
        except Exception as error:
            status.set_state(SpeakerState.ERROR)
            print(traceback.format_exc(), flush=True)
            if runtime_settings.get().tts_enabled:
                tts.speak(f"{ERROR_PREFIX} {error}")


if __name__ == "__main__":
    main()
