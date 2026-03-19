from pathlib import Path
from uploader import upload_to_drive
from datetime import datetime
from sheets import insert_result_row_top
from config import SPREADSHEET_ID
from auth import get_sheets_service
# video_path = Path("output") / "batch1_Batch_1.mp4"
# link = upload_to_drive(video_path)
# print("Uploaded file link:", link)
insert_result_row_top(["",""], SPREADSHEET_ID, "QUESTIONS")

def read_sheet_tab_values(service, spreadsheet_id: str, tab_name: str, a_col: str = "A", z_col: str = "Z"):
    range_name = f"{tab_name}!{a_col}:{z_col}"
    resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
    ).execute()
    return resp.get("values", [])

def update_cell_value(service, spreadsheet_id: str, tab_name: str, row_index: int, column_letter: str, value: str):
    range_name = f"{tab_name}!{column_letter}{row_index}"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body={"values": [[value]]},
    ).execute()

# service = get_sheets_service()
# values = read_sheet_tab_values(service, SPREADSHEET_ID, "QUESTIONS")
# print(values)

# row_index = next(
#     i for i, row in enumerate(values)
#     if row and row[0].strip() == "PROCESS_STATUS_ROW"
# )
# print(row_index)
# update_cell_value(service, SPREADSHEET_ID, "CONFIG", values[row_index][1], "C", "DONE")