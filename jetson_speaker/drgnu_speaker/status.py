from __future__ import annotations

from enum import Enum


class SpeakerState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    RECORDING = "recording"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class StatusReporter:
    def set_state(self, state: SpeakerState) -> None:
        print(f"[drgnu-speaker] state={state.value}", flush=True)

