from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from common import code6, dump_json, load_json, number

EASTMONEY_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def load_mapping(path: str) -> dict[str, dict[str, Any]]:
    raw = load_json(path)
    funds = raw.get("funds", raw) if isinstance(raw, dict) else raw
    result: dict[str, dict[str, Any]] = {}
    for item in funds or []:
        if not isinstance(item, dict):
            continue
        fund_code = code6(item.get("fund_code", item.get("code")))
        if fund_code:
            normalized = dict(item)
            normalized["fund_code"] = fund_code
            normalized["target_etf_code"] = code6(item.get("target_etf_code")) if item.get("target_etf_code") else ""
            result[fund_code] = normalized
    return result


def parse_kline_rows(raw: Any, etf_code: str = "") -> list[dict[str, Any]]:
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        raw = raw["data"].get("klines", [])
    elif isinstance(raw, dict) and "klines" in raw:
        raw = raw["klines"]
    elif isinstance(raw, dict) and etf_code in raw:
        raw = raw[etf_code]
    elif isinstance(raw, dict) and "bars" in raw:
        bars = raw["bars"]
        raw = bars.get(etf_code, bars) if isinstance(bars, dict) else bars

    rows: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, str):
            p = item.split(",")
            if len(p) < 7:
                continue
            row = {
                "date": p[0], "open": number(p[1]), "close": number(p[2]),
                "high": number(p[3]), "low": number(p[4]), "volume": number(p[5]),
                "amount": number(p[6]),
            }
        elif isinstance(item, dict):
            row = {
                "date": str(item.get("date", item.get("day", ""))),
                "open": number(item.get("open")), "close": number(item.get("close")),
                "high": number(item.get("high")), "low": number(item.get("low")),
                "volume": number(item.get("volume", item.get("vol"))),
                "amount": number(item.get("amount", item.get("turnover_amount"))),
            }
        else:
            continue
        if row["date"] and row["close"] > 0:
            rows.append(row)
    rows.sort(key=lambda x: x["date"])
    return rows


def load_offline_bars(path: str, etf_code: str) -> list[dict[str, Any]]:
    raw = load_json(path)
    return parse_kline_rows(raw, etf_code)


