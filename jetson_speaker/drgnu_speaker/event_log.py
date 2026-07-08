from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Optional


class EventLogger:
    def __init__(self, path: Optional[Path], device_id: str) -> None:
        self._path = path
        self._device_id = device_id
        self._lock = threading.Lock()
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields: Any) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "device_id": self._device_id,
            **fields,
        }
        print(f"[experiment] {json.dumps(payload, ensure_ascii=False)}", flush=True)
        if self._path is None:
            return
        with self._lock:
            with self._path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(payload, ensure_ascii=False) + "\n")


class EventTimer:
    def __init__(self, logger: EventLogger, event: str, **fields: Any) -> None:
        self._logger = logger
        self._event = event
        self._fields = fields
        self._started_at = monotonic()

    def finish(self, success: bool = True, **fields: Any) -> None:
        duration_ms = round((monotonic() - self._started_at) * 1000, 2)
        self._logger.emit(
            self._event,
            success=success,
            duration_ms=duration_ms,
            **self._fields,
            **fields,
        )
