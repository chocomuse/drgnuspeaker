from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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
    ptt_gpio_pin: int | None
    led_gpio_pin: int | None
    work_dir: Path

    @property
    def analysis_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/stt-analyze"


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
        work_dir=Path(os.getenv("DRGNU_WORK_DIR", "/tmp/drgnu-speaker")),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return int(value)

