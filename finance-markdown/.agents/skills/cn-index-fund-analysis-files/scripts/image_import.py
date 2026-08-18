from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from common import PROJECT_ROOT, load_schema
from _ledger_import import import_batch

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FIELD_ALIASES = {
    "申请日期": "申请日期", "日期": "申请日期", "交易日期": "申请日期",
    "交易ID": "交易ID", "确认日期": "确认日期", "基金代码": "基金代码", "代码": "基金代码",
    "交易类型": "交易类型", "类型": "交易类型", "申请成交金额": "申请成交金额",
    "金额": "申请成交金额", "确认份额": "确认份额", "份额": "确认份额",
    "确认净值": "确认净值", "净值": "确认净值", "手续费": "手续费",
    "实际到账分红": "实际到账分红", "确认状态": "确认状态", "策略标签": "策略标签",
    "备注": "备注", "关联交易ID": "关联交易ID",
}


def validate_image(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"交易图片不存在：{path}")
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"不支持的交易图片格式：{path.suffix}")
    signature = path.read_bytes()[:12]
    valid = signature.startswith(b"\xff\xd8\xff") or signature.startswith(b"\x89PNG") or signature.startswith(b"RIFF")
    if not valid:
        raise ValueError("交易图片文件头不是受支持的 JPEG、PNG 或 WebP")


def load_recognition(path: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("transactions", raw.get("records", []))
    else:
        raise ValueError("识别结果必须是对象或数组")
    if not isinstance(items, list) or not items:
        raise ValueError("识别结果没有 transactions/records")
    warnings: list[str] = []
    blocking_warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            warnings.append(f"第{index}条识别结果不是对象，已跳过")
            continue
        source = item.get("fields") if isinstance(item.get("fields"), dict) else item
        row: dict[str, Any] = {"操作": source.get("操作", "新增")}
        for key, value in source.items():
            canonical = FIELD_ALIASES.get(str(key))
            if canonical:
                row[canonical] = "" if value is None else str(value).strip()
        confidence = item.get("confidence")
        if confidence is not None:
            try:
                if float(confidence) < 0.85:
                    message = f"第{index}条识别置信度低于0.85：{confidence}"
                    warnings.append(message)
                    blocking_warnings.append(message)
            except (TypeError, ValueError):
                message = f"第{index}条置信度无法解析：{confidence}"
                warnings.append(message)
                blocking_warnings.append(message)
        if item.get("uncertain_fields"):
            message = f"第{index}条存在待确认字段：{item['uncertain_fields']}"
            warnings.append(message)
            blocking_warnings.append(message)
        rows.append(row)
    if not rows:
        raise ValueError("没有可导入的识别记录")
    return rows, warnings, blocking_warnings


def write_recognized_batch(project: Path, image: Path, rows: list[dict[str, Any]]) -> Path:
    schema = load_schema(project / "data" / "schema.json")["transactions"]
    pending = project / ".agents" / "skills" / "cn-index-fund-analysis-files" / "imports" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()[:10].upper()
    batch_id = f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-{digest}"
    path = pending / f"image-{batch_id}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=schema["input_headers"], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in schema["input_headers"]})
    return path


def import_from_image(project: str | Path, image_path: str | Path, recognition_path: str | Path, commit: bool = False, allow_possible_duplicate: bool = False) -> dict[str, Any]:
    root = Path(project)
    image = Path(image_path)
    recognition = Path(recognition_path)
    validate_image(image)
    if not recognition.is_file():
        raise ValueError(f"图片识别结果不存在：{recognition}")
    rows, warnings, blocking_warnings = load_recognition(recognition)
    batch = write_recognized_batch(root, image, rows)
    if commit and blocking_warnings:
        result = {
            "status": "ERROR",
            "committed": False,
            "errors": ["识别结果存在低置信度或待确认字段，不能直接提交；请先人工确认后重新预检。"],
            "warnings": [],
            "batch_path": str(batch.resolve()),
        }
    else:
        result = import_batch(root, batch, commit=commit, source="图片识别", allow_possible_duplicate=allow_possible_duplicate)
    result["image"] = str(image.resolve())
    result["recognition_json"] = str(recognition.resolve())
    result["batch_path"] = str(batch.resolve())
    result["warnings"] = warnings + result.get("warnings", [])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="从交易图片的视觉识别结果预检或原子导入交易")
    parser.add_argument("image", help="交易图片路径；支持 JPEG/PNG/WebP")
    parser.add_argument("--recognition-json", required=True, help="视觉识别结果JSON；由模型根据图片生成")
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--commit", action="store_true", help="预检通过后写入正式账本")
    parser.add_argument("--allow-possible-duplicate", action="store_true")
    args = parser.parse_args()
    try:
        result = import_from_image(args.root, args.image, args.recognition_json, args.commit, args.allow_possible_duplicate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "committed": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())