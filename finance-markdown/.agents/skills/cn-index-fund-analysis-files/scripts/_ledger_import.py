from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from common import PROJECT_ROOT, code6, load_schema, read_csv_rows, write_csv_atomic
from validate_data import possible_duplicate_key, validate_transactions

BUSINESS_FIELDS = ["申请日期", "确认日期", "基金代码", "交易类型", "申请成交金额", "确认份额", "确认净值", "手续费", "实际到账分红", "确认状态", "策略标签", "备注", "关联交易ID"]


def batch_id_for(path: Path, now: datetime) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8].upper()
    return f"BATCH-{now:%Y%m%d-%H%M%S}-{digest}"


def next_transaction_id(request_date: str, code: str, rows: list[dict[str, str]], reserved: set[str]) -> str:
    prefix = f"TX-{request_date.replace('-', '')}-{code6(code)}-"
    numbers: list[int] = []
    for tx_id in [r.get("交易ID", "") for r in rows] + list(reserved):
        if tx_id.startswith(prefix):
            try:
                numbers.append(int(tx_id.rsplit("-", 1)[1]))
            except ValueError:
                pass
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def normalize_new(raw: dict[str, str], headers: list[str], ledger: list[dict[str, str]], reserved: set[str], source: str, batch_id: str, now_text: str) -> dict[str, str]:
    row = {h: "" for h in headers}
    for field in BUSINESS_FIELDS:
        row[field] = (raw.get(field) or "").strip()
    row["基金代码"] = code6(row["基金代码"])
    if not row["确认状态"]:
        row["确认状态"] = "已确认" if row["确认日期"] else "待确认"
    tx_id = (raw.get("交易ID") or "").strip()
    if not tx_id:
        tx_id = next_transaction_id(row["申请日期"], row["基金代码"], ledger, reserved)
    row["交易ID"] = tx_id
    row["录入来源"] = source
    row["录入批次"] = batch_id
    row["录入时间"] = now_text
    reserved.add(tx_id)
    return row


def apply_update(existing: dict[str, str], raw: dict[str, str], clear_markers: set[str], source: str, batch_id: str, now_text: str, void: bool = False) -> dict[str, str]:
    updated = dict(existing)
    if void:
        updated["确认状态"] = "已作废"
        note = (raw.get("备注") or "").strip()
        if note:
            updated["备注"] = note
    else:
        for field in BUSINESS_FIELDS:
            value = (raw.get(field) or "").strip()
            if value in clear_markers:
                updated[field] = ""
            elif value != "":
                updated[field] = code6(value) if field == "基金代码" else value
    updated["最近修改来源"] = source
    updated["最近修改批次"] = batch_id
    updated["最近修改时间"] = now_text
    return updated


def import_batch(root: str | Path, batch_path: str | Path, commit: bool = False, source: str = "模型", allow_possible_duplicate: bool = False) -> dict[str, Any]:
    project = Path(root)
    batch = Path(batch_path)
    schema = load_schema(project / "data" / "schema.json")["transactions"]
    canonical_headers = schema["headers"]
    input_headers = schema["input_headers"]
    batch_headers, batch_rows = read_csv_rows(batch)
    if batch_headers != input_headers:
        return {"status": "ERROR", "committed": False, "errors": [f"批次表头不匹配。预期：{input_headers}；实际：{batch_headers}"], "warnings": []}
    ledger_path = project / "data" / "transactions.csv"
    ledger_headers, ledger = read_csv_rows(ledger_path)
    if ledger_headers != canonical_headers:
        return {"status": "ERROR", "committed": False, "errors": ["正式账本表头与Schema不一致"], "warnings": []}
    now = datetime.now().astimezone()
    now_text = now.isoformat(timespec="seconds")
    batch_id = batch_id_for(batch, now)
    clear_markers = set(schema.get("clear_markers", []))
    by_id = {row["交易ID"]: index for index, row in enumerate(ledger)}
    reserved: set[str] = set()
    candidate = [dict(row) for row in ledger]
    added: list[str] = []
    updated: list[str] = []
    voided: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    possible_existing: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for row in ledger:
        if row.get("确认状态") != "已作废":
            possible_existing[possible_duplicate_key(row)].append(row.get("交易ID", ""))

    for line_no, raw in enumerate(batch_rows, 2):
        operation = (raw.get("操作") or "新增").strip()
        if operation not in schema["operations"]:
            errors.append(f"批次第{line_no}行操作无效：{operation!r}")
            continue
        if operation == "新增":
            new_row = normalize_new(raw, canonical_headers, candidate, reserved, source, batch_id, now_text)
            if new_row["交易ID"] in by_id or new_row["交易ID"] in added:
                errors.append(f"批次第{line_no}行交易ID已存在：{new_row['交易ID']}")
                continue
            key = possible_duplicate_key(new_row)
            duplicates = possible_existing.get(key, [])
            if duplicates and any(key):
                message = f"批次第{line_no}行疑似重复，账本已有：{duplicates}"
                if allow_possible_duplicate:
                    warnings.append(message + "；已按显式参数允许")
                else:
                    errors.append(message)
                    continue
            candidate.append(new_row)
            by_id[new_row["交易ID"]] = len(candidate) - 1
            possible_existing[key].append(new_row["交易ID"])
            added.append(new_row["交易ID"])
        else:
            tx_id = (raw.get("交易ID") or "").strip()
            if not tx_id:
                errors.append(f"批次第{line_no}行{operation}操作缺少交易ID")
                continue
            if tx_id not in by_id:
                errors.append(f"批次第{line_no}行找不到交易ID：{tx_id}")
                continue
            index = by_id[tx_id]
            candidate[index] = apply_update(candidate[index], raw, clear_markers, source, batch_id, now_text, void=operation == "作废")
            (voided if operation == "作废" else updated).append(tx_id)

    if errors:
        return {"status": "ERROR", "committed": False, "batch_id": batch_id, "added": added, "updated": updated, "voided": voided, "errors": errors, "warnings": warnings}

    temp_candidate = project / "data" / f".transactions-candidate-{batch_id}.csv"
    try:
        write_csv_atomic(temp_candidate, canonical_headers, candidate)
        checked = validate_transactions(temp_candidate, project / "data" / "funds.yaml", project / "data" / "schema.json")
    finally:
        if temp_candidate.exists():
            temp_candidate.unlink()
    if checked["errors"]:
        return {"status": "ERROR", "committed": False, "batch_id": batch_id, "added": added, "updated": updated, "voided": voided, "errors": checked["errors"], "warnings": warnings + checked["warnings"]}
    warnings.extend(checked["warnings"])

    if commit:
        write_csv_atomic(ledger_path, canonical_headers, candidate)
        archive_dir = project / ".agents" / "skills" / "cn-index-fund-analysis-files" / "imports" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{batch_id}-{batch.name}"
        shutil.copy2(batch, archive_path)
    else:
        archive_path = None
    return {
        "status": "OK",
        "committed": commit,
        "batch_id": batch_id,
        "input_rows": len(batch_rows),
        "added": added,
        "updated": updated,
        "voided": voided,
        "ledger_rows_after": len(candidate),
        "archive_path": str(archive_path) if archive_path else None,
        "errors": [],
        "warnings": warnings,
    }

