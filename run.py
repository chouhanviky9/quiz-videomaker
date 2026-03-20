import logging
import time
import datetime
import shutil
from config.config import config
from config.constant import SPREADSHEET_ID, DRIVE_FOLDER_ID, TEMP_DIR, AUDIO_DIR, FRAMES_DIR, OUTPUT_DIR
from sheets import fetch_configs, get_pending_questions, mark_batch_done, append_result_row, move_questions_to_processed

def clear_temp_directory():
    """Wipes the temp directory and recreates the required subfolders."""
    logger.info("Cleaning up temp directory...")
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        
        # Recreate dirs immediately
        for d in (TEMP_DIR, AUDIO_DIR, FRAMES_DIR, OUTPUT_DIR):
            d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to clear temp directory: {e}")

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
) -> str:
    """Process a single batch of questions: TTS → render → compose → upload → mark processed."""
    from sheets import mark_question_processed
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

    logger.info(f"✅ Batch {batch_number} complete → {video_url}")
    return video_url

def main():
    logger.info("Starting Quiz Video Maker Watcher...")
    try:
        while True:
            config.refresh()
            spreadsheet_id = SPREADSHEET_ID
            if not spreadsheet_id:
                time.sleep(10)
                continue
            # print(batch_size = int(config.get("BATCH_SIZE", 2)))
            # return
            configs = fetch_configs(spreadsheet_id)
            if configs:
                batch_config = configs[0]
                batch_size = int(config.get("BATCH_SIZE", 2))
                
                questions = get_pending_questions(spreadsheet_id, limit=batch_size)
                
                if len(questions) >= batch_size:
                    logger.info(f"Sufficient batch size found: {len(questions)}/{batch_size}. Processing...")
                    
                    # Clear all temp files and output from previous runs
                    clear_temp_directory()
                    
                    # Determine background music index (1, 2, or 3)
                    bg_music_idx = str(config.get("BG_MUSIC", "1"))
                    selected_music_path = f"assets/sound/quizSong{bg_music_idx}.mp3"

                    video_url = process_batch_of_questions(
                        batch_config=batch_config,
                        questions=questions,
                        spreadsheet_id=spreadsheet_id,
                        logo_path="assets/logos/video-maker-logo.png",
                        bg_music_path=selected_music_path,
                        upload=True,
                        batch_number=batch_config.batch,
                    )
                    
                    logger.info("Writing results to RESULT tab...")
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    append_result_row([now_str, video_url], spreadsheet_id)
                    
                    logger.info("Moving questions to PROCESSED tab...")
                    move_questions_to_processed(questions, spreadsheet_id)
                    
                    logger.info("Batch completed successfully!")
                else:
                    logger.info(f"Listening... Not enough questions yet {len(questions)}/{batch_size}.")
                
            time.sleep(5)

    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()