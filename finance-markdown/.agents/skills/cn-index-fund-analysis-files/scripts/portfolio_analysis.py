from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from common import PROJECT_ROOT,  code6, decimal_or_none, dump_json, fund_map, load_json, load_schema, number, read_csv_rows



def inspect_nav_cache(path: str | Path, as_of: date | None = None) -> dict[str, Any]:
    """Validate that a NAV snapshot was checked today and is not future-dated."""
    errors: list[str] = []
    raw = load_json(path)
    if not isinstance(raw, dict):
        return {"errors": ["净值快照必须是JSON对象"], "warnings": [], "confirmed_date": "", "checked_at": ""}

    confirmed_text = str(raw.get("confirmed_date") or raw.get("as_of") or "")
    checked_text = str(raw.get("checked_at") or "")
    reference = as_of or date.today()
    try:
        confirmed = date.fromisoformat(confirmed_text)
    except ValueError:
        confirmed = None
        errors.append(f"净值快照确认日期无效：{confirmed_text!r}")
    try:
        checked = date.fromisoformat(checked_text)
    except ValueError:
        checked = None
        errors.append(f"净值快照核验日期无效：{checked_text!r}")

    if checked and checked != reference:
        errors.append(f"净值快照未在{reference.isoformat()}当天核验，实际核验日期为{checked.isoformat()}")
    if confirmed and confirmed > reference:
        errors.append(f"净值快照确认日期{confirmed.isoformat()}晚于核验日期{reference.isoformat()}")
    if confirmed and checked and confirmed > checked:
        errors.append(f"净值快照确认日期{confirmed.isoformat()}晚于核验日期{checked.isoformat()}")

    return {
        "errors": errors,
        "warnings": [],
        "confirmed_date": confirmed_text,
        "checked_at": checked_text,
        "source": str(raw.get("source") or ""),
    }

def load_navs(path: str | Path | None, as_of: date | None = None) -> tuple[dict[str, float], str, str, str]:
    if not path:
        return {}, "", "", ""
    cache_status = inspect_nav_cache(path, as_of)
    if cache_status["errors"]:
        raise ValueError("；".join(cache_status["errors"]))
    raw = load_json(path)
    nav_date = str(raw.get("confirmed_date") or raw.get("as_of") or "") if isinstance(raw, dict) else ""
    source = str(raw.get("source") or "") if isinstance(raw, dict) else ""
    checked_at = str(raw.get("checked_at") or "") if isinstance(raw, dict) else ""
    body = raw.get("funds", raw) if isinstance(raw, dict) else raw
    result: dict[str, float] = {}
    if isinstance(body, list):
        for item in body:
            if isinstance(item, dict):
                nav = item.get("latest_nav", item.get("nav"))
                if nav not in (None, ""):
                    result[code6(item.get("fund_code", item.get("code")))] = number(nav)
    elif isinstance(body, dict):
        for key, value in body.items():
            nav = value.get("latest_nav", value.get("nav")) if isinstance(value, dict) else value
            if nav not in (None, ""):
                result[code6(key)] = number(nav)
    return result, nav_date, source, checked_at


def amount(row: dict[str, str], field: str) -> float:
    return number(row.get(field), 0.0)


