from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "cn-index-fund-analysis-files" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import load_schema, read_csv_rows
from image_import import import_from_image
from portfolio_analysis import analyze as analyze_portfolio
from portfolio_analysis import inspect_nav_cache
from technical_analysis import analyze as analyze_technical
from validate_data import validate_project

SAMPLE_IMAGE = ROOT / ".agents" / "skills" / "cn-index-fund-analysis-files" / "imports" / "samples" / "交易记录样例.jpeg"


def approx(actual: float, expected: float, tolerance: float = 0.02) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"expected {expected}, got {actual}")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_recognition(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"image": SAMPLE_IMAGE.name, "transactions": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


def make_temp_project(base: Path) -> Path:
    project = base / "project"
    for rel in [
        "data", "data/nav", "reports",
        ".agents/skills/cn-index-fund-analysis-files/imports/pending",
        ".agents/skills/cn-index-fund-analysis-files/imports/archive",
    ]:
        (project / rel).mkdir(parents=True, exist_ok=True)
    for rel in ["data/schema.json", "data/funds.yaml", "data/transactions.csv", "data/nav/latest-nav.json"]:
        shutil.copy2(ROOT / rel, project / rel)
    return project


def main() -> int:
    checked = validate_project(ROOT)
    assert checked["status"] == "OK", checked
    checked_nav = validate_project(ROOT, ROOT / "data" / "nav" / "latest-nav.json", date(2026, 8, 18))
    assert checked_nav["status"] == "OK", checked_nav
    assert checked["fund_count"] == 6
    assert checked["transaction_count"] == 34
    assert checked["pending_count"] == 2

    portfolio = analyze_portfolio(ROOT, ROOT / "data" / "nav" / "latest-nav.json", date(2026, 8, 18))
    assert portfolio["transaction_count"] == 32
    assert portfolio["pending_count"] == 2
    approx(portfolio["portfolio"]["remaining_cost"], 28158.77)
    approx(portfolio["portfolio"]["market_value"], 24712.21)
    approx(portfolio["portfolio"]["unrealized_pnl"], -3446.56)
    approx(portfolio["portfolio"]["break_even_rise"], 0.139468, 0.000001)

    technical_codes = ["021934", "023652", "024663", "015877", "027521"]
    technical = analyze_technical(str(ROOT / "data" / "funds.yaml"), technical_codes, end="2026-08-14", bars_json=str(ROOT / "tests" / "fixtures" / "etf-bars.json"))
    assert len(technical["results"]) == 5
    assert not [item for item in technical["results"] if item.get("status") == "error"]
    required_metrics = [
        "kdj_k9", "kdj_d9", "kdj_j9", "macd_dif", "macd_dea", "macd_hist",
        "williams_r14", "dmi_plus_di14", "dmi_minus_di14", "dmi_adx14",
        "bias6", "bias12", "bias24", "obv", "cci20", "roc12", "cr26",
        "boll_mid20", "boll_upper20", "boll_lower20", "boll_bandwidth20", "boll_position20",
    ]
    for item in technical["results"]:
        assert all(item.get(metric) is not None for metric in required_metrics), item

    stale_status = inspect_nav_cache(ROOT / "data" / "nav" / "latest-nav.json", date(2026, 8, 19))
    assert stale_status["errors"]
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        project = make_temp_project(temp)
        ledger_path = project / "data" / "transactions.csv"
        initial_hash = file_hash(ledger_path)

        add_json = temp / "add.json"
        write_recognition(add_json, [{
            "申请日期": "2026-08-17",
            "基金代码": "020973",
            "交易类型": "买入",
            "申请成交金额": "1000",
            "确认状态": "待确认",
            "策略标签": "首次建仓",
            "confidence": 0.96,
        }])
        preview = import_from_image(project, SAMPLE_IMAGE, add_json, commit=False)
        assert preview["status"] == "OK", preview
        assert preview["committed"] is False
        assert len(preview["added"]) == 1
        assert file_hash(ledger_path) == initial_hash

        committed = import_from_image(project, SAMPLE_IMAGE, add_json, commit=True)
        assert committed["status"] == "OK", committed
        assert committed["committed"] is True
        new_id = committed["added"][0]
        assert file_hash(ledger_path) != initial_hash
        assert any((project / ".agents/skills/cn-index-fund-analysis-files/imports/archive").glob("*.csv"))

        duplicate = import_from_image(project, SAMPLE_IMAGE, add_json, commit=False)
        assert duplicate["status"] == "ERROR"
        assert any("疑似重复" in item for item in duplicate["errors"])

        update_json = temp / "update.json"
        write_recognition(update_json, [{
            "操作": "更新", "交易ID": new_id, "确认日期": "2026-08-18",
            "确认份额": "800", "确认净值": "1.25", "手续费": "0", "确认状态": "已确认",
        }])
        updated = import_from_image(project, SAMPLE_IMAGE, update_json, commit=True)
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
        assert new_row["录入来源"] == "图片识别"
        assert new_row["最近修改来源"] == "图片识别"

        before_low_confidence = file_hash(ledger_path)
        low_confidence_json = temp / "low-confidence.json"
        write_recognition(low_confidence_json, [{
            "申请日期": "2026-08-19", "基金代码": "020973", "交易类型": "买入",
            "申请成交金额": "1200", "确认状态": "待确认", "confidence": 0.50,
        }])
        blocked = import_from_image(project, SAMPLE_IMAGE, low_confidence_json, commit=True)
        assert blocked["status"] == "ERROR", blocked
        assert file_hash(ledger_path) == before_low_confidence
        assert any("置信度低于" in item for item in blocked["warnings"])

        before_invalid = file_hash(ledger_path)
        invalid_json = temp / "invalid.json"
        write_recognition(invalid_json, [{
            "申请日期": "2026-08-17", "基金代码": "999999", "交易类型": "买入",
            "申请成交金额": "500", "确认状态": "待确认",
        }])
        invalid = import_from_image(project, SAMPLE_IMAGE, invalid_json, commit=True)
        assert invalid["status"] == "ERROR"
        assert file_hash(ledger_path) == before_invalid

        void_json = temp / "void.json"
        write_recognition(void_json, [{"操作": "作废", "交易ID": new_id, "备注": "测试作废"}])
        voided = import_from_image(project, SAMPLE_IMAGE, void_json, commit=True)
        assert voided["status"] == "OK", voided
        assert voided["voided"] == [new_id]
        assert validate_project(project)["status"] == "OK"

    print("OK: validation, portfolio, complete technical indicators, image recognition preview, atomic commit, duplicate guard, update, rollback, and void")
    return 0


if __name__ == "__main__":
    sys.exit(main())