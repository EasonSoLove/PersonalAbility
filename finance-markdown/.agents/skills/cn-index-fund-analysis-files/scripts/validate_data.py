from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from common import PROJECT_ROOT,  code6, decimal_or_none, fund_map, load_funds_yaml, load_schema, read_csv_rows, valid_iso_date
from portfolio_analysis import inspect_nav_cache

TX_ID_PATTERN = re.compile(r"^TX-\d{8}-\d{6}-\d{3,}$")
SECID_PATTERN = re.compile(r"^[01]\.\d{6}$")


def transaction_fingerprint(row: dict[str, str]) -> tuple[str, ...]:
    fields = ["申请日期", "确认日期", "基金代码", "交易类型", "申请成交金额", "确认份额", "确认净值", "实际到账分红", "确认状态"]
    return tuple((row.get(x) or "").strip() for x in fields)


def possible_duplicate_key(row: dict[str, str]) -> tuple[str, ...]:
    fields = ["申请日期", "基金代码", "交易类型", "申请成交金额", "确认份额"]
    return tuple((row.get(x) or "").strip() for x in fields)


def validate_funds(path: str | Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        document = load_funds_yaml(path)
    except Exception as exc:
        return {"errors": [f"基金档案无法解析：{exc}"], "warnings": [], "fund_count": 0}
    if document.get("schema_version") != "1.0.0":
        warnings.append(f"基金档案Schema版本为{document.get('schema_version')!r}，当前预期1.0.0")
    codes: list[str] = []
    for index, fund in enumerate(document.get("funds", []), 1):
        prefix = f"基金档案第{index}项"
        code = code6(fund.get("code"))
        codes.append(code)
        if not re.fullmatch(r"\d{6}", code):
            errors.append(f"{prefix}基金代码无效：{fund.get('code')!r}")
        if not str(fund.get("name") or "").strip():
            errors.append(f"{prefix}/{code}缺少基金名称")
        source_url = str(fund.get("source_url") or "")
        if not source_url.startswith("https://fund.eastmoney.com/"):
            warnings.append(f"{prefix}/{code}天天基金页面为空或格式异常")
        etf = fund.get("linked_etf") or {}
        etf_code = code6(etf.get("code")) if etf.get("code") else ""
        secid = str(etf.get("secid") or "")
        if etf_code and not re.fullmatch(r"\d{6}", etf_code):
            errors.append(f"{prefix}/{code}关联ETF代码无效：{etf.get('code')!r}")
        if etf_code and not SECID_PATTERN.fullmatch(secid):
            errors.append(f"{prefix}/{code}已有关联ETF但SecID无效：{secid!r}")
        if not etf_code and secid:
            errors.append(f"{prefix}/{code}没有关联ETF代码却填写了SecID")
        synced = str(fund.get("synced_at") or "")
        if synced and not valid_iso_date(synced):
            errors.append(f"{prefix}/{code}同步日期格式无效：{synced}")
    duplicates = [code for code, count in Counter(codes).items() if code and count > 1]
    if duplicates:
        errors.append(f"基金代码重复：{duplicates}")
    return {"errors": errors, "warnings": warnings, "fund_count": len(codes)}


def validate_transactions(path: str | Path, funds_path: str | Path, schema_path: str | Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    schema = load_schema(schema_path)["transactions"]
    expected = schema["headers"]
    try:
        headers, rows = read_csv_rows(path)
    except Exception as exc:
        return {"errors": [f"交易账本无法读取：{exc}"], "warnings": [], "transaction_count": 0, "pending_count": 0}
    if headers != expected:
        errors.append(f"交易账本表头不匹配。预期：{expected}；实际：{headers}")
        return {"errors": errors, "warnings": warnings, "transaction_count": len(rows), "pending_count": 0}
    funds = fund_map(funds_path)
    ids: list[str] = []
    exact_seen: dict[tuple[str, ...], str] = {}
    possible_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    conversion_groups: dict[str, list[str]] = defaultdict(list)
    pending_count = 0
    for index, row in enumerate(rows, 2):
        prefix = f"交易账本第{index}行"
        tx_id = row.get("交易ID", "")
        ids.append(tx_id)
        if not TX_ID_PATTERN.fullmatch(tx_id):
            errors.append(f"{prefix}交易ID无效：{tx_id!r}")
        request_date = row.get("申请日期", "")
        confirm_date = row.get("确认日期", "")
        if not valid_iso_date(request_date) or not request_date:
            errors.append(f"{prefix}/{tx_id}申请日期无效：{request_date!r}")
        if confirm_date and not valid_iso_date(confirm_date):
            errors.append(f"{prefix}/{tx_id}确认日期无效：{confirm_date!r}")
        if request_date and confirm_date and valid_iso_date(request_date) and valid_iso_date(confirm_date):
            if date.fromisoformat(confirm_date) < date.fromisoformat(request_date):
                errors.append(f"{prefix}/{tx_id}确认日期早于申请日期")
        code = code6(row.get("基金代码"))
        if not re.fullmatch(r"\d{6}", code):
            errors.append(f"{prefix}/{tx_id}基金代码无效：{row.get('基金代码')!r}")
        elif code not in funds:
            errors.append(f"{prefix}/{tx_id}基金代码{code}不在funds.yaml")
        tx_type = row.get("交易类型", "")
        if tx_type not in schema["transaction_types"]:
            errors.append(f"{prefix}/{tx_id}交易类型无效：{tx_type!r}")
        status = row.get("确认状态", "")
        if status not in schema["statuses"]:
            errors.append(f"{prefix}/{tx_id}确认状态无效：{status!r}")
        if status == "待确认":
            pending_count += 1
        for field in ["申请成交金额", "确认份额", "确认净值", "手续费", "实际到账分红"]:
            raw = row.get(field, "")
            if raw != "":
                value = decimal_or_none(raw)
                if value is None:
                    errors.append(f"{prefix}/{tx_id}{field}不是有效数字：{raw!r}")
                elif value < 0:
                    errors.append(f"{prefix}/{tx_id}{field}不能为负数")
        if status == "已确认":
            if not confirm_date:
                errors.append(f"{prefix}/{tx_id}状态为已确认但缺少确认日期")
            if tx_type in schema["confirmed_in"] + schema["confirmed_out"]:
                shares = decimal_or_none(row.get("确认份额"))
                if shares is None or shares <= 0:
                    errors.append(f"{prefix}/{tx_id}{tx_type}已确认但确认份额无效")
            if tx_type in ("买入", "定投"):
                amount = decimal_or_none(row.get("申请成交金额"))
                if amount is None or amount <= 0:
                    errors.append(f"{prefix}/{tx_id}{tx_type}已确认但申请成交金额无效")
            if tx_type == "卖出" and not row.get("实际到账分红") and not row.get("申请成交金额"):
                warnings.append(f"{prefix}/{tx_id}卖出缺少实际到账和成交金额，收益只能估算")
            if tx_type == "现金分红":
                received = decimal_or_none(row.get("实际到账分红"))
                if received is None or received <= 0:
                    errors.append(f"{prefix}/{tx_id}现金分红已确认但实际到账分红无效")
        if status == "待确认" and confirm_date:
            warnings.append(f"{prefix}/{tx_id}状态为待确认但已填写确认日期")
        exact = transaction_fingerprint(row)
        if exact in exact_seen and status != "已作废":
            warnings.append(f"{prefix}/{tx_id}与{exact_seen[exact]}字段完全相同，可能重复")
        else:
            exact_seen[exact] = tx_id
        possible_groups[possible_duplicate_key(row)].append(tx_id)
        link = row.get("关联交易ID", "")
        if tx_type in ("转换转入", "转换转出"):
            if not link:
                warnings.append(f"{prefix}/{tx_id}{tx_type}缺少关联交易ID")
            else:
                conversion_groups[link].append(tx_type)
    duplicate_ids = [tx_id for tx_id, count in Counter(ids).items() if tx_id and count > 1]
    if duplicate_ids:
        errors.append(f"交易ID重复：{duplicate_ids}")
    for key, group_ids in possible_groups.items():
        if len(group_ids) > 1 and any(key):
            warnings.append(f"疑似同日同基金同类型同金额/份额交易：{group_ids}")
    for link, types in conversion_groups.items():
        if Counter(types)["转换转入"] != Counter(types)["转换转出"]:
            warnings.append(f"转换关联组{link}转入/转出不成对：{types}")
    return {"errors": errors, "warnings": warnings, "transaction_count": len(rows), "pending_count": pending_count}


def validate_project(root: str | Path, nav_json: str | Path | None = None, as_of: date | None = None) -> dict[str, Any]:
    project = Path(root)
    funds_result = validate_funds(project / "data" / "funds.yaml")
    tx_result = validate_transactions(project / "data" / "transactions.csv", project / "data" / "funds.yaml", project / "data" / "schema.json")
    nav_result = inspect_nav_cache(nav_json, as_of) if nav_json else {"errors": [], "warnings": []}
    errors = funds_result["errors"] + tx_result["errors"] + nav_result["errors"]
    warnings = funds_result["warnings"] + tx_result["warnings"] + nav_result["warnings"]
    return {
        "status": "OK" if not errors else "ERROR",
        "schema_version": load_schema(project / "data" / "schema.json").get("version"),
        "fund_count": funds_result["fund_count"],
        "transaction_count": tx_result["transaction_count"],
        "pending_count": tx_result["pending_count"],
        "errors": errors,
        "warnings": warnings,
        "nav_cache": nav_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验YAML基金档案和CSV交易账本")
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--nav-json")
    parser.add_argument("--as-of")
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    result = validate_project(args.root, args.nav_json, as_of)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[{result['status']}] Schema {result['schema_version']}；基金{result['fund_count']}只；交易{result['transaction_count']}笔；待确认{result['pending_count']}笔")
        for item in result["errors"]:
            print(f"ERROR: {item}")
        for item in result["warnings"]:
            print(f"WARN: {item}")
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
