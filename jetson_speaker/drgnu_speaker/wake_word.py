from __future__ import annotations

import json
import tempfile
import queue
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

import sounddevice as sd
import soundfile as sf
import numpy as np

from .config import SpeakerConfig
from .event_log import EventLogger
from .stt import GoogleSpeechClient


class WakeDetector(ABC):
    @abstractmethod
    def wait_for_wake(self) -> None:
        raise NotImplementedError


class KeyboardWakeDetector(WakeDetector):
    def wait_for_wake(self) -> None:
        try:
            input("Press Enter to simulate wake word: ")
        except EOFError as error:
            raise KeyboardInterrupt from error


class ButtonWakeDetector(WakeDetector):
    def __init__(self, gpio_pin: Optional[int]) -> None:
        self._gpio_pin = gpio_pin

    def wait_for_wake(self) -> None:
        if self._gpio_pin is None:
            raise RuntimeError("DRGNU_PTT_GPIO_PIN is required for button wake mode")
        raise NotImplementedError("GPIO button wake mode will be wired in the Jetson hardware pass")


class GoogleSttWakeDetector(WakeDetector):
    def __init__(self, config: SpeakerConfig, event_logger: Optional[EventLogger] = None) -> None:
        self._config = config
        self._event_logger = event_logger
        self._stt = GoogleSpeechClient(config, event_logger)
        self._last_match_at = 0.0
        self._phrases = tuple(
            phrase
            for phrase in (_normalize_text(item) for item in config.wake_phrases)
            if len(phrase) >= 3 or phrase.startswith("hey")
        )

    def wait_for_wake(self) -> None:
        if not self._stt.enabled:
            raise RuntimeError(
                "Google STT wake mode requires DRGNU_GOOGLE_STT_ENABLED=true and valid Google credentials"
            )

        started_at = time.monotonic()
        print("[drgnu-speaker] listening for wake phrase with Google STT", flush=True)
        while True:
            if self._config.wake_timeout_seconds > 0:
                elapsed = time.monotonic() - started_at
                if elapsed > self._config.wake_timeout_seconds:
                    raise TimeoutError("Wake phrase was not detected before timeout")

            audio_path, rms = self._record_wake_clip()
            if rms < self._config.wake_min_rms:
                if self._event_logger is not None:
                    self._event_logger.emit("wake_clip_skipped", reason="low_rms", rms=round(rms, 2))
                audio_path.unlink(missing_ok=True)
                continue
            try:
                recognition = self._stt.transcribe_result(audio_path)
            finally:
                try:
                    audio_path.unlink()
                except OSError:
                    pass

            if recognition.transcript:
                print(f"[drgnu-speaker] wake stt heard: {recognition.transcript}", flush=True)
            confidence_ok = (
                recognition.confidence is None
                or recognition.confidence >= self._config.wake_min_confidence
            )
            matched = confidence_ok and self._contains_wake_phrase(recognition.transcript)
            if self._event_logger is not None:
                self._event_logger.emit(
                    "wake_detection_attempt",
                    matched=matched,
                    rms=round(rms, 2),
                    confidence=recognition.confidence,
                    transcript=recognition.transcript,
                )
            if matched and time.monotonic() - self._last_match_at >= self._config.wake_cooldown_seconds:
                self._last_match_at = time.monotonic()
                return

            if self._config.wake_stt_pause_seconds > 0:
                time.sleep(self._config.wake_stt_pause_seconds)

    def _record_wake_clip(self) -> tuple[Path, float]:
        duration = max(0.5, self._config.wake_stt_seconds)
        sample_rate = self._config.sample_rate
        channels = self._config.channels
        frame_count = int(sample_rate * duration)

        audio = sd.rec(
            frame_count,
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
        )
        sd.wait()
        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

        self._config.work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="drgnu_wake_",
            suffix=".wav",
            dir=self._config.work_dir,
            delete=False,
        ) as temp_file:
            output_path = Path(temp_file.name)
        sf.write(output_path, audio, sample_rate)
        return output_path, rms

    def _contains_wake_phrase(self, text: str) -> bool:
        normalized = _normalize_text(text)
        if not normalized:
            return False
        matched_phrase = next((phrase for phrase in self._phrases if phrase in normalized), "")
        if matched_phrase:
            print(f"[drgnu-speaker] Google STT wake phrase matched: {text}", flush=True)
            return True
        return False


