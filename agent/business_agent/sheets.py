"""Reading tables out of CSV files or Google Sheets.

Both adapters return the same thing: a list of dicts with lowercased, stripped
column names. Everything downstream is written against that shape, so you can
develop against CSVs and flip to Google Sheets by editing config.json.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path

from .config import Config, SourceConfig

Row = dict[str, str]

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y")


def parse_date(value: str) -> date:
    """Parse the date formats a human might type into a spreadsheet."""
    text = (value or "").strip()
    if not text:
        raise ValueError("empty date")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {value!r}")


def _clean_header(name: str | None) -> str:
    """Normalise a column name.

    Internal whitespace is collapsed because real sheets wrap header text, and
    a cell reading "Numbers of Completed\nSurveys in WhatsApp" must match the
    same column name as one written on a single line.
    """
    return re.sub(r"\s+", " ", (name or "")).strip().lower()


def _normalise(rows: list[dict[str, str | None]]) -> list[Row]:
    out: list[Row] = []
    for row in rows:
        clean = {
            _clean_header(k): (v or "").strip()
            for k, v in row.items()
            if k is not None
        }
        if any(clean.values()):  # skip blank spacer rows
            out.append(clean)
    return out


def _read_csv(path: Path) -> list[Row]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return _normalise(list(csv.DictReader(handle)))


def _cell_to_text(value: object) -> str:
    """One spreadsheet cell to the string the rest of the agent expects.

    Excel hands back real types where CSV hands back text: dates arrive as
    datetime, and every number as a float, so "8" comes through as "8.0".
    Normalising here keeps every parser downstream working on one shape.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _read_xlsx(source: SourceConfig, base_dir: Path) -> list[Row]:
    """Read a worksheet from an .xlsx file.

    Sheets uploaded to Drive rather than converted stay as Excel files, and
    Google's Sheets API cannot read them — so this path exists.
    """
    try:
        import openpyxl  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "Reading .xlsx needs openpyxl: pip install -r requirements.txt"
        ) from exc

    path = Path(source.path)
    if not path.is_absolute():
        path = base_dir / path
    if not path.exists():
        raise FileNotFoundError(f"no such workbook: {path}")

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        sheet = workbook[source.tab] if source.tab else workbook[workbook.sheetnames[0]]
        rows = sheet.iter_rows(values_only=True)
        try:
            header = [_cell_to_text(cell) for cell in next(rows)]
        except StopIteration:
            return []

        # Worksheets report far more columns than they use, so the header ends
        # in a run of blanks. Those all normalise to the same empty name, and
        # zipping them into a dict lets the last one overwrite the first --
        # which silently wipes the unnamed first column that holds the names.
        while header and not header[-1]:
            header.pop()

        records = []
        for row in rows:
            record: dict[str, str | None] = {}
            for name, cell in zip(header, row):
                if name not in record:  # first column with a given name wins
                    record[name] = _cell_to_text(cell)
            records.append(record)
    finally:
        workbook.close()
    return _normalise(records)


def _read_gsheet(source: SourceConfig, credentials_path: str) -> list[Row]:
    try:
        import gspread  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "Google Sheets support needs gspread: pip install -r requirements.txt"
        ) from exc

    if not credentials_path:
        raise RuntimeError("config.google_credentials_path is not set")
    client = gspread.service_account(filename=credentials_path)
    worksheet = client.open_by_key(source.path).worksheet(source.tab)
    return _normalise(worksheet.get_all_records(default_blank=""))


def load_table(source: SourceConfig, config: Config, base_dir: Path) -> list[Row]:
    """Load one configured table."""
    if source.kind == "csv":
        path = Path(source.path)
        if not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            raise FileNotFoundError(f"no such CSV: {path}")
        return _read_csv(path)
    if source.kind == "xlsx":
        return _read_xlsx(source, base_dir)
    if source.kind == "gsheet":
        return _read_gsheet(source, config.google_credentials_path)
    raise ValueError(f"unknown source kind: {source.kind!r}")
