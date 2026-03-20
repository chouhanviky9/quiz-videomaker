"""
Google Drive uploader — uploads the rendered MP4 to a Drive folder.
"""

from __future__ import annotations

import logging
from pathlib import Path

from googleapiclient.http import MediaFileUpload

from auth import get_drive_service
from config.constant import DRIVE_FOLDER_ID

logger = logging.getLogger(__name__)


def upload_to_drive(
    file_path: Path,
    folder_id: str | None = None,
    filename: str | None = None,
) -> str:
    """
    Upload a file to Google Drive.

    Args:
        file_path: Local path to the file to upload.
        folder_id: Google Drive folder ID. Defaults to DRIVE_FOLDER_ID from .env.
        filename: Name for the file in Drive. Defaults to the local filename.

    Returns:
        The shareable web link to the uploaded file.
    """
    folder_id = folder_id or DRIVE_FOLDER_ID
    filename = filename or file_path.name

    if not folder_id:
        raise ValueError("DRIVE_FOLDER_ID is not set. Add it to your .env file.")

    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    # Determine MIME type
    suffix = file_path.suffix.lower()
    mime_types = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
    }
    mimetype = mime_types.get(suffix, "application/octet-stream")

    media = MediaFileUpload(
        str(file_path),
        mimetype=mimetype,
        resumable=True,
        chunksize=50 * 1024 * 1024,  # 50 MB chunks for large videos
    )

    logger.info(f"Uploading {filename} ({file_path.stat().st_size / 1024 / 1024:.1f} MB) to Drive…")

    request = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"  Upload progress: {int(status.progress() * 100)}%")

    file_id = response.get("id")
    web_link = response.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")

    # Make the file viewable by anyone with the link
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
    except Exception as e:
        logger.warning(f"Could not set public permissions: {e}")

    logger.info(f"✅ Uploaded: {web_link}")
    return web_link
