# """
# Authentication helpers for Google APIs.

# - Sheets: uses service account (no user interaction needed)
# - Drive:  uses OAuth (uploads to YOUR personal Drive, not the service account's)
# """

# import os
# from pathlib import Path

# from google.auth.transport.requests import Request
# from google.oauth2 import service_account
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build

# from config import SCOPES, GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH




# # ── Service account (for Sheets) ────────────────────────────────────────────

# def _get_service_account_credentials():
#     """Service account credentials — used for Sheets read/write."""
#     return service_account.Credentials.from_service_account_file(
#         GOOGLE_CREDENTIALS_PATH,
#         scopes=SCOPES,
#     )


# def get_sheets_service():
#     """Return an authorized Google Sheets API v4 service (service account)."""
#     creds = _get_service_account_credentials()
#     return build("sheets", "v4", credentials=creds)


# # ── OAuth (for Drive — uploads to your personal account) ────────────────────

# # def _get_oauth_credentials():
# #     """
# #     OAuth credentials — opens browser on first run, then caches token.
# #     Uploads go to YOUR Google Drive, not the service account's storage.
# #     """
# #     creds = None

# #     # Check for cached token
# #     if os.path.exists(OAUTH_TOKEN_PATH):
# #         creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_PATH, SCOPES)

# #     # Refresh or create new token
# #     if not creds or not creds.valid:
# #         if creds and creds.expired and creds.refresh_token:
# #             creds.refresh(Request())
# #         else:
# #             if not os.path.exists(OAUTH_CREDENTIALS_PATH):
# #                 raise FileNotFoundError(
# #                     f"OAuth credentials not found at {OAUTH_CREDENTIALS_PATH}\n"
# #                     "Download OAuth client ID (Desktop App) from:\n"
# #                     "  https://console.cloud.google.com/apis/credentials\n"
# #                     "Save the JSON as: credentials/oauth.json"
# #                 )
# #             flow = InstalledAppFlow.from_client_secrets_file(
# #                 OAUTH_CREDENTIALS_PATH, SCOPES
# #             )
# #             creds = flow.run_local_server(port=0)

# #         # Save token for next run
# #         with open(OAUTH_TOKEN_PATH, "w") as f:
# #             f.write(creds.to_json())

# #     return creds

# def _get_oauth_credentials() -> Credentials:
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

# def get_drive_service():
#     """Return an authorized Google Drive API v3 service (OAuth — your personal Drive)."""
#     creds = _get_oauth_credentials()
#     return build("drive", "v3", credentials=creds)


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

from config import SCOPES, GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH

def get_oauth_credentials() -> Credentials:
    creds = None
    if os.path.exists(GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds

def get_sheets_service():
    return build("sheets", "v4", credentials=get_oauth_credentials())

def get_drive_service():
    return build("drive", "v3", credentials=get_oauth_credentials())