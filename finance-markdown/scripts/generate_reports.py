from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import fund_map, write_text_atomic
from portfolio_analysis import analyze as analyze_portfolio
from portfolio_analysis import current_portfolio_markdown, transaction_check_markdown
from technical_analysis import analyze as analyze_technical, markdown as technical_markdown
from validate_data import validate_project


def generate(root: str | Path, nav_json: str | Path | None = None, technical: bool = False, end: str | None = None, bars_json: str | None = None, nav_bars_json: str | None = None) -> dict[str, Any]:
    project = Path(root)
    checked = validate_project(project)
    if checked["status"] != "OK":
        return {"status": "ERROR", "validation": checked, "outputs": {}}
    portfolio = analyze_portfolio(project, nav_json)
    generated = project / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    portfolio_path = generated / "current-portfolio.md"
    check_path = generated / "transaction-check.md"
    write_text_atomic(portfolio_path, current_portfolio_markdown(portfolio))
    write_text_atomic(check_path, transaction_check_markdown(portfolio))
    outputs: dict[str, str] = {
        "current_portfolio": str(portfolio_path.resolve()),
        "transaction_check": str(check_path.resolve()),
    }
    technical_result = None
    if technical:
        codes = sorted(fund_map(project / "data" / "funds.yaml"))
        technical_result = analyze_technical(str(project / "data" / "funds.yaml"), codes, end=end, bars_json=bars_json, nav_bars_json=nav_bars_json)
        technical_path = generated / "technical-dashboard.md"
        write_text_atomic(technical_path, technical_markdown(technical_result) + "\n")
        outputs["technical_dashboard"] = str(technical_path.resolve())
    return {
        "status": "OK",
        "validation": checked,
        "portfolio": portfolio,
        "technical": technical_result,
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验数据并生成当前持仓、流水检查和可选技术面Markdown")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--nav-json")
    parser.add_argument("--technical", action="store_true")
    parser.add_argument("--end")
    parser.add_argument("--bars-json")
    parser.add_argument("--nav-bars-json")
    args = parser.parse_args()
    result = generate(args.root, args.nav_json, args.technical, args.end, args.bars_json, args.nav_bars_json)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
