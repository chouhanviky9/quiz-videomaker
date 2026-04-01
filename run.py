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

        # Clear renderer caches for the new batch
        from renderer import clear_render_caches
        clear_render_caches()
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
    logo_path: str | None,
    bg_music_path: str | None,
    upload: bool,
    batch_number: int,
) -> str:
    """Process a single batch of questions: TTS → render → compose → upload."""
    from tts import generate_batch_audio
    from composer import compose_video
    from uploader import upload_to_drive

    logger.info(f"── Batch {batch_number}: processing {len(questions)} question(s) ──")

    # Generate TTS audio
    logger.info(f"─── Phase 1: Generating TTS audio (Language: {batch_config.language.upper()}) ───")
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
    while True:
        try:
            config.refresh()
            spreadsheet_id = SPREADSHEET_ID
            if not spreadsheet_id:
                time.sleep(10)
                continue
            # print(batch_size = int(config.get("BATCH_SIZE", 2)))
            # return
            configs, _raw_settings = fetch_configs(spreadsheet_id)
            if configs:
                batch_config = configs[0]
                # Check the dropdown switch
                if str(batch_config.status).strip().lower() != "start":
                    time.sleep(5)
                    continue

                logger.info("Detected 'Start'! Changing status to 'Processing'...")
                from sheets import set_config_status, set_error_message
                set_config_status(batch_config.row_index, "Processing", spreadsheet_id)
                set_error_message("", spreadsheet_id)

                try:
                    batch_size = int(config.get("BATCH_SIZE", 2))
                    
                    questions = get_pending_questions(spreadsheet_id, limit=batch_size)
                    
                    if len(questions) >= batch_size:
                        logger.info(f"Sufficient batch size found: {len(questions)}/{batch_size}. Processing...")
                        
                        # Clear all temp files and output from previous runs
                        clear_temp_directory()
                        
                        # Determine background music index (1, 2, or 3)
                        bg_music_idx = str(config.get("BG_MUSIC", "1"))
                        selected_music_path = f"assets/sound/quizSong{bg_music_idx}.mp3"

                        import urllib.request
                        from pathlib import Path
                        import shutil

                        def resolve_logo(key: str, default: str, dl_name: str) -> str:
                            val = str(config.get(key, "")).strip()
                            if not val:
                                return default
                            if val.startswith("http://") or val.startswith("https://"):
                                try:
                                    d_path = f"config/temp/{dl_name}"
                                    Path("config/temp").mkdir(parents=True, exist_ok=True)
                                    req = urllib.request.Request(val, headers={'User-Agent': 'Mozilla/5.0'})
                                    with urllib.request.urlopen(req) as res, open(d_path, 'wb') as out_f:
                                        shutil.copyfileobj(res, out_f)
                                    return d_path
                                except Exception as e:
                                    logger.warning(f"Failed download {key}: {e}")
                                    return default
                            if Path(val).exists(): return val
                            return default

                        default_logo = "assets/logos/video-maker-logo.png"
                        outrow_logo = resolve_logo("VIDEO_OUTROW_LOGO", default_logo, "outrow_logo.png")
                        topright_logo = resolve_logo("VIDEO_TOPRIGHT_LOGO", default_logo, "topright_logo.png")
                        
                        config.set("CURRENT_TOPRIGHT_LOGO", topright_logo)

                        import os
                        is_dev = os.getenv("MODE") == "DEV"
                        
                        if is_dev:
                            logger.info("DEV MODE ENABLED: Rendering only the first question. Uploading and sheet updates are disabled.")
                            questions = questions[:1]

                        video_url = process_batch_of_questions(
                            batch_config=batch_config,
                            questions=questions,
                            logo_path=outrow_logo,
                            bg_music_path=selected_music_path,
                            upload=not is_dev,
                            batch_number=batch_config.batch,
                        )
                        
                        if is_dev:
                            local_path = video_url.replace("LOCAL: ", "")
                            logger.info(f"Opening local test video: {local_path}")
                            import subprocess
                            subprocess.run(['open', local_path])
                            
                            logger.info("Resetting status to 'Stopped'...")
                            set_config_status(batch_config.row_index, "Stopped", spreadsheet_id)
                            continue
                        
                        logger.info("Writing results to RESULT tab...")
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        append_result_row([now_str, video_url], spreadsheet_id)
                        
                        logger.info("Moving questions to PROCESSED tab...")
                        move_questions_to_processed(questions, spreadsheet_id)
                        
                        logger.info("Marking batch config as DONE...")
                        mark_batch_done(batch_config, video_url, spreadsheet_id)
                        
                        logger.info("Batch completed successfully!")
                        logger.info("Resetting status to 'Stopped'...")
                        set_config_status(batch_config.row_index, "Stopped", spreadsheet_id)
                    else:
                        logger.info(f"Listening... Not enough questions yet {len(questions)}/{batch_size}.")
                        logger.info("Resetting status to 'Stopped'...")
                        set_config_status(batch_config.row_index, "Stopped", spreadsheet_id)

                except Exception as e:
                    logger.error(f"Error during video generation: {e}")
                    set_error_message(f"Error: {str(e)}", spreadsheet_id)
                    set_config_status(batch_config.row_index, "Stopped", spreadsheet_id)
                
            time.sleep(5)

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()