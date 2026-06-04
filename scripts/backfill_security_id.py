#!/usr/bin/env python3
"""Backfill missing SECURITY_ID on payTmMoney.db rows (in-place update)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "common"))
sys.path.insert(0, str(ROOT / "src"))

from mapIciciToNseStock import MapIciciToNseStock  # noqa: E402
from persistence import persistence  # noqa: E402
from trade_manager.symbol_resolver import resolve_symbol  # noqa: E402


def _normalize_security_id(security_id: str) -> str:
    sid = str(security_id or "").strip()
    if "!" in sid:
        return sid.rsplit("!", 1)[-1]
    return sid


def _missing_security_id(doc: dict) -> bool:
    return not _normalize_security_id(doc.get("SECURITY_ID") or "")


def _security_id_from_siblings(store, mkt_symbol: str) -> str:
    for row in store.getDb([["MKT_SYMBOL", mkt_symbol]]):
        sid = _normalize_security_id(row.get("SECURITY_ID") or "")
        if sid:
            return sid
    return ""


def main() -> int:
    db = ROOT / "src/paytm/db/payTmMoney.db"
    if not db.is_file():
        print(f"DB not found: {db}")
        return 1

    store = persistence(None, db)
    mapper = MapIciciToNseStock(
        str(ROOT / "dataset/NSEScripMaster.txt"),
        str(ROOT / "dataset/BSEScripMaster.txt"),
        str(ROOT / "dataset/FONSEScripMaster.txt"),
    )

    updated = 0
    failed = []

    for doc in store.getDb([]):
        if not _missing_security_id(doc):
            continue

        sym = (doc.get("MKT_SYMBOL") or "").strip().upper()
        product = doc.get("PRODUCT") or "CASH"
        mkt = doc.get("MKT") or "NSE"
        ok, sec_id, _icici, _mkt_sym, _mkt = resolve_symbol(
            mapper, store, sym, product=product, mkt=mkt
        )
        if not ok or not sec_id:
            sec_id = _security_id_from_siblings(store, sym)
        if not sec_id:
            failed.append(
                f"{sym} {doc.get('STRATEGY')} {doc.get('REC_DATE')} {doc.get('REC_TIME')}"
            )
            continue

        doc["SECURITY_ID"] = sec_id
        query = [
            ["SOURCE", doc["SOURCE"]],
            ["MKT_SYMBOL", doc["MKT_SYMBOL"]],
            ["STRATEGY", doc["STRATEGY"]],
            ["REC_DATE", doc["REC_DATE"]],
            ["REC_TIME", doc["REC_TIME"]],
        ]
        if not store.updateDb(doc, query):
            failed.append(
                f"update failed: {sym} {doc.get('STRATEGY')} {doc.get('REC_DATE')} {doc.get('REC_TIME')}"
            )
            continue

        updated += 1
        print(
            f"Updated {sym} {doc.get('STRATEGY')} {doc.get('REC_DATE')} {doc.get('REC_TIME')} -> SECURITY_ID={sec_id}"
        )

    remaining = sum(1 for doc in store.getDb([]) if _missing_security_id(doc))
    print(f"\nUpdated {updated} row(s). Remaining without SECURITY_ID: {remaining}")
    if failed:
        print("Failed:")
        for line in failed:
            print(f"  {line}")
        return 1
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
