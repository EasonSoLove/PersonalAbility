from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from common import code6, dump_json, load_funds_yaml, load_json, number

EASTMONEY_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def load_mapping(path: str) -> dict[str, dict[str, Any]]:
    raw = load_funds_yaml(path)
    result: dict[str, dict[str, Any]] = {}
    for fund in raw.get("funds", []):
        fund_code = code6(fund.get("code"))
        if not fund_code:
            continue
        etf = fund.get("linked_etf") or {}
        result[fund_code] = {
            "fund_code": fund_code,
            "fund_name": fund.get("name", ""),
            "target_etf_code": code6(etf.get("code")) if etf.get("code") else "",
            "target_etf_name": etf.get("name", ""),
            "exchange": etf.get("exchange", ""),
            "secid": etf.get("secid", ""),
        }
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


def ema_series(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (span + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def rolling_std(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    sample = values[-window:]
    mean = average(sample)
    if mean is None:
        return None
    return (sum((value - mean) ** 2 for value in sample) / window) ** 0.5


def kdj(highs: list[float], lows: list[float], closes: list[float], period: int = 9) -> dict[str, float | None]:
    if len(closes) < period:
        return {"k": None, "d": None, "j": None}
    k = d = 50.0
    j = None
    for index in range(period - 1, len(closes)):
        highest = max(highs[index - period + 1:index + 1])
        lowest = min(lows[index - period + 1:index + 1])
        rsv = 50.0 if highest == lowest else (closes[index] - lowest) / (highest - lowest) * 100
        k = (2 * k + rsv) / 3
        d = (2 * d + k) / 3
        j = 3 * k - 2 * d
    return {"k": k, "d": d, "j": j}


def macd(closes: list[float]) -> dict[str, float | None]:
    if len(closes) < 26:
        return {"dif": None, "dea": None, "hist": None}
    fast = ema_series(closes, 12)
    slow = ema_series(closes, 26)
    dif_series = [fast_value - slow_value for fast_value, slow_value in zip(fast, slow)]
    dea_series = ema_series(dif_series, 9)
    dif = dif_series[-1]
    dea = dea_series[-1]
    return {"dif": dif, "dea": dea, "hist": 2 * (dif - dea)}


def williams_r(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period:
        return None
    highest = max(highs[-period:])
    lowest = min(lows[-period:])
    return -50.0 if highest == lowest else (highest - closes[-1]) / (highest - lowest) * -100


def dmi(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> dict[str, float | None]:
    if len(closes) < period + 1:
        return {"plus_di": None, "minus_di": None, "adx": None}
    true_ranges: list[float] = []
    plus_moves: list[float] = []
    minus_moves: list[float] = []
    for index in range(1, len(closes)):
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_moves.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_moves.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        true_ranges.append(max(highs[index] - lows[index], abs(highs[index] - closes[index - 1]), abs(lows[index] - closes[index - 1])))
    dx_series: list[float] = []
    latest_plus = latest_minus = None
    for index in range(period - 1, len(true_ranges)):
        tr_sum = sum(true_ranges[index - period + 1:index + 1])
        plus_sum = sum(plus_moves[index - period + 1:index + 1])
        minus_sum = sum(minus_moves[index - period + 1:index + 1])
        if tr_sum == 0:
            continue
        latest_plus = plus_sum / tr_sum * 100
        latest_minus = minus_sum / tr_sum * 100
        denominator = latest_plus + latest_minus
        dx_series.append(abs(latest_plus - latest_minus) / denominator * 100 if denominator else 0.0)
    adx = average(dx_series[-period:]) if len(dx_series) >= period else None
    return {"plus_di": latest_plus, "minus_di": latest_minus, "adx": adx}


def bias(closes: list[float], period: int) -> float | None:
    moving_average = ma(closes, period)
    return None if moving_average in (None, 0) else (closes[-1] / moving_average - 1) * 100


def obv(closes: list[float], volumes: list[float]) -> dict[str, float | None]:
    if not closes or len(closes) != len(volumes):
        return {"value": None, "change_5d": None}
    values = [0.0]
    for index in range(1, len(closes)):
        direction = 1 if closes[index] > closes[index - 1] else -1 if closes[index] < closes[index - 1] else 0
        values.append(values[-1] + direction * volumes[index])
    return {"value": values[-1], "change_5d": values[-1] - values[-6] if len(values) >= 6 else None}


def cci(highs: list[float], lows: list[float], closes: list[float], period: int = 20) -> float | None:
    if len(closes) < period:
        return None
    typical_prices = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes)]
    window = typical_prices[-period:]
    mean = average(window)
    if mean is None:
        return None
    mean_deviation = average([abs(value - mean) for value in window])
    return None if not mean_deviation else (window[-1] - mean) / (0.015 * mean_deviation)


def roc(closes: list[float], period: int = 12) -> float | None:
    if len(closes) <= period or closes[-1 - period] == 0:
        return None
    return (closes[-1] / closes[-1 - period] - 1) * 100


def cr(highs: list[float], lows: list[float], period: int = 26) -> float | None:
    if len(highs) <= period or len(lows) != len(highs):
        return None
    up: list[float] = []
    down: list[float] = []
    for index in range(1, len(highs)):
        midpoint = (highs[index - 1] + lows[index - 1]) / 2
        up.append(max(highs[index] - midpoint, 0.0))
        down.append(max(midpoint - lows[index], 0.0))
    up_sum = sum(up[-period:])
    down_sum = sum(down[-period:])
    return None if down_sum == 0 else up_sum / down_sum * 100


def bollinger(closes: list[float], period: int = 20, deviations: float = 2.0) -> dict[str, float | None]:
    middle = ma(closes, period)
    deviation = rolling_std(closes, period)
    if middle is None or deviation is None:
        return {"middle": None, "upper": None, "lower": None, "bandwidth": None, "position": None}
    upper = middle + deviations * deviation
    lower = middle - deviations * deviation
    width = upper - lower
    return {"middle": middle, "upper": upper, "lower": lower, "bandwidth": width / middle if middle else None, "position": (closes[-1] - lower) / width if width else None}


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
    if len(rows) < 60:
        raise ValueError(f"daily bars insufficient: complete technical analysis requires 60, got {len(rows)}")
    closes = [number(x["close"]) for x in rows]
    highs = [number(x["high"]) for x in rows]
    lows = [number(x["low"]) for x in rows]
    volumes = [number(x.get("volume")) for x in rows]
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
        returns[f"return_{w}d"] = pct_change(current_close, closes[-1 - w])
    kdj_values = kdj(highs, lows, closes)
    macd_values = macd(closes)
    dmi_values = dmi(highs, lows, closes)
    obv_values = obv(closes, volumes)
    bollinger_values = bollinger(closes)
    result = {
        "as_of": current["date"], "sample_count": len(rows),
        "open": current["open"], "high": current["high"], "low": current["low"], "close": current_close,
        **ma_values, **returns,
        "rsi14": rsi14(closes), "distance_ma20": pct_change(current_close, ma_values["ma20"]),
        "distance_ma60": pct_change(current_close, ma_values["ma60"]), "ma20_slope_5d": ma20_slope,
        "low_20d": min(closes[-20:]), "high_20d": max(closes[-20:]),
        "low_60d": min(closes[-60:]), "high_60d": max(closes[-60:]),
        "amount": amounts[-1] if amounts[-1] > 0 else None, "amount_vs_prior5": amount_ratio,
        "volume_state": volume_label(amount_ratio),
        "kdj_k9": kdj_values["k"], "kdj_d9": kdj_values["d"], "kdj_j9": kdj_values["j"],
        "macd_dif": macd_values["dif"], "macd_dea": macd_values["dea"], "macd_hist": macd_values["hist"],
        "williams_r14": williams_r(highs, lows, closes),
        "dmi_plus_di14": dmi_values["plus_di"], "dmi_minus_di14": dmi_values["minus_di"], "dmi_adx14": dmi_values["adx"],
        "bias6": bias(closes, 6), "bias12": bias(closes, 12), "bias24": bias(closes, 24),
        "obv": obv_values["value"], "obv_change_5d": obv_values["change_5d"],
        "cci20": cci(highs, lows, closes), "roc12": roc(closes), "cr26": cr(highs, lows),
        "boll_mid20": bollinger_values["middle"], "boll_upper20": bollinger_values["upper"],
        "boll_lower20": bollinger_values["lower"], "boll_bandwidth20": bollinger_values["bandwidth"],
        "boll_position20": bollinger_values["position"],
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


def fmt_num(value: Any, digits: int = 2) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# ETF Technical Analysis", "",
        "|Fund|Target ETF|As of|Close|MA20|MA60|20d Return|RSI14|Volume|Trend|",
        "|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in result["results"]:
        if r.get("status") not in ("ok", "ok_nav_only"):
            lines.append(f"|{r.get('fund_code','')}|{r.get('target_etf_code','')}||||||||{r.get('status')}|")
            continue
        lines.append(f"|{r['fund_code']}|{r.get('target_etf_code','')}|{r['as_of']}|{r['close']:.4f}|{r['ma20']:.4f}|{r['ma60']:.4f}|{fmt_pct(r['return_20d'])}|{fmt_num(r['rsi14'], 1)}|{r['volume_state']}({'' if r['amount_vs_prior5'] is None else f'{r['amount_vs_prior5']:.2f}x'})|{r['trend_state']}|")
        lines += [
            "", f"## {r['fund_code']} Indicator Detail", "",
            "|Group|Indicator|Value|Interpretation|", "|---|---|---:|---|",
            f"|Trend|MA5 / MA10 / MA20 / MA60|{fmt_num(r['ma5'], 4)} / {fmt_num(r['ma10'], 4)} / {fmt_num(r['ma20'], 4)} / {fmt_num(r['ma60'], 4)}|Price versus averages and 5-day MA20 slope|",
            f"|Momentum|5d / 10d / 20d return|{fmt_pct(r['return_5d'])} / {fmt_pct(r['return_10d'])} / {fmt_pct(r['return_20d'])}|Multi-horizon momentum|",
            f"|Oscillator|RSI14 / KDJ(9,3,3)|{fmt_num(r['rsi14'], 1)} / K={fmt_num(r['kdj_k9'], 1)}, D={fmt_num(r['kdj_d9'], 1)}, J={fmt_num(r['kdj_j9'], 1)}|Overbought/oversold and short-term turns; not standalone signals|",
            f"|Trend momentum|MACD(12,26,9)|DIF={fmt_num(r['macd_dif'], 4)}, DEA={fmt_num(r['macd_dea'], 4)}, Hist={fmt_num(r['macd_hist'], 4)}|Direction and histogram momentum|",
            f"|Oscillator|W&R14 / CCI20|{fmt_num(r['williams_r14'], 1)} / {fmt_num(r['cci20'], 1)}|Range position and deviation|",
            f"|Trend strength|DMI14|+DI={fmt_num(r['dmi_plus_di14'], 1)}, -DI={fmt_num(r['dmi_minus_di14'], 1)}, ADX={fmt_num(r['dmi_adx14'], 1)}|Direction and strength; ADX is not directional|",
            f"|Deviation|BIAS6 / BIAS12 / BIAS24|{fmt_num(r['bias6'], 2)}% / {fmt_num(r['bias12'], 2)}% / {fmt_num(r['bias24'], 2)}%|Price deviation from averages|",
            f"|Volume-price|OBV / 5d change|{fmt_num(r['obv'], 0)} / {fmt_num(r['obv_change_5d'], 0)}|Volume-price confirmation for ETFs only|",
            f"|Momentum|ROC12 / CR26|{fmt_num(r['roc12'], 2)}% / {fmt_num(r['cr26'], 1)}|Rate of change and medium-term pressure|",
            f"|Volatility|BOLL20(2sigma)|Mid={fmt_num(r['boll_mid20'], 4)}, Upper={fmt_num(r['boll_upper20'], 4)}, Lower={fmt_num(r['boll_lower20'], 4)}, Width={fmt_pct(r['boll_bandwidth20'])}, Position={fmt_num(r['boll_position20'], 2)}|Channel, compression, and price position|",
        ]
    if result["warnings"]:
        lines += ["", "## Warnings"] + [f"- {x}" for x in result["warnings"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="计算关联ETF的trend, momentum, oscillator, volatility and volume indicators")
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
