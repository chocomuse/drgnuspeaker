from __future__ import annotations

import shlex
import subprocess


class TextToSpeech:
    def __init__(self, command: str) -> None:
        self._command = command.strip()

    def speak(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        if not self._command:
            print(text)
            return

        args = shlex.split(self._command)
        subprocess.run([*args, text], check=False)

