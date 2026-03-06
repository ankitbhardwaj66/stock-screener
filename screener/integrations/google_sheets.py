"""Google Sheets integration — reads symbols, writes screener scores."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials


_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Columns (1-indexed)
_COL_SYMBOL   = 2   # B — "Tiker"
_COL_SCORE    = 3   # C — "Score"   (numeric only, for sorting)
_COL_COMMENTS = 4   # D — "Comments" (label + delta, e.g. "BUY (+7)")
_HEADER_ROW   = 1


@dataclass
class SheetRow:
    row_num: int
    symbol: str        # raw symbol from sheet (e.g. "RELIANCE")
    ns_symbol: str     # with .NS suffix
    prev_score: Optional[int]  # parsed from Score column, None if blank


def _parse_score(cell: str) -> Optional[int]:
    """Extract numeric score from Score column (plain number like '71')."""
    if not cell or not cell.strip():
        return None
    m = re.match(r"^\s*(\d+)", cell.strip())
    return int(m.group(1)) if m else None


def make_comment(score: int, label: str, prev_score: Optional[int]) -> str:
    """Format the Comments cell: 'BUY', 'BUY (+7)', 'WATCH (-3)'."""
    if prev_score is not None and prev_score != score:
        delta = score - prev_score
        sign = "+" if delta > 0 else ""
        return f"{label} ({sign}{delta})"
    return label


class SheetSyncer:
    """Reads symbols from a Google Sheet and writes screener scores back."""

    def __init__(self, credentials_path: str, spreadsheet_id: str):
        creds = Credentials.from_service_account_file(credentials_path, scopes=_SCOPES)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(spreadsheet_id).sheet1

    def read_rows(self) -> list[SheetRow]:
        """Read all symbol rows (skips header). Score read from col C."""
        all_values = self.sheet.get_all_values()
        rows: list[SheetRow] = []
        for i, row in enumerate(all_values):
            row_num = i + 1
            if row_num == _HEADER_ROW:
                continue
            while len(row) < max(_COL_SYMBOL, _COL_SCORE):
                row.append("")
            raw_symbol = row[_COL_SYMBOL - 1].strip()
            if not raw_symbol:
                continue
            ns_symbol = raw_symbol if raw_symbol.endswith(".NS") else f"{raw_symbol}.NS"
            prev_score = _parse_score(row[_COL_SCORE - 1])
            rows.append(SheetRow(
                row_num=row_num,
                symbol=raw_symbol,
                ns_symbol=ns_symbol,
                prev_score=prev_score,
            ))
        return rows

    def write_scores(self, updates: list[tuple[int, int, str]]) -> None:
        """Batch-write scores + comments.
        `updates` is a list of (row_num, score_int, comment_str).
        Writes score (numeric) to col C and comment to col D in one API call.
        """
        if not updates:
            return
        min_row = min(r for r, _, _ in updates)
        max_row = max(r for r, _, _ in updates)

        # Fetch both columns C and D in one range call
        cells = self.sheet.range(min_row, _COL_SCORE, max_row, _COL_COMMENTS)
        update_map = {row_num: (score, comment) for row_num, score, comment in updates}
        for cell in cells:
            if cell.row not in update_map:
                continue
            score, comment = update_map[cell.row]
            if cell.col == _COL_SCORE:
                cell.value = score          # plain number → sortable
            elif cell.col == _COL_COMMENTS:
                cell.value = comment        # "BUY (+7)" etc.
        self.sheet.update_cells(cells, value_input_option="USER_ENTERED")
