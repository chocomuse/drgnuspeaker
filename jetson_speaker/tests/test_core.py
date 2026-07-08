from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from drgnu_speaker.event_log import EventLogger
from drgnu_speaker.pairing import DevicePairingClient
from drgnu_speaker.stt import GoogleSpeechClient
from drgnu_speaker.system_metrics import collect_system_metrics
from drgnu_speaker.wake_word import GoogleSttWakeDetector


class PairingTests(unittest.TestCase):
    def _config(self, token_path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            api_key="server-key",
            device_id="test-device",
            device_name="Test Speaker",
            device_token="",
            device_token_path=token_path,
            base_url="https://example.invalid",
            pairing_code_url="https://example.invalid/pairing-code",
            pairing_status_url="https://example.invalid/pairing-status",
            pairing_enabled=True,
            pairing_poll_seconds=0.01,
        )

    def test_pairing_code_failure_does_not_create_mock_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = DevicePairingClient(self._config(Path(directory) / ".device-token"))
            response = Mock()
            response.raise_for_status.side_effect = requests.HTTPError("server failed")
            client._session.post = Mock(return_value=response)

            with self.assertRaises(requests.HTTPError):
                client.create_pairing_code()

    def test_local_pairing_without_server_token_does_not_save_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / ".device-token"
            client = DevicePairingClient(self._config(token_path))
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"linked": True}
            client._session.post = Mock(return_value=response)

            with self.assertRaises(RuntimeError):
                client.claim_local_pairing("user-1", "User", "Speaker")

            self.assertFalse(token_path.exists())
            self.assertFalse((token_path.parent / ".user-info").exists())


class SpeechRecognitionTests(unittest.TestCase):
    def test_best_recognition_returns_transcript_and_average_confidence(self) -> None:
        client = GoogleSpeechClient.__new__(GoogleSpeechClient)
        result = client._best_recognition(
            {
                "results": [
                    {"alternatives": [{"transcript": "지누야", "confidence": 0.8}]},
                    {"alternatives": [{"transcript": "안녕", "confidence": 0.6}]},
                ]
            }
        )
        self.assertEqual(result.transcript, "지누야 안녕")
        self.assertAlmostEqual(result.confidence or 0, 0.7)

    def test_wake_match_rejects_short_alias(self) -> None:
        detector = GoogleSttWakeDetector.__new__(GoogleSttWakeDetector)
        detector._phrases = ("지누야", "진우야", "heyjinu")
        self.assertTrue(detector._contains_wake_phrase("진우야"))
        self.assertFalse(detector._contains_wake_phrase("진우"))
        self.assertFalse(detector._contains_wake_phrase("아무 의미 없는 말"))


class EventLogTests(unittest.TestCase):
    def test_event_logger_writes_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            logger = EventLogger(path, "test-device")
            logger.emit("test_event", duration_ms=12.5, success=True)

            payload = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["event"], "test_event")
            self.assertEqual(payload["device_id"], "test-device")
            self.assertTrue(payload["success"])

    def test_system_metrics_has_stable_schema(self) -> None:
        metrics = collect_system_metrics()
        self.assertIn("memory_total_mb", metrics)
        self.assertIn("memory_used_percent", metrics)
        self.assertIn("temperature_c", metrics)


if __name__ == "__main__":
    unittest.main()
