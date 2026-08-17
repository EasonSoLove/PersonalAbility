from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from common import code6, dump_json, load_json, number

FUND_PAGE = "https://fund.eastmoney.com/{code}.html"
FUND_PROFILE = "https://fundf10.eastmoney.com/jbgk_{code}.html"
FUND_SEARCH = "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx"


def fetch_text(url: str, timeout: int = 15) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def strip_tags(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def profile_field(page: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*</th>\s*<td[^>]*>([\s\S]*?)</td>"
    match = re.search(pattern, page, re.I)
    return strip_tags(match.group(1)) if match else ""


def parse_rate(text: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text or "")
    return number(match.group(1)) / 100 if match else None


def parse_date(text: str) -> str:
    match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", text or "")
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}" if match else ""


def target_candidates(page: str, fund_code: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for hit in re.finditer(r"目标ETF", page, re.I):
        fragment = page[max(0, hit.start() - 250): hit.start() + 900]
        for match in re.finditer(r"href=[\"'][^\"']*?([01589]\d{5})[^\"']*[\"'][^>]*>([\s\S]*?)</a>", fragment, re.I):
            code = code6(match.group(1))
            name = strip_tags(match.group(2))
            if code and code != fund_code and (code, name) not in candidates:
                candidates.append((code, name))
    return candidates


def exchange_and_secid(etf_code: str) -> tuple[str, str]:
    if etf_code.startswith(("5", "6")):
        return "SH", f"1.{etf_code}"
    if etf_code.startswith(("1", "3")):
        return "SZ", f"0.{etf_code}"
    return "", ""


def load_cache(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    raw = load_json(path)
    funds = raw.get("funds", raw) if isinstance(raw, dict) else raw
    result: dict[str, dict[str, Any]] = {}
    for item in funds or []:
        if isinstance(item, dict):
            code = code6(item.get("fund_code", item.get("code")))
            if code:
                result[code] = dict(item)
    return result


def search_name(code: str) -> str:
    query = urllib.parse.urlencode({"m": "1", "key": code})
    text = fetch_text(FUND_SEARCH + "?" + query)
    if text.lstrip().startswith("[") or text.lstrip().startswith("{"):
        raw = json.loads(text)
    else:
        match = re.search(r"\((.*)\)\s*;?\s*$", text, re.S)
        raw = json.loads(match.group(1)) if match else {}
    datas = raw.get("Datas", raw.get("data", [])) if isinstance(raw, dict) else raw
    for item in datas or []:
        item_code = code6(item.get("CODE", item.get("Code", item.get("code"))))
        if item_code == code:
            return str(item.get("NAME", item.get("Name", item.get("name", "")))).strip()
    return ""


def normalize_cached(code: str, item: dict[str, Any], synced_at: str) -> dict[str, Any]:
    result = dict(item)
    result["fund_code"] = code
    result.setdefault("source_url", FUND_PAGE.format(code=code))
    result["target_etf_code"] = code6(result.get("target_etf_code")) if result.get("target_etf_code") else ""
    result["synced_at"] = synced_at
    return result


def query_one(code: str, cached: dict[str, Any] | None, offline: bool, synced_at: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if offline:
        if not cached:
            return {"fund_code": code, "source_url": FUND_PAGE.format(code=code), "synced_at": synced_at}, [f"{code}离线缓存不存在"]
        return normalize_cached(code, cached, synced_at), warnings

    try:
        main_page = fetch_text(FUND_PAGE.format(code=code))
        profile = fetch_text(FUND_PROFILE.format(code=code))
    except Exception as exc:
        if cached:
            warnings.append(f"{code}联网失败，使用缓存：{exc}")
            return normalize_cached(code, cached, synced_at), warnings
        return {"fund_code": code, "source_url": FUND_PAGE.format(code=code), "synced_at": synced_at}, [f"{code}联网查询失败：{exc}"]

    title_match = re.search(r"<title>([\s\S]*?)</title>", main_page, re.I)
    title = strip_tags(title_match.group(1)) if title_match else ""
    name = profile_field(profile, "基金全称") or profile_field(profile, "基金简称")
    if not name:
        name = re.split(r"[（(]", title)[0].replace("基金净值", "").strip()
    if not name:
        try:
            name = search_name(code)
        except Exception as exc:
            warnings.append(f"{code}名称搜索失败：{exc}")

    tracked_index = profile_field(profile, "业绩比较基准")
    inception = parse_date(profile_field(profile, "成立日期/规模") or profile_field(profile, "成立日期"))
    service_text = profile_field(profile, "销售服务费率") or profile_field(profile, "销售服务费")
    redemption = profile_field(profile, "赎回费率") or profile_field(profile, "赎回费")

    candidates = target_candidates(main_page + profile, code)
    target_code = target_name = ""
    if len(candidates) == 1:
        target_code, target_name = candidates[0]
    elif len(candidates) > 1:
        warnings.append(f"{code}页面出现多个目标ETF候选：{[x[0] for x in candidates]}，未自动选择")
    elif cached and cached.get("target_etf_code"):
        target_code = code6(cached.get("target_etf_code"))
        target_name = str(cached.get("target_etf_name") or "")
        warnings.append(f"{code}本次未从页面唯一识别目标ETF，保留缓存映射{target_code}，需人工复核")
    else:
        warnings.append(f"{code}未唯一识别关联场内ETF；技术分析只能使用净值序列，不能判断放量")

    exchange, secid = exchange_and_secid(target_code) if target_code else ("", "")
    result = {
        "fund_code": code,
        "fund_name": name,
        "theme": (cached or {}).get("theme", ""),
        "tracked_index": tracked_index or (cached or {}).get("tracked_index", ""),
        "target_etf_code": target_code,
        "target_etf_name": target_name,
        "exchange": exchange,
        "secid": secid,
        "inception_date": inception or (cached or {}).get("inception_date", ""),
        "sales_service_fee": parse_rate(service_text) if service_text else (cached or {}).get("sales_service_fee"),
        "redemption_note": redemption or (cached or {}).get("redemption_note", ""),
        "source_url": FUND_PAGE.format(code=code),
        "synced_at": synced_at,
    }
    if not result["fund_name"]:
        warnings.append(f"{code}基金名称未解析成功")
    return result, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="从天天基金查询任意基金并输出基金信息Sheet标准字段")
    parser.add_argument("fund_codes", nargs="+")
    parser.add_argument("--cache")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--synced-at", default=date.today().isoformat())
    parser.add_argument("--output")
    args = parser.parse_args()

    cache = load_cache(args.cache)
    funds: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for raw_code in args.fund_codes:
        code = code6(raw_code)
        if not re.fullmatch(r"\d{6}", code) or code in seen:
            if code not in seen:
                warnings.append(f"无效基金代码：{raw_code}")
            continue
        seen.add(code)
        item, item_warnings = query_one(code, cache.get(code), args.offline, args.synced_at)
        funds.append(item)
        warnings.extend(item_warnings)

    result = {"source": "天天基金", "synced_at": args.synced_at, "funds": funds, "warnings": warnings}
    text = dump_json(result)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if funds else 1


if __name__ == "__main__":
    sys.exit(main())
