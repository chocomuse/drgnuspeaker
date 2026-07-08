from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .config import SpeakerConfig
from .event_log import EventLogger


SPEECH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


@dataclass(frozen=True)
class SpeechRecognition:
    transcript: str
    confidence: Optional[float]


class GoogleSpeechClient:
    def __init__(self, config: SpeakerConfig, event_logger: Optional[EventLogger] = None) -> None:
        self._config = config
        self._api_key = ""
        self._credentials: service_account.Credentials | None = None
        self._http = requests.Session()
        self._http.trust_env = False
        self._event_logger = event_logger

        if not config.google_stt_enabled:
            print("[google-stt] disabled. Set DRGNU_GOOGLE_STT_ENABLED=true to enable it.", flush=True)
            return

        self._credentials = self._load_service_account(config.google_service_account_json)
        if not self._credentials:
            self._api_key = config.google_stt_api_key or self._load_api_key_from_google_services(
                config.google_services_json
            )

        if self._credentials:
            print("[google-stt] ready with service account", flush=True)
        elif self._api_key:
            print("[google-stt] ready", flush=True)
        else:
            print(
                "[google-stt] credentials missing. Set DRGNU_GOOGLE_SERVICE_ACCOUNT_JSON, DRGNU_GOOGLE_STT_API_KEY, or DRGNU_GOOGLE_SERVICES_JSON.",
                flush=True,
            )

    @property
    def enabled(self) -> bool:
        return bool(self._config.google_stt_enabled and (self._credentials or self._api_key))

    def transcribe(self, audio_path: Path) -> str:
        return self.transcribe_result(audio_path).transcript

    def transcribe_result(self, audio_path: Path) -> SpeechRecognition:
        if not self.enabled:
            return SpeechRecognition("", None)
        if not audio_path.exists():
            print(f"[google-stt] audio file not found: {audio_path}", flush=True)
            return SpeechRecognition("", None)

        started_at = time.monotonic()
        try:
            audio_content = base64.b64encode(audio_path.read_bytes()).decode("ascii")
            payload = {
                "config": {
                    "encoding": "LINEAR16",
                    "sampleRateHertz": self._config.sample_rate,
                    "languageCode": self._config.google_stt_language_code,
                    "enableAutomaticPunctuation": True,
                    "model": "latest_short",
                },
                "audio": {"content": audio_content},
            }
            if self._config.channels > 1:
                payload["config"]["audioChannelCount"] = self._config.channels

            response = self._post_recognize(payload)

            if response.status_code != 200:
                self._print_error(response)
                self._emit_event(started_at, False, status_code=response.status_code)
                return SpeechRecognition("", None)

            recognition = self._best_recognition(response.json())
            if recognition.transcript:
                print(f"[google-stt] transcript: {recognition.transcript}", flush=True)
            else:
                print("[google-stt] no speech recognized", flush=True)
            self._emit_event(
                started_at,
                True,
                recognized=bool(recognition.transcript),
                confidence=recognition.confidence,
            )
            return recognition
        except requests.RequestException as error:
            print(f"[google-stt] request failed: {error}", flush=True)
            self._emit_event(started_at, False, error_type=type(error).__name__)
            return SpeechRecognition("", None)
        except Exception as error:
            print(f"[google-stt] transcription failed: {error}", flush=True)
            self._emit_event(started_at, False, error_type=type(error).__name__)
            return SpeechRecognition("", None)

    def _post_recognize(self, payload: dict[str, Any]) -> requests.Response:
        url = "https://speech.googleapis.com/v1/speech:recognize"
        if self._credentials:
            if not self._credentials.valid:
                self._credentials.refresh(Request(session=self._http))
            return self._http.post(
                url,
                headers={"Authorization": f"Bearer {self._credentials.token}"},
                json=payload,
                timeout=(10, 60),
            )

        return self._http.post(
            url,
            params={"key": self._api_key},
            json=payload,
            timeout=(10, 60),
        )

    def _load_service_account(self, config_path: Optional[Path]) -> service_account.Credentials | None:
        if not config_path:
            return None

        path = config_path if config_path.is_absolute() else Path.cwd() / config_path
        if not path.exists():
            print(f"[google-stt] service account file not found: {path}", flush=True)
            return None

        try:
            return service_account.Credentials.from_service_account_file(
                str(path),
                scopes=[SPEECH_SCOPE],
            )
        except Exception as error:
            print(f"[google-stt] failed to read service account file: {error}", flush=True)
            return None

    def _load_api_key_from_google_services(self, config_path: Optional[Path]) -> str:
        if not config_path:
            return ""

        path = config_path if config_path.is_absolute() else Path.cwd() / config_path
        if not path.exists():
            print(f"[google-stt] google-services file not found: {path}", flush=True)
            return ""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            clients = payload.get("client", [])
            if not clients:
                return ""
            api_keys = clients[0].get("api_key", [])
            if not api_keys:
                return ""
            return str(api_keys[0].get("current_key", "")).strip()
        except Exception as error:
            print(f"[google-stt] failed to read google-services file: {error}", flush=True)
            return ""

    def _best_recognition(self, payload: dict[str, Any]) -> SpeechRecognition:
        parts = []
        confidences = []
        for result in payload.get("results", []):
            alternatives = result.get("alternatives", [])
            if alternatives:
                transcript = str(alternatives[0].get("transcript", "")).strip()
                if transcript:
                    parts.append(transcript)
                confidence = alternatives[0].get("confidence")
                if confidence is not None:
                    try:
                        confidences.append(float(confidence))
                    except (TypeError, ValueError):
                        pass
        average_confidence = sum(confidences) / len(confidences) if confidences else None
        return SpeechRecognition(" ".join(parts).strip(), average_confidence)

    def _emit_event(self, started_at: float, success: bool, **fields: Any) -> None:
        if self._event_logger is None:
            return
        self._event_logger.emit(
            "google_stt_completed",
            success=success,
            duration_ms=round((time.monotonic() - started_at) * 1000, 2),
            **fields,
        )

    def _print_error(self, response: requests.Response) -> None:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        print(f"[google-stt] API error {response.status_code}: {detail}", flush=True)
        if response.status_code in (401, 403):
            print(
                "[google-stt] Check that Speech-to-Text API is enabled and the API key/service account has access.",
                flush=True,
            )
