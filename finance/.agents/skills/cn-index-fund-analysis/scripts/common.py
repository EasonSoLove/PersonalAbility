from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = SKILL_ROOT / "references" / "workbook-schema.json"


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    return load_json(path or DEFAULT_SCHEMA)


def code6(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else text


def number(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def iso_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip() or None


def header_map(ws: Any, header_row: int) -> dict[str, int]:
    result: dict[str, int] = {}
    for cell in ws[header_row]:
        if cell.value not in (None, ""):
            result[str(cell.value).strip()] = cell.column
    return result


def row_dict(ws: Any, row: int, headers: dict[str, int]) -> dict[str, Any]:
    return {name: ws.cell(row=row, column=col).value for name, col in headers.items()}


def contains_any(values: Iterable[Any], markers: Iterable[str]) -> bool:
    text = " | ".join("" if v is None else str(v) for v in values)
    return any(marker in text for marker in markers)


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)