def analyze(root: str | Path, nav_json: str | Path | None = None, as_of: date | None = None) -> dict[str, Any]:
    project = Path(root)
    schema = load_schema(project / "data" / "schema.json")["transactions"]
    headers, ledger = read_csv_rows(project / "data" / "transactions.csv")
    if headers != schema["headers"]:
        raise ValueError("交易账本表头与Schema不一致")
    funds = fund_map(project / "data" / "funds.yaml")
    navs, nav_date, nav_source, nav_checked_at = load_navs(nav_json, as_of)
    confirmed = [r for r in ledger if r.get("确认状态") == "已确认"]
    pending = [r for r in ledger if r.get("确认状态") == "待确认"]
    voided = [r for r in ledger if r.get("确认状态") == "已作废"]
    confirmed.sort(key=lambda r: (r.get("确认日期") or r.get("申请日期") or "9999-99-99", r.get("交易ID", "")))

    warnings: list[str] = []
    label_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    buy_dates: dict[str, list[date]] = defaultdict(list)
    conversion_groups: dict[str, list[str]] = defaultdict(list)
    holdings: dict[str, dict[str, float]] = defaultdict(lambda: {"shares": 0.0, "cost": 0.0, "realized_pnl": 0.0, "dividends": 0.0, "external_cash": 0.0})

    for row in confirmed:
        code = code6(row.get("基金代码"))
        tx_type = row.get("交易类型", "")
        label = row.get("策略标签", "")
        if label:
            label_stats[label][tx_type] += 1
        if tx_type in schema["confirmed_in"] and row.get("确认日期"):
            try:
                buy_dates[code].append(date.fromisoformat(row["确认日期"]))
            except ValueError:
                pass
        if tx_type in ("转换转入", "转换转出"):
            conversion_groups[row.get("关联交易ID", "")].append(tx_type)

        trade_amount = amount(row, "申请成交金额")
        shares = amount(row, "确认份额")
        nav = amount(row, "确认净值")
        fee = amount(row, "手续费")
        received = amount(row, "实际到账分红")
        h = holdings[code]
        tx_id = row.get("交易ID", "")

        if tx_type in schema["confirmed_in"]:
            if shares <= 0:
                warnings.append(f"{tx_id}/{code}{tx_type}缺少确认份额，未计入持仓")
                continue
            h["shares"] += shares
            h["cost"] += trade_amount + fee
            if tx_type != "转换转入":
                h["external_cash"] += trade_amount + fee
        elif tx_type in schema["confirmed_out"]:
            if shares <= 0:
                warnings.append(f"{tx_id}/{code}{tx_type}缺少确认份额，未处理")
                continue
            if h["shares"] <= 0:
                warnings.append(f"{tx_id}/{code}在无持仓时发生{tx_type}")
                continue
            if shares > h["shares"] + 1e-8:
                warnings.append(f"{tx_id}/{code}{tx_type}份额{shares:.4f}超过账面份额{h['shares']:.4f}，按全部持仓处理")
                shares = h["shares"]
            average_cost = h["cost"] / h["shares"] if h["shares"] else 0.0
            removed_cost = average_cost * shares
            proceeds = received if received > 0 else trade_amount if trade_amount > 0 else shares * nav - fee
            if received <= 0 and trade_amount <= 0:
                warnings.append(f"{tx_id}/{code}{tx_type}缺少实际到账和成交金额，使用份额×净值−手续费估算")
            h["shares"] -= shares
            h["cost"] -= removed_cost
            h["realized_pnl"] += proceeds - removed_cost
            if "止盈" in label and proceeds < removed_cost:
                warnings.append(f"{tx_id}/{code}标记为止盈，但本次到账低于转出成本")
            if tx_type != "转换转出":
                h["external_cash"] -= proceeds
        elif tx_type in schema["dividend"]:
            h["dividends"] += received
            h["realized_pnl"] += received
            h["external_cash"] -= received

    for code, dates in buy_dates.items():
        dates.sort()
        if any((dates[i] - dates[i - 2]).days <= 7 for i in range(2, len(dates))):
            warnings.append(f"{code}存在7日内至少3笔确认买入，需核对是否短期快速建仓或越跌越密集")
    for link, types in conversion_groups.items():
        if not link:
            continue
        if types.count("转换转入") != types.count("转换转出"):
            warnings.append(f"转换关联组{link}转入/转出不成对：{types}")
    if "再平衡" in label_stats and sum(label_stats["再平衡"].get(t, 0) for t in schema["confirmed_out"]) == 0:
        warnings.append("标记为‘再平衡’的记录没有减仓交易，本质可能只是继续加仓")
    if "回撤加仓" in label_stats:
        warnings.append("存在‘回撤加仓’记录；需核对触发阈值、最大仓位和停止条件")

    rows: list[dict[str, Any]] = []
    for code, h in sorted(holdings.items()):
        if abs(h["shares"]) < 1e-8:
            h["shares"] = 0.0
            h["cost"] = max(h["cost"], 0.0)
        latest_nav = navs.get(code)
        market_value = h["shares"] * latest_nav if latest_nav is not None else None
        unrealized = market_value - h["cost"] if market_value is not None else None
        break_even = max(h["cost"] - market_value, 0.0) / market_value if market_value and market_value > 0 else None
        rows.append({
            "fund_code": code,
            "fund_name": funds.get(code, {}).get("name", ""),
            "shares": round(h["shares"], 4),
            "remaining_cost": round(h["cost"], 2),
            "average_cost": round(h["cost"] / h["shares"], 6) if h["shares"] else None,
            "latest_nav": latest_nav,
            "market_value": round(market_value, 2) if market_value is not None else None,
            "unrealized_pnl": round(unrealized, 2) if unrealized is not None else None,
            "break_even_rise": round(break_even, 6) if break_even is not None else None,
            "realized_pnl": round(h["realized_pnl"], 2),
            "external_net_cash": round(h["external_cash"], 2),
        })

    active = [r for r in rows if r["shares"] > 0]
    total_cost = sum(r["remaining_cost"] for r in active)
    values_known = bool(active) and all(r["market_value"] is not None for r in active)
    total_market = sum(r["market_value"] for r in active) if values_known else None
    total_unrealized = total_market - total_cost if total_market is not None else None
    total_break_even = max(total_cost - total_market, 0.0) / total_market if total_market and total_market > 0 else None
    return {
        "generated_at": date.today().isoformat(),
        "analysis_mode": "portfolio_plus_technical" if active else "technical_only",
        "transaction_count": len(confirmed),
        "pending_count": len(pending),
        "voided_count": len(voided),
        "pending_trades": pending,
        "holdings": rows,
        "portfolio": {
            "remaining_cost": round(total_cost, 2),
            "market_value": round(total_market, 2) if total_market is not None else None,
            "unrealized_pnl": round(total_unrealized, 2) if total_unrealized is not None else None,
            "break_even_rise": round(total_break_even, 6) if total_break_even is not None else None,
        },
        "nav_confirmed_date": nav_date,
        "nav_source": nav_source,
        "nav_checked_at": nav_checked_at,
        "warnings": warnings,
    }


