from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from .event_log import EventLogger


class SystemMetricsWorker:
    def __init__(self, logger: EventLogger, interval_seconds: float) -> None:
        self._logger = logger
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._interval_seconds <= 0 or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._logger.emit("system_metrics", **collect_system_metrics())
            self._stop_event.wait(self._interval_seconds)


def collect_system_metrics() -> dict[str, object]:
    memory = _memory_metrics()
    load_average = os.getloadavg() if hasattr(os, "getloadavg") else (None, None, None)
    return {
        **memory,
        "load_1m": load_average[0],
        "load_5m": load_average[1],
        "load_15m": load_average[2],
        "temperature_c": _temperature_c(),
    }


def _memory_metrics() -> dict[str, Optional[float]]:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return {"memory_total_mb": None, "memory_available_mb": None, "memory_used_percent": None}

    values = {}
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        key, _, raw_value = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            values[key] = float(raw_value.strip().split()[0]) / 1024
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used_percent = None
    if total and available is not None:
        used_percent = round((total - available) / total * 100, 2)
    return {
        "memory_total_mb": round(total, 2) if total is not None else None,
        "memory_available_mb": round(available, 2) if available is not None else None,
        "memory_used_percent": used_percent,
    }


def _temperature_c() -> Optional[float]:
    temperatures = []
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            value = float(path.read_text(encoding="utf-8").strip())
            temperatures.append(value / 1000 if value > 200 else value)
        except (OSError, ValueError):
            continue
    return round(max(temperatures), 2) if temperatures else None
