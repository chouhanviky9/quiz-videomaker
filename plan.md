## Plan: Quiz Video Automation System (Python)

A Python-based pipeline that reads quiz data from a Google Sheet, generates multilingual TTS narration via Gemini 2.5 Flash, composes quiz video frames (question + 4 options + countdown timer + answer reveal) using MoviePy, mixes in sound effects, and uploads the final MP4 to Google Drive — all triggered by a single command.

### Steps

1. **Scaffold project structure** — Create the following layout in the empty workspace:
   - `main.py` — CLI entry point (accepts sheet ID, language, voice, logo path)
   - `config.py` — Constants (colors, fonts, durations, scopes, sheet range)
   - `auth.py` — Shared OAuth 2.0 flow for Sheets + Drive (single `credentials.json` / `token.json`)
   - `sheets.py` — Read quiz rows (columns: `#, QUESTION, A, B, C, D, ANSWER, LETTER`)
   - `tts.py` — Generate per-question narration WAV via `gemini-2.5-flash-preview-tts`
   - `renderer.py` — Build each 13-second question clip (question frame → 10s countdown → answer reveal)
   - `composer.py` — Concatenate all question clips + intro/end screen, mix SFX, export MP4
   - `uploader.py` — Upload final video to a Google Drive folder
   - `assets/` — Fonts (`.ttf`), sound effects (tick, correct, wrong), logo templates, end-screen template
   - `requirements.txt` — All dependencies
   - `.env.example` — Template for `GEMINI_API_KEY`, `SPREADSHEET_ID`, `DRIVE_FOLDER_ID`
   - `README.md` — Setup guide + Google Sheet format spec

2. **Implement Google Sheets reader (`sheets.py`)** — Use `google-api-python-client` with `spreadsheets.readonly` scope to fetch all quiz rows; parse each row into a `Question` dataclass (`number, text, option_a/b/c/d, answer, letter`); validate that every row has all 8 columns populated.

3. **Implement Gemini TTS generator (`tts.py`)** — For each `Question`, call `gemini-2.5-flash-preview-tts` with a natural-language prompt like *"Read this quiz question clearly: {question_text}"*; configure `SpeechConfig` with a chosen `voice_name` (e.g., Kore for French, Puck for English); save the returned PCM data as a 24 kHz WAV file in a `temp/audio/` directory. Support a `--language` flag that adjusts the prompt language automatically.

4. **Implement video renderer (`renderer.py`)** — Recreate the quiz frame layout shown in the reference image using MoviePy v2.0:
   - **Background**: `ColorClip` (blue `#1a3a8a`, 1920×1080)
   - **Header**: Red gradient bar with question number badge (top-left circle) + question text (`TextClip`, bold white, centered)
   - **Options grid**: 2×2 layout of rounded-rectangle option cards (white fill, orange letter badge A/B/C/D, dark blue text) — rendered as `ImageClip` via Pillow for rounded corners
   - **Countdown bar**: Animated green progress bar (shrinks over 10 seconds) at the bottom
   - **Answer reveal**: At t=10s, highlight the correct option in green and flash incorrect ones red; hold for 3s
   - Overlay the TTS audio starting at t=0; add tick SFX during countdown, correct/wrong SFX at reveal

5. **Implement video composer (`composer.py`)** — Concatenate all per-question clips via `concatenate_videoclips`; prepend an optional intro clip and append an end-screen clip (logo-swappable PNG template rendered as `ImageClip`); add background music track (low volume) across the full duration; export as `1080p MP4` at 30 fps using `libx264`.

6. **Implement Drive uploader (`uploader.py`)** — Use `drive.file` scope + `MediaFileUpload` to upload the final MP4 to a specified folder; print the shareable link on success. Reuse the same OAuth token from `auth.py`.

### Further Considerations

1. **Rounded-rectangle option cards** — MoviePy's `TextClip` can't natively draw rounded rects. Recommendation: pre-render each option card as a PNG via **Pillow** (`ImageDraw.rounded_rectangle`) and load them as `ImageClip`. Agree?
2. **Server deployment vs. local** — OAuth 2.0 desktop flow requires a browser for first auth. For headless servers, should we use a **service account** with domain-wide delegation instead, or do the initial auth locally and copy the `token.json` to the server?
3. **End-screen customization** — Should the end screen be a static image template (logo + channel name overlaid via Pillow) or a short animated outro clip? Static is simpler and more flexible across channels.
