from __future__ import annotations

from abc import ABC, abstractmethod

from .config import SpeakerConfig


class WakeDetector(ABC):
    @abstractmethod
    def wait_for_wake(self) -> None:
        raise NotImplementedError


class KeyboardWakeDetector(WakeDetector):
    def wait_for_wake(self) -> None:
        input("Press Enter to simulate wake word: ")


class ButtonWakeDetector(WakeDetector):
    def __init__(self, gpio_pin: int | None) -> None:
        self._gpio_pin = gpio_pin

    def wait_for_wake(self) -> None:
        if self._gpio_pin is None:
            raise RuntimeError("DRGNU_PTT_GPIO_PIN is required for button wake mode")
        raise NotImplementedError("GPIO button wake mode will be wired in the Jetson hardware pass")


def build_wake_detector(config: SpeakerConfig) -> WakeDetector:
    if config.wake_mode == "keyboard":
        return KeyboardWakeDetector()
    if config.wake_mode == "button":
        return ButtonWakeDetector(config.ptt_gpio_pin)
    raise RuntimeError(
        f"Unsupported wake mode '{config.wake_mode}'. Use keyboard or button for the MVP."
    )

