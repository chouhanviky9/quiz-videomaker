"""
Global configuration — colors, sizes, durations, scopes, paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
SFX_DIR = ASSETS_DIR / "sfx"
LOGOS_DIR = ASSETS_DIR / "logos"
TEMP_DIR = BASE_DIR / "temp"
AUDIO_DIR = TEMP_DIR / "audio"
FRAMES_DIR = TEMP_DIR / "frames"
OUTPUT_DIR = TEMP_DIR / "output" # Moved under temp directory

# Create dirs on import
for d in (TEMP_DIR, AUDIO_DIR, FRAMES_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── API Keys & IDs ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

# Service account JSON for Cloud TTS operations
GOOGLE_CREDENTIALS_TTS_PATH = BASE_DIR.parent / "credential-for-tts-new.json"

# ── Google API Scopes ────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",  # read + write STATUS/VIDEO_URL
    "https://www.googleapis.com/auth/drive.file",     # upload videos
]

# ── Sheet tab names & ranges ─────────────────────────────────────────────────
CONFIG_TAB = "CONFIG"
QUESTIONS_TAB = "QUESTIONS"
RESULT_TAB = "RESULT"
CONFIG_RANGE = f"{CONFIG_TAB}!A2:F"       # BATCH, LANGUAGE, VOICE, TITLE, STATUS, VIDEO_URL
QUESTIONS_RANGE = f"{QUESTIONS_TAB}!A2:H"  # QUESTION, A, B, C, D, ANSWER, LETTER, PROCESSED
RESULT_RANGE = f"{RESULT_TAB}!A2:B"      # DateTime, VIDEO_URL

# ── Video dimensions ─────────────────────────────────────────────────────────
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30


# ── Fonts ────────────────────────────────────────────────────────────────────
FONT_BOLD = str(FONTS_DIR / "Montserrat-Bold.ttf")
FONT_EXTRABOLD = str(FONTS_DIR / "Montserrat-ExtraBold.ttf")
FONT_REGULAR = str(FONTS_DIR / "Montserrat-Regular.ttf")

# ── Google Cloud TTS ─────────────────────────────────────────────────────────
TTS_SAMPLE_RATE = 24000   # 24 kHz PCM output

# Default voices per language (client can override in CONFIG tab)
# Using high-quality Journey and Neural2 voices
DEFAULT_VOICES = {
    "en": "en-US-Chirp3-HD-Rasalgethi",
    "fr": "fr-FR-Chirp3-HD-Rasalgethi",
    "es": "es-ES-Chirp3-HD-Rasalgethi",
    "de": "de-DE-Chirp3-HD-Rasalgethi",
    "ar": "ar-XA-Chirp3-HD-Rasalgethi",
    "pt": "pt-BR-Chirp3-HD-Rasalgethi",
    "hi": "hi-IN-Chirp3-HD-Rasalgethi",
    "ja": "ja-JP-Chirp3-HD-Rasalgethi",
    "ko": "ko-KR-Chirp3-HD-Rasalgethi",
    "tr": "tr-TR-Chirp3-HD-Rasalgethi",
}

# ── Sound effects ────────────────────────────────────────────────────────────
SFX_TICK = str(SFX_DIR / "tick.mp3")
SFX_CORRECT = str(SFX_DIR / "correct.mp3")
SFX_WRONG = str(SFX_DIR / "wrong.mp3")
SFX_INTRO = str(SFX_DIR / "intro.mp3")
