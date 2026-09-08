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
    if source.kind == "gsheet":
        return _read_gsheet(source, config.google_credentials_path)
    raise ValueError(f"unknown source kind: {source.kind!r}")
