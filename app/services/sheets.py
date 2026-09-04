import asyncio
from typing import Any, cast
import gspread
from app.config import settings

HEADERS = ["Job Title", "Company", "Location", "Posted Date", "AmbitionBox Rating",
           "Status", "Date Applied", "Notes", "Link", "Match Score"]

_COL_WIDTHS = [220, 150, 150, 100, 130, 100, 110, 180, 300, 90]

_STATUS_COLORS = {
    "New":       {"red": 0.93, "green": 0.93, "blue": 0.93},
    "Prepared":  {"red": 1.0,  "green": 0.93, "blue": 0.80},
    "Applied":   {"red": 0.80, "green": 0.90, "blue": 1.0},
    "Interview": {"red": 0.80, "green": 0.96, "blue": 0.80},
    "Offer":     {"red": 0.71, "green": 0.96, "blue": 0.71},
    "Rejected":  {"red": 1.0,  "green": 0.85, "blue": 0.85},
}


def _get_sheet():
    gc = gspread.service_account(filename=settings.google_credentials_path)
    return gc.open_by_key(settings.google_sheet_id).sheet1


def _format_sheet(sheet):
    spreadsheet = sheet.spreadsheet
    sheet_id = sheet._properties["sheetId"]
    n_cols = len(HEADERS)

    requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": n_cols},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.10, "green": 0.45, "blue": 0.91},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}, "fontSize": 10},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        *[
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}},
                    "fields": "userEnteredFormat.horizontalAlignment",
                }
            }
            for col in [3, 4, 5, 6, 9]
        ],
    ]

    for i, width in enumerate(_COL_WIDTHS):
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    spreadsheet.batch_update({"requests": requests})


def _ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if not first_row:
        sheet.append_row(HEADERS, value_input_option="RAW")
        _format_sheet(sheet)
    elif len(first_row) < len(HEADERS):
        for i, h in enumerate(HEADERS[len(first_row):], start=len(first_row) + 1):
            sheet.update_cell(1, i, h)
        _format_sheet(sheet)


def _color_status_cell(sheet, row: int, status: str):
    color = _STATUS_COLORS.get(status)
    if not color:
        return
    sheet_id = sheet._properties["sheetId"]
    sheet.spreadsheet.batch_update({"requests": [{
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": row - 1, "endRowIndex": row,
                      "startColumnIndex": 5, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"backgroundColor": color}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    }]})


def _append_jobs_sync(jobs: list[dict]):
    sheet = _get_sheet()
    _ensure_headers(sheet)
    existing_links = sheet.col_values(9)
    rows = []
    for job in jobs:
        if job["job_url"] in existing_links:
            continue
        rows.append([
            job["job_title"],
            job["company"],
            job.get("location", ""),
            job.get("posted_at") or "",
            job.get("company_rating") or "N/A",
            "New",
            "",
            "",
            job["job_url"],
            job.get("match_score", ""),
        ])
    if rows:
        first_new_row = len(sheet.col_values(1)) + 1
        sheet.append_rows(rows, value_input_option=cast(Any, "RAW"))
        for i in range(len(rows)):
            _color_status_cell(sheet, first_new_row + i, "New")
    return len(rows)


def _read_sheet_sync() -> list[dict]:
    sheet = _get_sheet()
    return sheet.get_all_records()


def _update_job_status_sync(job_url: str, status: str, date_applied: str = "", notes: str = "") -> bool:
    sheet = _get_sheet()
    links = sheet.col_values(9)
    for i, link in enumerate(links):
        if link == job_url:
            row = i + 1
            sheet.update_cell(row, 6, status)
            if date_applied:
                sheet.update_cell(row, 7, date_applied)
            if notes:
                sheet.update_cell(row, 8, notes)
            _color_status_cell(sheet, row, status)
            return True
    return False


async def append_jobs_to_sheet(jobs: list[dict]) -> int:
    return await asyncio.to_thread(_append_jobs_sync, jobs)


async def read_sheet() -> list[dict]:
    return await asyncio.to_thread(_read_sheet_sync)


async def update_job_status(job_url: str, status: str, date_applied: str = "", notes: str = "") -> bool:
    return await asyncio.to_thread(_update_job_status_sync, job_url, status, date_applied, notes)
