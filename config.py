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
OUTPUT_DIR = BASE_DIR / "output"

# Create dirs on import
for d in (TEMP_DIR, AUDIO_DIR, FRAMES_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── API Keys & IDs ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

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

# ── Timing (seconds) ────────────────────────────────────────────────────────
QUESTION_DURATION = 13       # total time per question
COUNTDOWN_DURATION = 10      # countdown timer length
ANSWER_REVEAL_DURATION = 3   # time the correct answer is shown
INTRO_DURATION = 4           # intro screen hold time
ENDSCREEN_DURATION = 5       # end screen hold time

# ── Colors (RGB tuples) ─────────────────────────────────────────────────────
COLOR_BG_BLUE = (26, 58, 138)            # #1a3a8a — main background
COLOR_HEADER_RED = (239, 68, 68)         # #ef4444 — header bar
COLOR_HEADER_RED_DARK = (185, 28, 28)    # #b91c1c — header gradient bottom
COLOR_WHITE = (255, 255, 255)
COLOR_OPTION_TEXT = (30, 58, 138)        # dark navy for option text
COLOR_BADGE_ORANGE = (249, 115, 22)      # #f97316 — A/B/C/D badge
COLOR_BADGE_RED = (220, 38, 38)          # #dc2626 — C/D badge
COLOR_CORRECT_GREEN = (34, 197, 94)      # #22c55e — correct answer highlight
COLOR_WRONG_RED = (239, 68, 68)          # #ef4444 — wrong answer highlight
COLOR_TIMER_GREEN = (74, 222, 128)       # #4ade80 — countdown bar fill
COLOR_TIMER_BG = (209, 213, 219)         # #d1d5db — countdown bar background
COLOR_NUMBER_BADGE_BG = (37, 99, 235)    # #2563eb — question number circle
COLOR_BLACK = (0, 0, 0)

# ── Fonts ────────────────────────────────────────────────────────────────────
FONT_BOLD = str(FONTS_DIR / "Montserrat-Bold.ttf")
FONT_EXTRABOLD = str(FONTS_DIR / "Montserrat-ExtraBold.ttf")
FONT_REGULAR = str(FONTS_DIR / "Montserrat-Regular.ttf")

# ── Gemini TTS ───────────────────────────────────────────────────────────────
TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_SAMPLE_RATE = 24000   # 24 kHz PCM output

# Default voices per language (client can override in CONFIG tab)
DEFAULT_VOICES = {
    "en": "Puck",
    "fr": "Kore",
    "es": "Aoede",
    "de": "Charon",
    "ar": "Sadachbia",
    "pt": "Achernar",
    "hi": "Algieba",
    "ja": "Callirrhoe",
    "ko": "Autonoe",
    "tr": "Gacrux",
}

# ── Sound effects ────────────────────────────────────────────────────────────
SFX_TICK = str(SFX_DIR / "tick.mp3")
SFX_CORRECT = str(SFX_DIR / "correct.mp3")
SFX_WRONG = str(SFX_DIR / "wrong.mp3")
SFX_INTRO = str(SFX_DIR / "intro.mp3")
