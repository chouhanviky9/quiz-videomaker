"""
Quiz Video Maker — CLI entry point.

Reads BATCH_SIZE from the CONFIG tab, fetches that many unprocessed
questions, processes them (TTS → render → upload), marks them as
processed, and repeats until all questions are done.

Usage:
    python main.py                          # Process all pending questions
    python main.py --no-upload              # Render only, skip Drive upload
    python main.py --logo assets/logos/my_logo.png
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from config import SPREADSHEET_ID, DRIVE_FOLDER_ID

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("quiz-video-maker")


def process_batch_of_questions(
    batch_config,
    questions: list,
    spreadsheet_id: str,
    logo_path: str | None,
    bg_music_path: str | None,
    upload: bool,
    batch_number: int,
) -> None:
    """Process a single batch of questions: TTS → render → compose → upload → mark processed."""
    from sheets import mark_batch_done, mark_question_processed
    from tts import generate_batch_audio
    from composer import compose_video
    from uploader import upload_to_drive

    logger.info(f"── Batch {batch_number}: processing {len(questions)} question(s) ──")

    # Generate TTS audio
    logger.info("─── Phase 1: Generating TTS audio ───")
    audio_paths = generate_batch_audio(
        questions=questions,
        language=batch_config.language,
        voice=batch_config.voice or None,
    )

    # Compose video
    logger.info("─── Phase 2: Rendering video ───")
    video_path = compose_video(
        batch_config=batch_config,
        questions=questions,
        audio_paths=audio_paths,
        logo_path=logo_path,
        bg_music_path=bg_music_path,
    )

    # Upload to Drive
    video_url = ""
    if upload:
        logger.info("─── Phase 3: Uploading to Google Drive ───")
        try:
            video_url = upload_to_drive(video_path)
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            video_url = f"UPLOAD_FAILED: {e}"
    else:
        logger.info("Skipping upload (--no-upload flag)")
        video_url = f"LOCAL: {video_path}"

    # Mark each question as processed in the sheet
    for q in questions:
        try:
            mark_question_processed(q, spreadsheet_id)
        except Exception as e:
            logger.warning(f"Could not mark question row {q.row_index} as processed: {e}")

    logger.info(f"✅ Batch {batch_number} complete → {video_url}")


@click.command()
@click.option("--sheet-id", default=None, help="Google Sheet ID (overrides .env)")
@click.option("--logo", default=None, type=click.Path(exists=True), help="Path to channel logo PNG")
@click.option("--music", default=None, type=click.Path(exists=True), help="Path to background music file")
@click.option("--upload/--no-upload", default=True, help="Upload to Google Drive (default: yes)")
def main(sheet_id, logo, music, upload):
    """Quiz Video Maker — generate quiz videos from a Google Sheet."""
    from sheets import fetch_configs, get_pending_questions

    spreadsheet_id = sheet_id or SPREADSHEET_ID
    if not spreadsheet_id:
        logger.error("No spreadsheet ID. Set SPREADSHEET_ID in .env or pass --sheet-id")
        sys.exit(1)

    # Read config (language, voice, batch_size, etc.)
    configs = fetch_configs(spreadsheet_id)
    if not configs:
        logger.error("No config found in CONFIG tab")
        sys.exit(1)
    batch_config = configs[0]
    batch_size = batch_config.batch_size

    logger.info(f"Spreadsheet: {spreadsheet_id} | batch_size={batch_size} | lang={batch_config.language}")

    batch_number = 0
    while True:
        # Fetch up to batch_size unprocessed questions
        questions = get_pending_questions(spreadsheet_id, limit=batch_size)
        if not questions:
            if batch_number == 0:
                logger.info("No pending questions found. All rows are already processed.")
            else:
                logger.info(f"All questions processed after {batch_number} batch(es).")
            break

        batch_number += 1
        process_batch_of_questions(
            batch_config=batch_config,
            questions=questions,
            spreadsheet_id=spreadsheet_id,
            logo_path=logo,
            bg_music_path=music,
            upload=upload,
            batch_number=batch_number,
        )

    logger.info("🎬 All done!")


if __name__ == "__main__":
    main()
