from __future__ import annotations

import traceback
import time
from dataclasses import replace

from .api_client import DrgnuApiClient
from .audio_io import AudioRecorder
from .config import load_config
from .event_log import EventLogger, EventTimer
from .local_pairing import LocalPairingServer
from .pairing import DevicePairingClient
from .runtime_settings import DeviceSettings, RuntimeSettings
from .settings_sync import SettingsSyncWorker
from .status import SpeakerState, StatusReporter
from .system_metrics import SystemMetricsWorker
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
    event_logger = EventLogger(config.event_log_path, config.device_id)
    event_logger.emit("application_started")
    tts = TextToSpeech(config.tts_command)
    
    # Headless Wi-Fi setup if disconnected
    wifi_timer = EventTimer(event_logger, "wifi_ready")
    WifiProvisioner(config, tts, event_logger).ensure_connected()
    wifi_timer.finish()
    
    local_pairing_server = LocalPairingServer(config, event_logger)
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
    wake_detector = build_wake_detector(config, event_logger)
    recorder = AudioRecorder(config)
    api_client = DrgnuApiClient(config)
    google_stt_client = GoogleSpeechClient(config, event_logger)
    status = StatusReporter()
    metrics_worker = SystemMetricsWorker(event_logger, config.system_metrics_seconds)
    metrics_worker.start()

    tts.speak(START_MESSAGE)
    consecutive_errors = 0

    while True:
        try:
            status.set_state(SpeakerState.IDLE)
            current_settings = runtime_settings.get()
            if current_settings.mic_muted:
                print("[drgnu-speaker] microphone is muted by app setting", flush=True)
                time.sleep(5)
                continue
            wake_detector.wait_for_wake()
            event_logger.emit("wake_detected")
            current_settings = runtime_settings.get()
            if current_settings.mic_muted:
                continue

            status.set_state(SpeakerState.LISTENING)
            if current_settings.tts_enabled:
                tts.speak(READY_MESSAGE)

            status.set_state(SpeakerState.RECORDING)
            recording_timer = EventTimer(event_logger, "question_recording_completed")
            audio_path = recorder.record_once(current_settings.record_seconds)
            recording_timer.finish(audio_path=str(audio_path))

            status.set_state(SpeakerState.THINKING)
            
            local_stt = google_stt_client.transcribe(audio_path)

            analysis_timer = EventTimer(event_logger, "backend_analysis_completed")
            try:
                result = api_client.analyze_audio(
                    audio_path,
                    voice_profile_id=current_settings.active_voice_profile_id,
                    local_stt=local_stt,
                )
                analysis_timer.finish(status="ok")
            except Exception as error:
                analysis_timer.finish(False, error_type=type(error).__name__)
                raise

            status.set_state(SpeakerState.SPEAKING)
            if runtime_settings.get().tts_enabled:
                # Speak the main answer immediately
                if result.answer:
                    tts_timer = EventTimer(event_logger, "tts_answer_completed")
                    tts.speak(result.answer)
                    tts_timer.finish()
                
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
            consecutive_errors = 0
        except KeyboardInterrupt:
            settings_sync.stop()
            metrics_worker.stop()
            if runtime_settings.get().tts_enabled:
                tts.speak(STOP_MESSAGE)
            local_pairing_server.stop()
            break
        except Exception as error:
            status.set_state(SpeakerState.ERROR)
            event_logger.emit("application_error", error_type=type(error).__name__, message=str(error))
            print(traceback.format_exc(), flush=True)
            if runtime_settings.get().tts_enabled:
                tts.speak(f"{ERROR_PREFIX} {error}")
            consecutive_errors += 1
            retry_delay = min(30, 2 ** min(consecutive_errors, 5))
            event_logger.emit("error_retry_scheduled", delay_seconds=retry_delay)
            time.sleep(retry_delay)


if __name__ == "__main__":
    main()