class VoskPhraseWakeDetector(WakeDetector):
    def __init__(
        self,
        model_path: Path,
        phrases: Tuple[str, ...],
        sample_rate: int,
        channels: int,
        timeout_seconds: float,
    ) -> None:
        self._phrases = tuple(_normalize_text(phrase) for phrase in phrases)
        self._sample_rate = sample_rate
        self._channels = channels
        self._timeout_seconds = timeout_seconds
        self._model = self._load_model(model_path)

    def wait_for_wake(self) -> None:
        from vosk import KaldiRecognizer
        import json

        # Restrict Vosk vocabulary to only target wake phrases and unknown sounds ([unk]).
        # This dramatically reduces false positives and boosts wake word detection accuracy.
        grammar = [
            "지누야", "진우야", "지누 야", "진우 야", "지 이누야", "이누야", "이누 야",
            "지우야", "지우 야", "기누야", "기누 야", "지누", "진우", "지우", "이누", "기누",
            "헤이 지누", "헤이 진우", "hey jinu", "hey ginu", "[unk]"
        ]
        grammar_json = json.dumps(grammar, ensure_ascii=False)
        recognizer = KaldiRecognizer(self._model, self._sample_rate, grammar_json)
        audio_queue: "queue.Queue[bytes]" = queue.Queue()
        started_at = time.monotonic()


        def callback(indata: bytes, frames: int, time_info: object, status: object) -> None:
            if status:
                print(f"[drgnu-speaker] wake audio status={status}", flush=True)
            audio_queue.put(bytes(indata))

        try:
            default_device = sd.query_devices(kind='input')
            device_name = default_device.get('name', 'Unknown')
            print(f"[drgnu-speaker] default input device: {device_name}", flush=True)
        except Exception as e:
            print(f"[drgnu-speaker] failed to query input devices: {e}", flush=True)

        print("[drgnu-speaker] listening for wake phrase", flush=True)
        with sd.RawInputStream(
            samplerate=self._sample_rate,
            blocksize=8000,
            dtype="int16",
            channels=self._channels,
            callback=callback,
        ):
            while True:
                if self._timeout_seconds > 0 and time.monotonic() - started_at > self._timeout_seconds:
                    raise TimeoutError("Wake phrase was not detected before timeout")

                data = audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                    if text.strip():
                        print(f"\n[인식된 문장]: {text}", flush=True)
                    if self._contains_wake_phrase(text):
                        return
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    if partial.strip():
                        print(f"[음성 감지 중...]: {partial}      ", end="\r", flush=True)
                    if self._contains_wake_phrase(partial):
                        return


    def _contains_wake_phrase(self, text: str) -> bool:
        normalized = _normalize_text(text)
        if not normalized:
            return False
        matched = any(phrase in normalized for phrase in self._phrases)
        if matched:
            print(f"[drgnu-speaker] wake phrase matched: {text}", flush=True)
        return matched

    @staticmethod
    def _load_model(model_path: Path) -> object:
        if not model_path.exists():
            raise RuntimeError(
                "Vosk wake model not found. "
                f"Download it first or set DRGNU_WAKE_MODEL_PATH: {model_path}"
            )

        try:
            from vosk import Model, SetLogLevel
        except ImportError as error:
            raise RuntimeError("Install wake dependencies first: pip install -r requirements.txt") from error

        SetLogLevel(-1)
        return Model(str(model_path))


def _normalize_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\uac00-\ud7a3]+", "", value).lower()


def build_wake_detector(
    config: SpeakerConfig,
    event_logger: Optional[EventLogger] = None,
) -> WakeDetector:
    if config.wake_mode == "keyboard":
        return KeyboardWakeDetector()
    if config.wake_mode == "button":
        return ButtonWakeDetector(config.ptt_gpio_pin)
    if config.wake_mode in ("google_stt", "stt", "google"):
        return GoogleSttWakeDetector(config, event_logger)
    if config.wake_mode in ("phrase", "vosk"):
        return VoskPhraseWakeDetector(
            model_path=config.wake_model_path,
            phrases=config.wake_phrases,
            sample_rate=config.sample_rate,
            channels=config.channels,
            timeout_seconds=config.wake_timeout_seconds,
        )
    raise RuntimeError(
        f"Unsupported wake mode '{config.wake_mode}'. Use keyboard, button, phrase, or vosk."
    )
