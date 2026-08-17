from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from portfolio_analysis import analyze as analyze_portfolio
from technical_analysis import analyze as analyze_technical
from validate_workbook import validate


def approx(actual: float, expected: float, tolerance: float = 0.02) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"expected {expected}, got {actual}")


def main() -> int:
    parser = argparse.ArgumentParser(description="技能端到端冒烟测试")
    parser.add_argument("--workbook", required=True)
    args = parser.parse_args()

    fixtures = ROOT / "tests" / "fixtures"
    mapping = ROOT / "references" / "fund-map.json"

    checked = validate(args.workbook)
    assert checked["status"] == "OK", checked

    portfolio = analyze_portfolio(args.workbook, str(fixtures / "latest-nav.json"))
    assert portfolio["analysis_mode"] == "portfolio_plus_technical"
    assert portfolio["transaction_count"] == 32
    assert portfolio["pending_count"] == 2
    approx(portfolio["portfolio"]["remaining_cost"], 28158.77)
    approx(portfolio["portfolio"]["market_value"], 23714.97)
    approx(portfolio["portfolio"]["unrealized_pnl"], -4443.80)
    approx(portfolio["portfolio"]["break_even_rise"], 0.187384, 0.000001)

    empty = analyze_portfolio(str(fixtures / "no-position.xlsx"))
    assert empty["analysis_mode"] == "technical_only"
    assert empty["transaction_count"] == 0

    technical = analyze_technical(str(mapping), end="2026-08-14", bars_json=str(fixtures / "etf-bars.json"))
    assert len(technical["results"]) == 5
    assert not [x for x in technical["results"] if x.get("status") == "error"]

    nav_only = analyze_technical(str(fixtures / "nav-only-map.json"), ["000001"], end="2026-08-14", nav_bars_json=str(fixtures / "nav-bars.json"))
    assert nav_only["results"][0]["status"] == "ok_nav_only"
    assert nav_only["results"][0]["volume_state"] == "不适用（场外净值）"

    print("OK: template, portfolio, technical-only, portfolio+technical, and NAV-only branches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
