import os
import sys
import time
from dotenv import load_dotenv

# Ensure the root of the project is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drgnu_speaker.config import load_config
from drgnu_speaker.tts import TextToSpeech
from drgnu_speaker.wifi_provisioner import WifiProvisioner

def main():
    # Load settings from .env
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(dotenv_path)
    
    config = load_config()
    
    # Use standard console printer for TTS in test script to prevent subprocess failures
    class MockTTS(TextToSpeech):
        def __init__(self):
            super().__init__("")
        def speak(self, text: str) -> None:
            print(f"[TTS Audio Output]: {text}")
            
    tts = MockTTS()
    
    print("Initializing WifiProvisioner in simulation mode...")
    provisioner = WifiProvisioner(config, tts)
    
    # Force connection check to fail to trigger provisioning server
    provisioner.is_connected = lambda: False
    
    print("\nStarting Wi-Fi Setup simulation...")
    print("=================================================================")
    print("Open your browser and navigate to: http://localhost:8080")
    print("If run with Administrator privileges, it may bind to port 80:")
    print("http://localhost")
    print("You should see the premium dark-mode Wi-Fi setup page.")
    print("=================================================================\n")
    
    try:
        provisioner.ensure_connected()
    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")
    except Exception as e:
        print(f"\nSimulation error: {e}")

if __name__ == "__main__":
    main()
