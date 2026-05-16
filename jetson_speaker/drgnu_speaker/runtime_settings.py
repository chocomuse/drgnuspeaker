from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class DeviceSettings:
    device_name: str
    wake_mode: str
    record_seconds: float
    tts_enabled: bool
    mic_muted: bool
    local_pairing_enabled: bool

    @classmethod
    def defaults(
        cls,
        device_name: str,
        wake_mode: str,
        record_seconds: float,
        local_pairing_enabled: bool,
    ) -> "DeviceSettings":
        return cls(
            device_name=device_name,
            wake_mode=wake_mode,
            record_seconds=record_seconds,
            tts_enabled=True,
            mic_muted=False,
            local_pairing_enabled=local_pairing_enabled,
        )

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], fallback: "DeviceSettings") -> "DeviceSettings":
        return cls(
            device_name=str(payload.get("device_name") or fallback.device_name),
            wake_mode=str(payload.get("wake_mode") or fallback.wake_mode),
            record_seconds=_clamp(
                _float_value(payload.get("record_seconds"), fallback.record_seconds),
                minimum=1.0,
                maximum=30.0,
            ),
            tts_enabled=_bool_value(payload.get("tts_enabled"), fallback.tts_enabled),
            mic_muted=_bool_value(payload.get("mic_muted"), fallback.mic_muted),
            local_pairing_enabled=_bool_value(
                payload.get("local_pairing_enabled"),
                fallback.local_pairing_enabled,
            ),
        )


class RuntimeSettings:
    def __init__(self, initial: DeviceSettings) -> None:
        self._current = initial
        self._lock = threading.Lock()

    def get(self) -> DeviceSettings:
        with self._lock:
            return self._current

    def update(self, settings: DeviceSettings) -> None:
        with self._lock:
            self._current = settings


def _float_value(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _bool_value(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
