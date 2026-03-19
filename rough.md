read sheet from a source unknow
 read and setup read on update hook on excel file
 or read with chrone job

fetch list of rows needed to convert
and language in which needed

mark row processed


Step 1: Prepare Google Sheet
Open your Sheet > File > Share > Change to "Anyone with the link" > Viewer.

Copy Sheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0

Extract {SHEET_ID} (e.g., 1rWG6LNi5kPpbogrdnRBhNUwxWNM9zvN58pRgLSFGzBM).

Export URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx—downloads full workbook as XLSX (multi-tab support).

Step 2: Fetch & Save XLSX (NestJS)