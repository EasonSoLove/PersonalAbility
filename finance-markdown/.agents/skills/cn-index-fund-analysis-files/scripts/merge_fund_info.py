from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from common import PROJECT_ROOT,  code6, dump_funds_yaml, load_funds_yaml, load_json, write_text_atomic


def merge(funds_path: str | Path, query_json: str | Path) -> dict:
    path = Path(funds_path)
    document = load_funds_yaml(path)
    raw = load_json(query_json)
    incoming = raw.get("funds", []) if isinstance(raw, dict) else []
    by_code = {code6(item.get("code")): dict(item) for item in document.get("funds", [])}
    added: list[str] = []
    updated: list[str] = []
    for item in incoming:
        code = code6(item.get("fund_code", item.get("code")))
        if not code:
            continue
        old = by_code.get(code, {"code": code})
        etf_old = old.get("linked_etf") or {}
        etf_code = code6(item.get("target_etf_code")) if item.get("target_etf_code") else etf_old.get("code", "")
        merged = {
            "code": code,
            "name": item.get("fund_name") or old.get("name", ""),
            "theme": item.get("theme") if item.get("theme") not in (None, "") else old.get("theme", ""),
            "tracked_index": item.get("tracked_index") if item.get("tracked_index") not in (None, "") else old.get("tracked_index", ""),
            "linked_etf": {
                "code": etf_code,
                "name": item.get("target_etf_name") or etf_old.get("name", ""),
                "exchange": item.get("exchange") or etf_old.get("exchange", ""),
                "secid": item.get("secid") or etf_old.get("secid", ""),
            },
            "inception_date": item.get("inception_date") or old.get("inception_date", ""),
            "sales_service_fee": item.get("sales_service_fee") if item.get("sales_service_fee") is not None else old.get("sales_service_fee"),
            "redemption_note": item.get("redemption_note") or old.get("redemption_note", ""),
            "source_url": item.get("source_url") or old.get("source_url", ""),
            "synced_at": item.get("synced_at") or raw.get("synced_at") or date.today().isoformat(),
        }
        if code in by_code:
            updated.append(code)
        else:
            added.append(code)
        by_code[code] = merged
    document["funds"] = list(by_code.values())
    document["updated_at"] = raw.get("synced_at") or date.today().isoformat()
    write_text_atomic(path, dump_funds_yaml(document))
    return {"status": "OK", "added": added, "updated": updated, "fund_count": len(document["funds"]), "warnings": raw.get("warnings", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description="把天天基金查询JSON安全合并到funds.yaml")
    parser.add_argument("query_json")
    parser.add_argument("--funds", default=str(PROJECT_ROOT / "data" / "funds.yaml"))
    args = parser.parse_args()
    result = merge(args.funds, args.query_json)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
