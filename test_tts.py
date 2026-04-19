import sys
import logging
from config.constant import GEMINI_API_KEY
from tts import _generate_audio_cloud
from pathlib import Path

logging.basicConfig(level=logging.INFO)

print(f"API Key startswith: {GEMINI_API_KEY[:5]}")

try:
    path = _generate_audio_cloud(
        text="Hello, this is a test of the Google Cloud Text to Speech API.",
        output_path=Path("temp/test_cloud_tts_en.wav"),
        row_index=1,
        language="en",
    )
    print(f"Success! Saved to {path}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
