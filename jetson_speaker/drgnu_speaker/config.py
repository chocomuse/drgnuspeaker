from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


DEFAULT_WAKE_PHRASES = (
    "\uc9c0\ub204\uc57c",
    "\uc9c4\uc6b0\uc57c",
    "\ud5e4\uc774 \uc9c0\ub204",
    "\ud5e4\uc774 \uc9c4\uc6b0",
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
    pairing_enabled: bool
    pairing_poll_seconds: float
    device_name: str
    device_token: str
    device_token_path: Path
    local_pairing_enabled: bool
    local_pairing_port: int
    local_pairing_service_type: str
    work_dir: Path

    @property
    def analysis_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/stt-analyze"

    @property
    def pairing_code_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/devices/pairing-code"

    @property
    def pairing_status_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/devices/pairing-status"


def load_config() -> SpeakerConfig:
    load_dotenv()
    return SpeakerConfig(
        base_url=_required_env("DRGNU_BASE_URL"),
        api_key=_required_env("DRGNU_API_KEY"),
        device_id=os.getenv("DRGNU_DEVICE_ID", "jetson-nano-dev-001"),
        session_id=os.getenv("DRGNU_SESSION_ID", "test_user_001"),
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
        pairing_enabled=_bool_env("DRGNU_PAIRING_ENABLED", False),
        pairing_poll_seconds=float(os.getenv("DRGNU_PAIRING_POLL_SECONDS", "3")),
        device_name=os.getenv("DRGNU_DEVICE_NAME", "Drgnu Jetson Speaker").strip(),
        device_token=os.getenv("DRGNU_DEVICE_TOKEN", "").strip(),
        device_token_path=Path(os.getenv("DRGNU_DEVICE_TOKEN_PATH", ".device-token")),
        local_pairing_enabled=_bool_env("DRGNU_LOCAL_PAIRING_ENABLED", True),
        local_pairing_port=int(os.getenv("DRGNU_LOCAL_PAIRING_PORT", "8765")),
        local_pairing_service_type=os.getenv(
            "DRGNU_LOCAL_PAIRING_SERVICE_TYPE",
            "_drgnu-speaker._tcp.local.",
        ).strip(),
        work_dir=Path(os.getenv("DRGNU_WORK_DIR", "/tmp/drgnu-speaker")),
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
