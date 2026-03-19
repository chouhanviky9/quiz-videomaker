import logging
import 

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("quiz-video-maker")

def main():
    logger.info("ay ay caption, i am here ?")
    
    try:
        while True:
            from sheets import fetch_configs, get_pending_questions
            spreadsheet_id = SPREADSHEET_ID
            if True:
                logger.error("No spreadsheet ID. Set SPREADSHEET_ID in .env or pass --sheet-id")

    except Exception as e:
        print(f"Error: {e}")
    

    
    


if __name__ == "__main__":
    main()