def fmt_money(value: Any) -> str:
    return "—" if value is None else f"¥{value:,.2f}"


def fmt_number(value: Any, digits: int = 4) -> str:
    return "—" if value is None else f"{value:,.{digits}f}"


def current_portfolio_markdown(result: dict[str, Any]) -> str:
    branch = "持仓 + 技术面" if result["analysis_mode"] == "portfolio_plus_technical" else "仅技术面"
    lines = [
        "# 当前基金持仓",
        "",
        f"> 报告生成日期：{result['generated_at']}",
        f"> 最近确认净值日期：{result['nav_confirmed_date'] or '未提供'}",
        f"> 净值来源：{result['nav_source'] or '未提供'}",
        f"> 净值快照核验日期：{result['nav_checked_at'] or '未提供'}",
        "",
        f"- 分析分支：{branch}",
        f"- 已确认交易：{result['transaction_count']}笔",
        f"- 待确认交易：{result['pending_count']}笔",
        f"- 已作废交易：{result['voided_count']}笔",
        f"- 当前剩余成本：{fmt_money(result['portfolio']['remaining_cost'])}",
        f"- 当前市值：{fmt_money(result['portfolio']['market_value'])}",
        f"- 浮动盈亏：{fmt_money(result['portfolio']['unrealized_pnl'])}",
        f"- 组合回本所需涨幅：{'—' if result['portfolio']['break_even_rise'] is None else f"{result['portfolio']['break_even_rise']:.2%}"}",
        "",
        "|基金代码|基金名称|确认份额|剩余成本|平均成本|最新净值|当前市值|浮动盈亏|回本所需涨幅|",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["holdings"]:
        pct = "—" if row["break_even_rise"] is None else f"{row['break_even_rise']:.2%}"
        lines.append(f"|{row['fund_code']}|{row['fund_name']}|{fmt_number(row['shares'])}|{fmt_money(row['remaining_cost'])}|{fmt_number(row['average_cost'], 6)}|{fmt_number(row['latest_nav'], 4)}|{fmt_money(row['market_value'])}|{fmt_money(row['unrealized_pnl'])}|{pct}|")
    lines += ["", "## 口径", "", "- 待确认交易不改变已确认份额和成本。", "- 买入成本为成交金额加手续费。", "- 卖出按移动加权平均成本减少。", "- 回本所需涨幅为未弥补亏损除以当前市值。"]
    return "\n".join(lines) + "\n"


def transaction_check_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 交易账本检查",
        "",
        f"> 检查日期：{result['generated_at']}",
        "",
        "## 待确认交易",
        "",
    ]
    if result["pending_trades"]:
        lines += ["|交易ID|申请日期|基金代码|交易类型|申请金额|确认份额|策略标签|备注|", "|---|---|---|---|---:|---:|---|---|"]
        for row in result["pending_trades"]:
            lines.append(f"|{row.get('交易ID','')}|{row.get('申请日期','')}|{row.get('基金代码','')}|{row.get('交易类型','')}|{row.get('申请成交金额','')}|{row.get('确认份额','')}|{row.get('策略标签','')}|{str(row.get('备注','')).replace('|','\\|')}|")
    else:
        lines.append("当前没有待确认交易。")
    lines += ["", "## 风险与一致性提醒", ""]
    if result["warnings"]:
        lines += [f"- {item}" for item in result["warnings"]]
    else:
        lines.append("未发现固定规则范围内的异常。")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="从CSV交易账本计算持仓、成本、盈亏和待确认交易")
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--nav-json")
    parser.add_argument("--format", choices=["json", "portfolio-md", "check-md"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze(args.root, args.nav_json)
    if args.format == "portfolio-md":
        text = current_portfolio_markdown(result)
    elif args.format == "check-md":
        text = transaction_check_markdown(result)
    else:
        text = dump_json(result) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
