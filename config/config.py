import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Setup paths based on your workspace structure
BASE_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = BASE_DIR / "assets" / "fonts"
SFX_DIR = BASE_DIR / "assets" / "sfx"

class Config:
    def __init__(self):
        # Hooks registry for config changes
        self._hooks = []
        
        # Default configuration data dict
        self._data = {
            # Colors (RGB)
            "COLOR_BG_BLUE": (1, 65, 163),
            "COLOR_HEADER_RED": (225, 77, 77),
            "COLOR_HEADER_RED_DARK": (225, 77, 77),
            "COLOR_WHITE": (255, 255, 255),
            "COLOR_OPTION_TEXT": (28, 30, 57),
            "COLOR_BADGE_ORANGE": (249, 115, 22),
            "COLOR_BADGE_RED": (220, 38, 38),
            "COLOR_BADGE_GRADIENT_TOP": (255, 130, 20),
            "COLOR_BADGE_GRADIENT_BOTTOM": (220, 30, 30),
            "COLOR_CORRECT_GREEN": (99, 243, 46),
            "COLOR_WRONG_RED": (239, 68, 68),
            "COLOR_TIMER_GREEN": (74, 222, 128),
            "COLOR_TIMER_BG": (209, 213, 219),
            "COLOR_NUMBER_BADGE_BG": (37, 99, 235),
            "COLOR_BLACK": (0, 0, 0),
            "COLOR_SHADOW_DARK": (10, 10, 40),
            
            # Fonts
            "FONT_BOLD": str(FONTS_DIR / "Montserrat-Bold.ttf"),
            "FONT_EXTRABOLD": str(FONTS_DIR / "Montserrat-ExtraBold.ttf"),
            "FONT_REGULAR": str(FONTS_DIR / "Montserrat-Regular.ttf"),
            
            # Gemini TTS
            "TTS_MODEL": "gemini-2.5-flash-preview-tts",
            "TTS_SAMPLE_RATE": 24000,
            "DEFAULT_VOICES": {
                "en": "Puck", "fr": "Kore", "es": "Aoede", "de": "Charon",
                "ar": "Sadachbia", "pt": "Achernar", "hi": "Algieba",
                "ja": "Callirrhoe", "ko": "Autonoe", "tr": "Gacrux",
            },
            
            # Sounds
            "SFX_TICK": str(SFX_DIR / "tick.mp3"),
            "SFX_CORRECT": str(SFX_DIR / "correct.mp3"),
            "SFX_WRONG": str(SFX_DIR / "wrong.mp3"),
            "SFX_INTRO": str(SFX_DIR / "intro.mp3"),

            # Video timing (seconds)
            "QUESTION_DURATION": 13,       # total time per question
            "COUNTDOWN_DURATION": 10,      # countdown timer length
            "ANSWER_REVEAL_DURATION": 3,   # time the correct answer is shown
            "INTRO_DURATION": 1,           # intro screen hold time
            "ENDSCREEN_DURATION": 5,       # end screen hold time

            # Dynamic logo URL (loaded from CONFIG sheet, can be https:// or data:image/... base64)
            "VIDEO_TOPRIGHT_LOGO": "",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Magic Methods for Direct Attribute Access 
    # (e.g., config.COLOR_BG_BLUE = (0,0,0) or print(config.COLOR_BG_BLUE))
    # ─────────────────────────────────────────────────────────────────────────
    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        # Prevent recursion for internal attributes
        if name in ["_data", "_hooks"]:
            super().__setattr__(name, value)
        else:
            self.set(name, value)

    # ─────────────────────────────────────────────────────────────────────────
    # Getters, Setters, and Sync logic
    # ─────────────────────────────────────────────────────────────────────────
    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        old_value = self._data.get(key)

        # Auto-coerce string values to match the type of the existing default
        if isinstance(value, str) and old_value is not None:
            try:
                if isinstance(old_value, int):
                    value = int(value)
                elif isinstance(old_value, float):
                    value = float(value)
                elif isinstance(old_value, tuple):
                    val_str = value.strip()
                    if val_str.startswith("#"):
                        h = val_str.lstrip("#")
                        # Handle both #RGB and #RRGGBB formats just in case, though 6-char is standard
                        if len(h) == 3:
                            h = "".join([c*2 for c in h])
                        value = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                    else:
                        # Parse "(R, G, B)" or "R, G, B" strings into tuples
                        cleaned = val_str.strip("()")
                        value = tuple(int(x.strip()) for x in cleaned.split(","))
            except (ValueError, TypeError):
                pass  # Keep as string if conversion fails

        self._data[key] = value
        
        # Only notify hooks if the value actually changed
        if old_value != value:
            self._trigger_hooks(key, value, old_value)

    def update_from_dict(self, new_data: dict):
        """Update multiple keys at once, fetching via sheets."""
        for k, v in new_data.items():
            if v == "" or v is None:
                continue
            if k == "" or k is None:
                continue
            self.set(k, v)

    def refresh(self):
        """Fetch config from Google sheets and update the local store."""
        try:
            from sheets import fetch_configs
            result = fetch_configs()
            if result:
                configs, raw_settings = result
                # Use raw_settings dict which has ALL key-value pairs from the sheet
                # (BatchConfig only has a subset of fields)
                if raw_settings:
                    print(f"Fetched config from sheet: {raw_settings}")
                    self.update_from_dict(raw_settings)
        except ImportError as e:
            print(f"Warning: Could not fetch configs. Error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Hooks System
    # ─────────────────────────────────────────────────────────────────────────
    def add_hook(self, callback):
        """
        Register a function to perform an action when a config changes.
        The callback should accept 3 arguments: (key, new_value, old_value)
        """
        if callback not in self._hooks:
            self._hooks.append(callback)

    def _trigger_hooks(self, key, new_value, old_value):
        """Internal method to run hooks after a setter is invoked"""
        for hook in self._hooks:
            try:
                hook(key, new_value, old_value)
            except Exception as e:
                print(f"Config hook error on '{key}': {e}")

# Instantiate a singleton to be imported safely across all files
config = Config()
