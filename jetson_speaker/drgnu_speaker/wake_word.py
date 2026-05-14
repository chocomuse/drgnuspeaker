from __future__ import annotations

import json
import queue
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

import sounddevice as sd

from .config import SpeakerConfig


class WakeDetector(ABC):
    @abstractmethod
    def wait_for_wake(self) -> None:
        raise NotImplementedError


class KeyboardWakeDetector(WakeDetector):
    def wait_for_wake(self) -> None:
        input("Press Enter to simulate wake word: ")


class ButtonWakeDetector(WakeDetector):
    def __init__(self, gpio_pin: Optional[int]) -> None:
        self._gpio_pin = gpio_pin

    def wait_for_wake(self) -> None:
        if self._gpio_pin is None:
            raise RuntimeError("DRGNU_PTT_GPIO_PIN is required for button wake mode")
        raise NotImplementedError("GPIO button wake mode will be wired in the Jetson hardware pass")


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

        recognizer = KaldiRecognizer(self._model, self._sample_rate)
        audio_queue: "queue.Queue[bytes]" = queue.Queue()
        started_at = time.monotonic()

        def callback(indata: bytes, frames: int, time_info: object, status: object) -> None:
            if status:
                print(f"[drgnu-speaker] wake audio status={status}", flush=True)
            audio_queue.put(bytes(indata))

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
                    if self._contains_wake_phrase(text):
                        return
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
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


def build_wake_detector(config: SpeakerConfig) -> WakeDetector:
    if config.wake_mode == "keyboard":
        return KeyboardWakeDetector()
    if config.wake_mode == "button":
        return ButtonWakeDetector(config.ptt_gpio_pin)
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
