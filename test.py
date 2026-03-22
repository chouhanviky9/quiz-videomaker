from pathlib import Path
from sheets import Question
from renderer import build_question_clip
from tts import generate_batch_audio
def main():
    q = Question(
        text="What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France What is the capital of France?",
        option_a="London",
        option_b="Berlin",
        option_c="Paris",
        option_d="Madrid",
        answer="Paris",
        letter="C",
        processed=False,
        row_index=2
    )
    generate_batch_audio([q,q],'en')   
    print(f"Building single question clip...")
    
    # We can pass an audio_path if we want, or None to skip TTS.
    # We will pass None here for a quick visual test.
    clip = build_question_clip(q, audio_path="./assets/sound/quizSong1.mp3")

    output_path = "test_question.mp4"
    print(f"Writing video to {output_path}...")
    
    # Use moviepy to write the file with higher bitrate to preserve the smooth supersampled edges
    clip.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="100000k",
        threads=4,
        logger="bar"
    )

    print(f"Saved test video to {output_path}")

if __name__ == "__main__":
    main()


# import os
# from datetime import datetime

# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build

# from config.config import SPREADSHEET_ID
# from config.constant import (
# GEMINI_API_KEY,
# DRIVE_FOLDER_ID,
# GOOGLE_CREDENTIALS_PATH,
# GOOGLE_TOKEN_PATH,
# )

# SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
# CLIENT_SECRETS_FILE = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS", "client_secret.json")
# TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_PATH", "token.json")


# def get_oauth_credentials() -> Credentials:
#     creds = None

#     if os.path.exists(TOKEN_FILE):
#         creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
#             creds = flow.run_local_server(port=0)

#         with open(TOKEN_FILE, "w", encoding="utf-8") as f:
#             f.write(creds.to_json())

#     return creds


# def append_result_row(values: list[str]) -> None:
#     creds = get_oauth_credentials()
#     service = build("sheets", "v4", credentials=creds)

#     service.spreadsheets().values().append(
#         spreadsheetId=SPREADSHEET_ID,
#         range="RESULT!A:Z",
#         valueInputOption="USER_ENTERED",
#         insertDataOption="INSERT_ROWS",
#         body={"values": [values]},
#     ).execute()


# if __name__ == "__main__":
#     if not SPREADSHEET_ID:
#         raise SystemExit("Missing SPREADSHEET_ID env var")

#     append_result_row(
#         [
#             "TEST",
#             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             "ok",
#             "hello from oauth append",
#         ]
#     )
#     print("Appended one row to RESULT.")