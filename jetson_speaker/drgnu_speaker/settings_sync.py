from __future__ import annotations

import threading
import time
from typing import Optional

import requests

from .config import SpeakerConfig
from .runtime_settings import DeviceSettings, RuntimeSettings


class SettingsSyncWorker:
    def __init__(self, config: SpeakerConfig, runtime_settings: RuntimeSettings) -> None:
        self._config = config
        self._runtime_settings = runtime_settings
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": config.api_key,
            "X-Device-Id": config.device_id,
        })
        if config.device_token:
            self._session.headers.update({"Authorization": f"Bearer {config.device_token}"})
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.sync_once()
            self._stop_event.wait(self._config.settings_sync_seconds)

    def sync_once(self) -> None:
        try:
            response = self._session.get(self._config.device_settings_url, timeout=(10, 20))
            if response.status_code == 404:
                return
            response.raise_for_status()
            payload = response.json()
            raw_settings = payload.get("settings", payload)
            current = self._runtime_settings.get()
            next_settings = DeviceSettings.from_payload(raw_settings, current)
            if next_settings != current:
                self._runtime_settings.update(next_settings)
                print(f"[drgnu-speaker] settings updated: {next_settings}", flush=True)
        except Exception as error:
            print(f"[drgnu-speaker] settings sync failed: {error}", flush=True)
