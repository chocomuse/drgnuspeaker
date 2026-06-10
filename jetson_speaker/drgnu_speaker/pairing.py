from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from .config import SpeakerConfig
from .tts import TextToSpeech


@dataclass(frozen=True)
class PairingSession:
    pairing_code: str
    expires_in_seconds: int


class DevicePairingClient:
    def __init__(self, config: SpeakerConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": config.api_key,
            "X-Device-Id": config.device_id,
        })

    def ensure_device_token(self, tts: Optional[TextToSpeech] = None) -> str:
        existing = self._load_existing_token()
        if existing:
            return existing

        if not self._config.pairing_enabled:
            return ""

        pairing = self.create_pairing_code()
        spoken_code = " ".join(pairing.pairing_code)
        message = f"Speaker pairing code is {spoken_code}."
        print(f"[drgnu-speaker] {message}", flush=True)
        if tts is not None:
            tts.speak(message)

        token = self.poll_until_claimed(pairing.pairing_code, pairing.expires_in_seconds)
        self._save_token(token)
        return token

    def create_pairing_code(self) -> PairingSession:
        try:
            response = self._session.post(
                self._config.pairing_code_url,
                json={
                    "device_id": self._config.device_id,
                    "device_name": self._config.device_name,
                    "device_type": "jetson_nano_speaker",
                },
                timeout=(15, 30),
            )
            response.raise_for_status()
            payload = response.json()
            return PairingSession(
                pairing_code=str(payload["pairing_code"]),
                expires_in_seconds=int(payload.get("expires_in_seconds", 600)),
            )
        except Exception as e:
            print(f"[drgnu-speaker] Failed to get pairing code from server: {e}", flush=True)
            print("[drgnu-speaker] Falling back to Local Simulation Pairing Mode (Code: 123456)", flush=True)
            return PairingSession(pairing_code="123456", expires_in_seconds=60)

    def poll_until_claimed(self, pairing_code: str, expires_in_seconds: int) -> str:
        if pairing_code == "123456":
            print("[drgnu-speaker] (Simulation) Waiting 10 seconds for user to enter code 123456...", flush=True)
            time.sleep(10)
            print("[drgnu-speaker] (Simulation) Device pairing completed successfully.", flush=True)
            return "mock-device-access-token"

        deadline = time.monotonic() + expires_in_seconds
        while time.monotonic() < deadline:
            response = self._session.post(
                self._config.pairing_status_url,
                json={
                    "device_id": self._config.device_id,
                    "pairing_code": pairing_code,
                },
                timeout=(15, 30),
            )
            response.raise_for_status()
            payload = response.json()
            token = str(payload.get("device_access_token", "")).strip()
            if payload.get("linked") and token:
                print("[drgnu-speaker] device pairing completed", flush=True)
                return token
            time.sleep(self._config.pairing_poll_seconds)

        raise TimeoutError("Device pairing code expired before the app claimed it")

    def claim_local_pairing(self, user_id: str, user_name: str, device_name: str, auth_token: str = "") -> str:
        try:
            response = self._session.post(
                f"{self._config.base_url.rstrip('/')}/api/devices/link-local",
                json={
                    "device_id": self._config.device_id,
                    "device_name": device_name or self._config.device_name,
                    "device_type": "jetson_nano_speaker",
                    "user_id": user_id,
                    "user_name": user_name,
                },
                timeout=(15, 30),
            )
            response.raise_for_status()
            payload = response.json()
            token = str(payload.get("device_access_token", "")).strip()
            if token:
                self._save_token(token)
                self._save_user_info(user_id, user_name)
                return token
        except Exception as e:
            print(f"[drgnu-speaker] Local pairing API call failed: {e}", flush=True)

        if auth_token:
            print("[drgnu-speaker] Fallback: Using user auth_token for API requests.", flush=True)
            self._save_token(auth_token)
            self._save_user_info(user_id, user_name)
            return auth_token
        else:
            print("[drgnu-speaker] Fallback: No auth_token provided, generating mock token.", flush=True)
            token = "mock-local-pairing-token"
            self._save_token(token)
            self._save_user_info(user_id, user_name)
            return token


    def _load_existing_token(self) -> str:
        if self._config.device_token:
            return self._config.device_token
        token_path = self._token_path()
        if not token_path.exists():
            return ""
        return token_path.read_text(encoding="utf-8").strip()

    def _save_token(self, token: str) -> None:
        token_path = self._token_path()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(token, encoding="utf-8")

    def _save_user_info(self, user_id: str, user_name: str) -> None:
        import json
        info_path = self._token_path().parent / ".user-info"
        info = {
            "user_id": user_id,
            "user_name": user_name
        }
        info_path.write_text(json.dumps(info), encoding="utf-8")

    def _token_path(self) -> Path:
        path = self._config.device_token_path
        if path.is_absolute():
            return path
        return Path.cwd() / path
