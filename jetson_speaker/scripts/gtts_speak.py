import sys
import tempfile
import os
import subprocess

def speak(text: str) -> None:
    text = text.strip()
    if not text:
        return

    if sys.platform == "win32":
        # Windows: Use native SpeechSynthesizer via PowerShell (no file locks, works headlessly)
        escaped_text = text.replace("'", "''").replace('"', '""')
        ps_code = f"""
        Add-Type -AssemblyName System.Speech
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $synth.Speak('{escaped_text}')
        """
        subprocess.run(["powershell", "-Command", ps_code], check=False)
    else:
        # Linux/Ubuntu: Use Google TTS + mpg123
        try:
            from gtts import gTTS
        except ImportError:
            print("[gtts-speak] gTTS library not found. Install it with: pip install gTTS", file=sys.stderr)
            sys.exit(1)
            
        tts = gTTS(text=text, lang="ko")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
        try:
            tts.save(temp_path)
            subprocess.run(["mpg123", "-q", temp_path], check=False)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gtts_speak.py <text_to_speak>", file=sys.stderr)
        sys.exit(1)
        
    text_arg = " ".join(sys.argv[1:])
    speak(text_arg)
