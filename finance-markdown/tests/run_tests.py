from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import load_schema, read_csv_rows
from import_transactions import import_batch
from portfolio_analysis import analyze as analyze_portfolio
from technical_analysis import analyze as analyze_technical
from validate_data import validate_project


def approx(actual: float, expected: float, tolerance: float = 0.02) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"expected {expected}, got {actual}")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_batch(path: Path, rows: list[dict[str, str]]) -> None:
    headers = load_schema(ROOT / "data" / "schema.json")["transactions"]["input_headers"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def make_temp_project(base: Path) -> Path:
    project = base / "project"
    for rel in ["data", "data/nav", "archive/imported-batches", "inbox/batches", "generated"]:
        (project / rel).mkdir(parents=True, exist_ok=True)
    for rel in ["data/schema.json", "data/funds.yaml", "data/transactions.csv", "data/nav/latest-nav.json"]:
        shutil.copy2(ROOT / rel, project / rel)
    return project


def main() -> int:
    checked = validate_project(ROOT)
    assert checked["status"] == "OK", checked
    assert checked["fund_count"] == 6
    assert checked["transaction_count"] == 34
    assert checked["pending_count"] == 2

    portfolio = analyze_portfolio(ROOT, ROOT / "data" / "nav" / "latest-nav.json")
    assert portfolio["transaction_count"] == 32
    assert portfolio["pending_count"] == 2
    approx(portfolio["portfolio"]["remaining_cost"], 28158.77)
    approx(portfolio["portfolio"]["market_value"], 23714.97)
    approx(portfolio["portfolio"]["unrealized_pnl"], -4443.80)
    approx(portfolio["portfolio"]["break_even_rise"], 0.187384, 0.000001)

    technical_codes = ["021934", "023652", "024663", "015877", "027521"]
    technical = analyze_technical(str(ROOT / "data" / "funds.yaml"), technical_codes, end="2026-08-14", bars_json=str(ROOT / "tests" / "fixtures" / "etf-bars.json"))
    assert len(technical["results"]) == 5
    assert not [item for item in technical["results"] if item.get("status") == "error"]

    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        project = make_temp_project(temp)
        ledger_path = project / "data" / "transactions.csv"
        initial_hash = file_hash(ledger_path)

        add_batch = temp / "add.csv"
        write_batch(add_batch, [{
            "操作": "新增",
            "申请日期": "2026-08-17",
            "基金代码": "020973",
            "交易类型": "买入",
            "申请成交金额": "1000",
            "确认状态": "待确认",
            "策略标签": "首次建仓",
        }])
        preview = import_batch(project, add_batch, commit=False, source="模型")
        assert preview["status"] == "OK", preview
        assert preview["committed"] is False
        assert len(preview["added"]) == 1
        assert file_hash(ledger_path) == initial_hash

        committed = import_batch(project, add_batch, commit=True, source="模型")
        assert committed["status"] == "OK", committed
        assert committed["committed"] is True
        new_id = committed["added"][0]
        assert file_hash(ledger_path) != initial_hash
        assert any((project / "archive" / "imported-batches").glob("*.csv"))

        duplicate = import_batch(project, add_batch, commit=False, source="模型")
        assert duplicate["status"] == "ERROR"
        assert any("疑似重复" in item for item in duplicate["errors"])

        update_batch = temp / "update.csv"
        write_batch(update_batch, [{
            "操作": "更新",
            "交易ID": new_id,
            "确认日期": "2026-08-18",
            "确认份额": "800",
            "确认净值": "1.25",
            "手续费": "0",
            "确认状态": "已确认",
        }])
        updated = import_batch(project, update_batch, commit=True, source="模型")
        assert updated["status"] == "OK", updated
        assert updated["updated"] == [new_id]
        project_checked = validate_project(project)
        assert project_checked["status"] == "OK", project_checked
        assert project_checked["transaction_count"] == 35
        assert project_checked["pending_count"] == 2

        _, rows = read_csv_rows(ledger_path)
        new_row = next(row for row in rows if row["交易ID"] == new_id)
        assert new_row["确认状态"] == "已确认"
        assert new_row["确认份额"] == "800"
        assert new_row["录入来源"] == "模型"
        assert new_row["最近修改来源"] == "模型"

        before_invalid = file_hash(ledger_path)
        invalid_batch = temp / "invalid.csv"
        write_batch(invalid_batch, [{
            "操作": "新增",
            "申请日期": "2026-08-17",
            "基金代码": "999999",
            "交易类型": "买入",
            "申请成交金额": "500",
            "确认状态": "待确认",
        }])
        invalid = import_batch(project, invalid_batch, commit=True, source="模型")
        assert invalid["status"] == "ERROR"
        assert file_hash(ledger_path) == before_invalid

        void_batch = temp / "void.csv"
        write_batch(void_batch, [{"操作": "作废", "交易ID": new_id, "备注": "测试作废"}])
        voided = import_batch(project, void_batch, commit=True, source="人工")
        assert voided["status"] == "OK", voided
        assert voided["voided"] == [new_id]
        after_void = validate_project(project)
        assert after_void["status"] == "OK", after_void

    print("OK: migration baseline, validation, portfolio, technical analysis, preview, atomic commit, duplicate guard, update, invalid rollback, and void")
    return 0


if __name__ == "__main__":
    sys.exit(main())
