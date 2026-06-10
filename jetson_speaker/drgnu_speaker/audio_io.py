from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import time

import sounddevice as sd
import soundfile as sf
import numpy as np

from .config import SpeakerConfig


class AudioRecorder:
    def __init__(self, config: SpeakerConfig) -> None:
        self._config = config
        self._config.work_dir.mkdir(parents=True, exist_ok=True)

    def record_once(self, record_seconds: Optional[float] = None) -> Path:
        max_duration = record_seconds if record_seconds is not None else self._config.record_seconds
        sample_rate = self._config.sample_rate
        channels = self._config.channels
        
        # Record in 100ms (0.1s) chunks
        block_duration = 0.1
        block_size = int(sample_rate * block_duration)
        
        recorded_chunks = []
        silence_duration = 0.0
        max_silence_limit = 3.0
        
        # Threshold for silence in 16-bit integer scale
        silence_threshold = 200.0
        
        print(f"[drgnu-speaker] recording started (max: {max_duration}s, silence timeout: {max_silence_limit}s)...", flush=True)
        
        with sd.InputStream(samplerate=sample_rate, channels=channels, dtype="int16") as stream:
            start_time = time.time()
            while (time.time() - start_time) < max_duration:
                chunk, overflowed = stream.read(block_size)
                recorded_chunks.append(chunk)
                
                # Calculate root-mean-square (RMS) of the chunk to detect voice activity
                rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                
                if rms < silence_threshold:
                    silence_duration += block_duration
                else:
                    silence_duration = 0.0
                    
                if silence_duration >= max_silence_limit:
                    print(f"[drgnu-speaker] silence detected for {max_silence_limit}s, stopping recording early.", flush=True)
                    break
                    
        if recorded_chunks:
            audio = np.concatenate(recorded_chunks, axis=0)
        else:
            audio = np.zeros((0, channels), dtype="int16")
            
        filename = datetime.utcnow().strftime("drgnu_%Y%m%d_%H%M%S.wav")
        output_path = self._config.work_dir / filename
        sf.write(output_path, audio, sample_rate)
        return output_path
