"""
Google Sheets reader — fetches CONFIG + QUESTIONS tabs,
returns typed dataclasses ready for the pipeline.

QUESTIONS sheet layout (row 1 = header, data starts at row 2):
  Col A: Question
  Col B: Option A
  Col C: Option B
  Col D: Option C
  Col E: Option D
  Col F: Answer (full text)
  Col G: Letter (A / B / C / D)
  Col H: Processed (empty = pending, "YES" = done)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from auth import get_sheets_service
from config import SPREADSHEET_ID, CONFIG_RANGE, QUESTIONS_RANGE, CONFIG_TAB, QUESTIONS_TAB

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class BatchConfig:
    batch: int
    batch_size: int      # how many questions to process per run
    language: str
    voice: str
    title: str
    status: str          # empty = pending, "DONE" = already processed
    video_url: str       # filled after upload
    row_index: int       # 0-based index in the sheet (for writing STATUS back)


@dataclass
class Question:
    text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    answer: str
    letter: str          # "A" | "B" | "C" | "D"
    processed: bool      # True if already processed
    row_index: int       # 1-based sheet row (for marking processed)


# ── Sheet reading ────────────────────────────────────────────────────────────

def fetch_configs(spreadsheet_id: Optional[str] = None) -> list[BatchConfig]:
    """Read the CONFIG tab as vertical key/value config and return a single BatchConfig."""
    sid = spreadsheet_id or SPREADSHEET_ID
    service = get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=CONFIG_RANGE)  # "CONFIG!A1:B"
        .execute()
    )
    rows = result.get("values", [])
    settings: dict[str, str] = {}
    status_row_index: int | None = None  # sheet row where STATUS lives
    for i, row in enumerate(rows):
        if not row:
            continue
        key = row[0].strip()
        if not key:
            continue
        value = row[1].strip() if len(row) > 1 else ""
        settings[key.upper()] = value
        if key.upper() == "STATUS":
            # CONFIG_RANGE starts at row 1 → sheet row = i + 1
            status_row_index = i + 1
    # Extract fields with defaults
    batch_num = int(settings.get("BATCH", "1"))
    batch_size = int(settings.get("BATCH_SIZE", "2"))
    language = settings.get("LANGUAGE", "en").lower()
    voice = settings.get("VOICE", "")
    title = settings.get("TITLE", f"Batch {batch_num}")
    status = settings.get("STATUS", "")
    video_url = settings.get("VIDEO_URL", "")
    row_index = status_row_index or 1  # used by mark_batch_done
    config = BatchConfig(
        batch=batch_num,
        batch_size=batch_size,
        language=language,
        voice=voice,
        title=title,
        status=status,
        video_url=video_url,
        row_index=row_index,
    )
    print(f"Config: {config}")
    return [config]


def fetch_questions(spreadsheet_id: Optional[str] = None) -> list[Question]:
    """Read the QUESTIONS tab and return all question rows."""
    sid = spreadsheet_id or SPREADSHEET_ID
    service = get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=QUESTIONS_RANGE)
        .execute()
    )
    rows = result.get("values", [])
    questions: list[Question] = []

    for i, row in enumerate(rows):
        # Minimum 7 columns required (question + 4 options + answer + letter)
        if len(row) < 7:
            logger.warning(f"QUESTIONS row {i + 2}: expected ≥7 columns, got {len(row)} — skipping")
            continue

        text, a, b, c, d, answer, letter = row[:7]
        if not text.strip():
            continue

        # Column H (index 7) = processed flag
        processed_str = row[7].strip().upper() if len(row) > 7 else ""
        is_processed = processed_str in ("YES", "TRUE", "DONE", "1")

        questions.append(
            Question(
                text=text.strip(),
                option_a=a.strip(),
                option_b=b.strip(),
                option_c=c.strip(),
                option_d=d.strip(),
                answer=answer.strip(),
                letter=letter.strip().upper(),
                processed=is_processed,
                row_index=i + 2,  # header is row 1, data starts at row 2
            )
        )

    return questions


def get_pending_questions(spreadsheet_id: Optional[str] = None, limit: int = 0) -> list[Question]:
    """Return only questions where Processed column is empty (not yet processed).
    
    Args:
        limit: max number of questions to return. 0 = all.
    """
    questions = fetch_questions(spreadsheet_id)
    pending = [q for q in questions if not q.processed]
    if limit > 0:
        pending = pending[:limit]
    return pending


def mark_question_processed(question: Question, spreadsheet_id: Optional[str] = None):
    """Write 'YES' to the Processed column (H) for the given question row."""
    sid = spreadsheet_id or SPREADSHEET_ID
    service = get_sheets_service()
    row = question.row_index

    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range=f"{QUESTIONS_TAB}!H{row}",
        valueInputOption="RAW",
        body={"values": [["YES"]]},
    ).execute()

    logger.info(f"Question row {row} marked as processed")


def mark_batch_done(batch_config: BatchConfig, video_url: str, spreadsheet_id: Optional[str] = None):
    """Write STATUS=DONE and VIDEO_URL back to the CONFIG tab for this batch row."""
    import datetime

    sid = spreadsheet_id or SPREADSHEET_ID
    service = get_sheets_service()
    row = batch_config.row_index

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status_value = f"DONE ({timestamp})"

    # Update STATUS (column E) and VIDEO_URL (column F)
    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range=f"{CONFIG_TAB}!E{row}:F{row}",
        valueInputOption="RAW",
        body={"values": [[status_value, video_url]]},
    ).execute()

    logger.info(f"Batch {batch_config.batch} marked DONE in sheet row {row}")


def append_result_row(values: list[str], spreadsheet_id: Optional[str] = None) -> None:
    """
    Appends one row to RESULT tab.
    `values` must be ordered exactly like your RESULT columns.
    """
    sid = spreadsheet_id or SPREADSHEET_ID
    service = get_sheets_service()
    service.spreadsheets().values().append(
        spreadsheetId=sid,
        range="RESULT!A:Z",           # adjust width if needed
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]},
    ).execute()


def _get_sheet_id_by_title(service, spreadsheet_id: str, title: str) -> int:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties"
    ).execute()
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        if props.get("title") == title:
            return props["sheetId"]
    raise ValueError(f"Sheet tab not found: {title}")
def insert_result_row_top(values: list[str], spreadsheet_id: Optional[str] = None, tab_name: str = "RESULT") -> None:
    """
    Inserts a new row just below the header in RESULT (row 2), shifting existing rows down,
    then writes `values` into that new row starting at column A.
    """
    sid = spreadsheet_id or SPREADSHEET_ID
    service = get_sheets_service()
    result_sheet_id = _get_sheet_id_by_title(service, sid, tab_name)
    # Insert at index 1 => row 2 (assuming row 1 is header). If you have no header, use startIndex=0.
    service.spreadsheets().batchUpdate(
        spreadsheetId=sid,
        body={
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": result_sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 1,
                            "endIndex": 2,
                        },
                        "inheritFromBefore": False
                    }
                }
            ]
        },
    ).execute()
    # Write into the inserted row (row 2)
    # If you only care about A and B, you can use range="RESULT!A2:B2"
    service.spreadsheets().values().update(
        spreadsheetId=sid,
        range="RESULT!A2:B2",
        valueInputOption="RAW",
        body={"values": [values[:2]]},
    ).execute()