from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


DEFAULT_WAKE_PHRASES = (
    "지누야",
    "진우야",
    "지이누야",
    "이누야",
    "지우야",
    "기누야",
    "지누",
    "진우",
    "지우",
    "이누",
    "기누",
    "헤이 지누",
    "헤이 진우",
    "hey jinu",
    "hey ginu",
)



@dataclass(frozen=True)
class SpeakerConfig:
    base_url: str
    api_key: str
    device_id: str
    session_id: str
    wake_mode: str
    record_seconds: float
    sample_rate: int
    channels: int
    tts_command: str
    ptt_gpio_pin: Optional[int]
    led_gpio_pin: Optional[int]
    wake_model_path: Path
    wake_phrases: Tuple[str, ...]
    wake_timeout_seconds: float
    wake_stt_seconds: float
    wake_stt_pause_seconds: float
    pairing_enabled: bool
    pairing_poll_seconds: float
    device_name: str
    device_token: str
    device_token_path: Path
    local_pairing_enabled: bool
    local_pairing_port: int
    local_pairing_service_type: str
    settings_sync_enabled: bool
    settings_sync_seconds: float
    work_dir: Path
    hotspot_ssid: str
    hotspot_ssid_prefix: str
    hotspot_password: str
    hotspot_port: int
    hotspot_gateway_ip: str
    wifi_setup_token: str
    wifi_setup_timeout_seconds: float
    google_stt_enabled: bool
    google_stt_api_key: str
    google_stt_language_code: str
    google_services_json: Optional[Path]
    google_service_account_json: Optional[Path]
    event_log_path: Optional[Path]
    wake_min_rms: float
    wake_min_confidence: float
    wake_cooldown_seconds: float
    system_metrics_seconds: float


    @property
    def analysis_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/stt-analyze"

    @property
    def pairing_code_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/devices/pairing-code"

    @property
    def pairing_status_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/devices/pairing-status"

    @property
    def device_settings_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/devices/{self.device_id}/settings"


