from __future__ import annotations

import csv
import json
import math
import os
import re
import tempfile
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "data" / "schema.json").is_file() and (candidate / "data" / "funds.yaml").is_file():
            return candidate
    raise RuntimeError("无法定位 finance-markdown 项目根目录")


PROJECT_ROOT = find_project_root()
DEFAULT_SCHEMA = PROJECT_ROOT / "data" / "schema.json"
DEFAULT_FUNDS = PROJECT_ROOT / "data" / "funds.yaml"
DEFAULT_TRANSACTIONS = PROJECT_ROOT / "data" / "transactions.csv"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


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


def decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def decimal_text(value: Any) -> str:
    dec = decimal_or_none(value)
    if dec is None:
        return ""
    text = format(dec, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def iso_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    return text.replace("/", "-")


def valid_iso_date(value: str) -> bool:
    if not value:
        return True
    try:
        date.fromisoformat(value)
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    except ValueError:
        return False


def read_csv_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = []
        for raw in reader:
            row = {str(k): "" if v is None else str(v).strip() for k, v in raw.items() if k is not None}
            if any(row.values()):
                rows.append(row)
    return headers, rows


def write_csv_atomic(path: str | Path, headers: list[str], rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({h: "" if row.get(h) is None else row.get(h, "") for h in headers})
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _parse_yaml_scalar(text: str) -> Any:
    text = text.strip()
    if text == "":
        return ""
    if text in ("null", "~"):
        return None
    if text in ("true", "false"):
        return text == "true"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _split_yaml_pair(text: str, line_no: int) -> tuple[str, Any]:
    if ":" not in text:
        raise ValueError(f"funds.yaml第{line_no}行缺少冒号")
    key, raw = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ValueError(f"funds.yaml第{line_no}行字段名为空")
    return key, _parse_yaml_scalar(raw)


def load_funds_yaml(path: str | Path = DEFAULT_FUNDS) -> dict[str, Any]:
    source = Path(path)
    result: dict[str, Any] = {}
    funds: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section = ""
    for line_no, raw in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        if indent == 0:
            key, value = _split_yaml_pair(text, line_no)
            if key == "funds":
                if value not in ("", None):
                    raise ValueError(f"funds.yaml第{line_no}行funds后不应有值")
                result["funds"] = funds
                section = "funds"
            else:
                result[key] = value
                section = ""
            continue
        if section not in ("funds", "fund_item", "linked_etf"):
            raise ValueError(f"funds.yaml第{line_no}行缩进位置无效")
        if indent == 2 and text.startswith("- "):
            current = {}
            funds.append(current)
            section = "fund_item"
            remainder = text[2:].strip()
            if remainder:
                key, value = _split_yaml_pair(remainder, line_no)
                current[key] = value
            continue
        if current is None:
            raise ValueError(f"funds.yaml第{line_no}行没有基金列表项")
        if indent == 4:
            key, value = _split_yaml_pair(text, line_no)
            if key == "linked_etf" and value in ("", None):
                current[key] = {}
                section = "linked_etf"
            else:
                current[key] = value
                section = "fund_item"
            continue
        if indent == 6 and section == "linked_etf":
            key, value = _split_yaml_pair(text, line_no)
            current.setdefault("linked_etf", {})[key] = value
            continue
        raise ValueError(f"funds.yaml第{line_no}行存在不支持的缩进或结构")
    result.setdefault("funds", funds)
    return result


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def dump_funds_yaml(document: dict[str, Any]) -> str:
    lines = [
        f"schema_version: {_yaml_scalar(document.get('schema_version', '1.0.0'))}",
        f"updated_at: {_yaml_scalar(document.get('updated_at', ''))}",
        f"source: {_yaml_scalar(document.get('source', '天天基金'))}",
        "funds:",
    ]
    order = ["code", "name", "theme", "tracked_index", "inception_date", "sales_service_fee", "redemption_note", "source_url", "synced_at"]
    etf_order = ["code", "name", "exchange", "secid"]
    for fund in document.get("funds", []):
        lines.append(f"  - code: {_yaml_scalar(code6(fund.get('code')))}")
        for key in order[1:4]:
            lines.append(f"    {key}: {_yaml_scalar(fund.get(key, ''))}")
        lines.append("    linked_etf:")
        etf = fund.get("linked_etf") or {}
        for key in etf_order:
            value = code6(etf.get(key)) if key == "code" and etf.get(key) else etf.get(key, "")
            lines.append(f"      {key}: {_yaml_scalar(value)}")
        for key in order[4:]:
            lines.append(f"    {key}: {_yaml_scalar(fund.get(key, ''))}")
    return "\n".join(lines) + "\n"


def write_text_atomic(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def fund_map(path: str | Path = DEFAULT_FUNDS) -> dict[str, dict[str, Any]]:
    document = load_funds_yaml(path)
    result: dict[str, dict[str, Any]] = {}
    for fund in document.get("funds", []):
        item = dict(fund)
        item["code"] = code6(item.get("code"))
        if item["code"]:
            result[item["code"]] = item
    return result


def contains_any(values: Iterable[Any], markers: Iterable[str]) -> bool:
    text = " | ".join("" if v is None else str(v) for v in values)
    return any(marker in text for marker in markers)
