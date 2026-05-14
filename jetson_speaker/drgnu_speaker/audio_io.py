from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sounddevice as sd
import soundfile as sf

from .config import SpeakerConfig


class AudioRecorder:
    def __init__(self, config: SpeakerConfig) -> None:
        self._config = config
        self._config.work_dir.mkdir(parents=True, exist_ok=True)

    def record_once(self) -> Path:
        frame_count = int(self._config.sample_rate * self._config.record_seconds)
        audio = sd.rec(
            frame_count,
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype="float32",
        )
        sd.wait()

        filename = datetime.utcnow().strftime("drgnu_%Y%m%d_%H%M%S.wav")
        output_path = self._config.work_dir / filename
        sf.write(output_path, audio, self._config.sample_rate)
        return output_path