def load_config() -> SpeakerConfig:
    load_dotenv()
    
    device_token_path = Path(os.getenv("DRGNU_DEVICE_TOKEN_PATH", ".device-token"))
    resolved_token_path = device_token_path if device_token_path.is_absolute() else Path.cwd() / device_token_path
    user_info_path = resolved_token_path.parent / ".user-info"
    
    session_id = os.getenv("DRGNU_SESSION_ID", "test_user_001")
    if user_info_path.exists():
        try:
            import json
            info = json.loads(user_info_path.read_text(encoding="utf-8"))
            if info.get("user_id"):
                session_id = info["user_id"]
                print(f"[drgnu-speaker] Loaded session_id (user_id) from user info: {session_id}", flush=True)
        except Exception as e:
            print(f"[drgnu-speaker] Failed to load user info: {e}", flush=True)

    return SpeakerConfig(
        base_url=_required_env("DRGNU_BASE_URL"),
        api_key=_required_env("DRGNU_API_KEY"),
        device_id=os.getenv("DRGNU_DEVICE_ID", "jetson-nano-dev-001"),
        session_id=session_id,
        wake_mode=os.getenv("DRGNU_WAKE_MODE", "keyboard").strip().lower(),
        record_seconds=float(os.getenv("DRGNU_RECORD_SECONDS", "7")),
        sample_rate=int(os.getenv("DRGNU_SAMPLE_RATE", "16000")),
        channels=int(os.getenv("DRGNU_CHANNELS", "1")),
        tts_command=os.getenv("DRGNU_TTS_COMMAND", "spd-say").strip(),
        ptt_gpio_pin=_optional_int("DRGNU_PTT_GPIO_PIN"),
        led_gpio_pin=_optional_int("DRGNU_LED_GPIO_PIN"),
        wake_model_path=Path(
            os.getenv(
                "DRGNU_WAKE_MODEL_PATH",
                "models/vosk-model-small-ko-0.22",
            )
        ),
        wake_phrases=_configured_wake_phrases(),
        wake_timeout_seconds=float(os.getenv("DRGNU_WAKE_TIMEOUT_SECONDS", "0")),
        wake_stt_seconds=float(os.getenv("DRGNU_WAKE_STT_SECONDS", "2.0")),
        wake_stt_pause_seconds=float(os.getenv("DRGNU_WAKE_STT_PAUSE_SECONDS", "0.2")),
        pairing_enabled=_bool_env("DRGNU_PAIRING_ENABLED", False),
        pairing_poll_seconds=float(os.getenv("DRGNU_PAIRING_POLL_SECONDS", "3")),
        device_name=os.getenv("DRGNU_DEVICE_NAME", "Drgnu Jetson Speaker").strip(),
        device_token=os.getenv("DRGNU_DEVICE_TOKEN", "").strip(),
        device_token_path=device_token_path,
        local_pairing_enabled=_bool_env("DRGNU_LOCAL_PAIRING_ENABLED", True),
        local_pairing_port=int(os.getenv("DRGNU_LOCAL_PAIRING_PORT", "8765")),
        local_pairing_service_type=os.getenv(
            "DRGNU_LOCAL_PAIRING_SERVICE_TYPE",
            "_drgnu-speaker._tcp.local.",
        ).strip(),
        settings_sync_enabled=_bool_env("DRGNU_SETTINGS_SYNC_ENABLED", True),
        settings_sync_seconds=float(os.getenv("DRGNU_SETTINGS_SYNC_SECONDS", "30")),
        work_dir=Path(os.getenv("DRGNU_WORK_DIR", "/tmp/drgnu-speaker")),
        hotspot_ssid=os.getenv("DRGNU_HOTSPOT_SSID", "DrGNU-Speaker-Setup").strip(),
        hotspot_ssid_prefix=os.getenv("DRGNU_HOTSPOT_SSID_PREFIX", "Drgnu-Speaker-").strip(),
        hotspot_password=os.getenv("DRGNU_HOTSPOT_PASSWORD", "drgnuspeaker").strip(),
        hotspot_port=int(os.getenv("DRGNU_HOTSPOT_PORT", "8765")),
        hotspot_gateway_ip=os.getenv("DRGNU_HOTSPOT_GATEWAY_IP", "192.168.4.1").strip(),
        wifi_setup_token=os.getenv("DRGNU_WIFI_SETUP_TOKEN", "").strip(),
        wifi_setup_timeout_seconds=float(os.getenv("DRGNU_WIFI_SETUP_TIMEOUT_SECONDS", "900")),
        google_stt_enabled=_bool_env("DRGNU_GOOGLE_STT_ENABLED", False),
        google_stt_api_key=os.getenv("DRGNU_GOOGLE_STT_API_KEY", "").strip(),
        google_stt_language_code=os.getenv("DRGNU_GOOGLE_STT_LANGUAGE_CODE", "ko-KR").strip(),
        google_services_json=_optional_path("DRGNU_GOOGLE_SERVICES_JSON"),
        google_service_account_json=_optional_path("DRGNU_GOOGLE_SERVICE_ACCOUNT_JSON"),
        event_log_path=_optional_path("DRGNU_EVENT_LOG_PATH", "logs/experiments.jsonl"),
        wake_min_rms=float(os.getenv("DRGNU_WAKE_MIN_RMS", "180")),
        wake_min_confidence=float(os.getenv("DRGNU_WAKE_MIN_CONFIDENCE", "0.55")),
        wake_cooldown_seconds=float(os.getenv("DRGNU_WAKE_COOLDOWN_SECONDS", "2.0")),
        system_metrics_seconds=float(os.getenv("DRGNU_SYSTEM_METRICS_SECONDS", "60")),
    )



def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _optional_int(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return int(value)


def _optional_path(name: str, default: str = "") -> Optional[Path]:
    value = os.getenv(name, default).strip()
    if not value:
        return None
    return Path(value).expanduser()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "y", "on")


def _configured_wake_phrases() -> Tuple[str, ...]:
    value = os.getenv("DRGNU_WAKE_PHRASES", "").strip()
    if not value:
        return DEFAULT_WAKE_PHRASES
    return _csv_tuple(value)


def _csv_tuple(value: str) -> Tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    if not items:
        raise RuntimeError("DRGNU_WAKE_PHRASES must contain at least one phrase")
    return items