def fetch_bars(secid: str, end: str | None = None, limit: int = 260, timeout: int = 15) -> list[dict[str, Any]]:
    params = {
        "secid": secid,
        "klt": "101",
        "fqt": "1",
        "lmt": str(limit),
        "end": (end or "20500101").replace("-", ""),
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    request = urllib.request.Request(
        EASTMONEY_KLINE + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return parse_kline_rows(raw)


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def ma(closes: list[float], window: int) -> float | None:
    return average(closes[-window:]) if len(closes) >= window else None


def rsi14(closes: list[float]) -> float | None:
    if len(closes) < 15:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
    gains = sum(max(x, 0.0) for x in changes) / 14
    losses = sum(max(-x, 0.0) for x in changes) / 14
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = gains / losses
    return 100 - 100 / (1 + rs)


def pct_change(current: float, previous: float | None) -> float | None:
    return current / previous - 1 if previous and previous != 0 else None


def volume_label(ratio: float | None) -> str:
    if ratio is None:
        return "数据不足"
    if ratio < 1.0:
        return "缩量"
    if ratio < 1.2:
        return "轻微放量"
    if ratio < 1.5:
        return "中等放量"
    return "明显放量"


def technical_state(close: float, ma20: float | None, ma60: float | None, ma20_slope: float | None) -> str:
    if ma20 is None:
        return "样本不足"
    if close >= ma20 and (ma20_slope or 0) > 0 and (ma60 is None or close >= ma60):
        return "偏强趋势"
    if close >= ma20 and (ma20_slope or 0) <= 0:
        return "反弹/反转尝试"
    if close < ma20 and (ma20_slope or 0) < 0:
        return "弱势下行"
    return "震荡整理"


def analyze_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 20:
        raise ValueError(f"日K样本不足：至少20条，实际{len(rows)}条")
    closes = [number(x["close"]) for x in rows]
    amounts = [number(x.get("amount")) for x in rows]
    current = rows[-1]
    current_close = closes[-1]
    ma_values = {f"ma{w}": ma(closes, w) for w in (5, 10, 20, 60)}
    ma20_series = [average(closes[i - 19:i + 1]) for i in range(19, len(closes))]
    ma20_slope = None
    if len(ma20_series) >= 6 and ma20_series[-6]:
        ma20_slope = ma20_series[-1] / ma20_series[-6] - 1
    prior5_amounts = [x for x in amounts[-6:-1] if x > 0]
    amount_ratio = amounts[-1] / average(prior5_amounts) if amounts[-1] > 0 and prior5_amounts else None

    returns: dict[str, float | None] = {}
    for w in (5, 10, 20):
        previous = closes[-1 - w] if len(closes) > w else None
        returns[f"return_{w}d"] = pct_change(current_close, previous)

    result = {
        "as_of": current["date"],
        "sample_count": len(rows),
        "open": current["open"], "high": current["high"], "low": current["low"], "close": current_close,
        **ma_values,
        **returns,
        "rsi14": rsi14(closes),
        "distance_ma20": pct_change(current_close, ma_values["ma20"]),
        "distance_ma60": pct_change(current_close, ma_values["ma60"]),
        "ma20_slope_5d": ma20_slope,
        "low_20d": min(closes[-20:]), "high_20d": max(closes[-20:]),
        "low_60d": min(closes[-60:]) if len(closes) >= 60 else min(closes),
        "high_60d": max(closes[-60:]) if len(closes) >= 60 else max(closes),
        "amount": amounts[-1] if amounts[-1] > 0 else None,
        "amount_vs_prior5": amount_ratio,
        "volume_state": volume_label(amount_ratio),
    }
    result["trend_state"] = technical_state(current_close, result["ma20"], result["ma60"], ma20_slope)
    return result


def analyze(mapping_path: str, fund_codes: list[str] | None = None, end: str | None = None, bars_json: str | None = None, nav_bars_json: str | None = None) -> dict[str, Any]:
    mapping = load_mapping(mapping_path)
    selected = [code6(x) for x in fund_codes] if fund_codes else list(mapping)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for fund_code in selected:
        info = mapping.get(fund_code)
        if not info:
            warnings.append(f"{fund_code}不在基金映射中")
            continue
        etf_code = code6(info.get("target_etf_code")) if info.get("target_etf_code") else ""
        secid = str(info.get("secid") or "")
        if not etf_code or not secid:
            if nav_bars_json:
                try:
                    rows = load_offline_bars(nav_bars_json, fund_code)
                    if end:
                        rows = [x for x in rows if x["date"] <= end]
                    metrics = analyze_rows(rows)
                    metrics["amount"] = None
                    metrics["amount_vs_prior5"] = None
                    metrics["volume_state"] = "不适用（场外净值）"
                    results.append({"fund_code": fund_code, "fund_name": info.get("fund_name"), "source": "场外基金净值序列", "status": "ok_nav_only", **metrics})
                except Exception as exc:
                    warnings.append(f"{fund_code}净值技术面计算失败：{exc}")
                    results.append({"fund_code": fund_code, "status": "error", "error": str(exc)})
            else:
                warnings.append(f"{fund_code}没有唯一关联ETF；需提供净值历史才能分析趋势，且不能判断放量")
                results.append({"fund_code": fund_code, "fund_name": info.get("fund_name"), "status": "no_target_etf"})
            continue
        try:
            rows = load_offline_bars(bars_json, etf_code) if bars_json else fetch_bars(secid, end=end)
            if end:
                rows = [x for x in rows if x["date"] <= end]
            metrics = analyze_rows(rows)
            results.append({
                "fund_code": fund_code, "fund_name": info.get("fund_name"),
                "target_etf_code": etf_code, "target_etf_name": info.get("target_etf_name"),
                "secid": secid, "source": "offline_fixture" if bars_json else "东方财富ETF前复权日K",
                "status": "ok", **metrics,
            })
        except Exception as exc:
            warnings.append(f"{fund_code}/{etf_code}技术面计算失败：{exc}")
            results.append({"fund_code": fund_code, "target_etf_code": etf_code, "status": "error", "error": str(exc)})
    return {"generated_on": date.today().isoformat(), "end": end, "results": results, "warnings": warnings}


def fmt_pct(value: Any) -> str:
    return "" if value is None else f"{value:.2%}"


def markdown(result: dict[str, Any]) -> str:
    lines = ["# ETF技术面", "", "|基金|目标ETF|截止日|收盘|MA20|MA60|20日收益|RSI14|量能|趋势|", "|---|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in result["results"]:
        if r.get("status") not in ("ok", "ok_nav_only"):
            lines.append(f"|{r.get('fund_code','')}|{r.get('target_etf_code','')}||||||||{r.get('status')}|")
            continue
        lines.append(f"|{r['fund_code']}|{r['target_etf_code']}|{r['as_of']}|{r['close']:.4f}|{r['ma20']:.4f}|{'' if r['ma60'] is None else f'{r['ma60']:.4f}'}|{fmt_pct(r['return_20d'])}|{r['rsi14']:.1f}|{r['volume_state']}({'' if r['amount_vs_prior5'] is None else f'{r['amount_vs_prior5']:.2f}x'})|{r['trend_state']}|")
    if result["warnings"]:
        lines += ["", "## 警告"] + [f"- {x}" for x in result["warnings"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="计算关联ETF的K线、均线、RSI和成交额指标")
    parser.add_argument("fund_codes", nargs="*")
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--end")
    parser.add_argument("--bars-json", help="离线ETF日K JSON；可按ETF代码分组")
    parser.add_argument("--nav-bars-json", help="无关联ETF时使用的场外基金历史净值JSON；按基金代码分组")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze(args.mapping, args.fund_codes, args.end, args.bars_json, args.nav_bars_json)
    text = dump_json(result) if args.format == "json" else markdown(result)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not any(x.get("status") == "error" for x in result["results"]) else 1


if __name__ == "__main__":
    sys.exit(main())
