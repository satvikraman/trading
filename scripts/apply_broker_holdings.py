#!/usr/bin/env python3
"""Apply broker-reported holdings to payTmMoney.db (close stale rows, update CORE)."""
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "common"))
sys.path.insert(0, str(ROOT / "src"))

from persistence import persistence  # noqa: E402
from mapIciciToNseStock import MapIciciToNseStock  # noqa: E402

CORE_REC_DATE = "17-May-2026"
CORE_REC_TIME = "xx:xx"

# Sold — close all open non-CORE rows for these symbols
CLOSE_SYMBOLS = {"LUPIN", "ZYDUSLIFE", "JINDALSTEL", "INDHOTEL", "BAJAJ-AUTO"}

# No longer held — close MANUAL/CORE rows
CLOSE_CORE_SYMBOLS = {"CESC", "CGCL", "THELEELA", "AADHARHFC", "NUVAMA", "WELCORP"}

# Total Paytm qty (treated as CORE / long-term book)
BROKER_CORE_QTY = {
    "SUZLON": 245,
    "GOLDBETA": 12084,
    "SILVER": 8978,
    "HNGSNGBEES": 649,
    "MON100": 335,
    "ADANIPORTS": 144,
    "ATHERENERG": 90,
    "FINCABLES": 146,
    "GRAVITA": 66,
    "PFC": 199,
    "SAGILITY": 1177,
    "BALRAMCHIN": 58,
    "EMCURE": 17,
    "KPIL": 4,
    "SAILIFE": 37,
    "RRKABEL": 6,
    "ADANIPOWER": 193,
}


def _close_row(store, doc):
    doc["REC_STATUS"] = "CLOSE"
    doc["POS_HOLD_STATUS"] = "CLOSE"
    doc["POS_HOLD_QTY"] = 0
    doc["POS_QTY"] = 0
    doc["HOLD_QTY"] = 0
    query = [
        ["SOURCE", doc["SOURCE"]],
        ["MKT_SYMBOL", doc["MKT_SYMBOL"]],
        ["STRATEGY", doc["STRATEGY"]],
        ["REC_DATE", doc["REC_DATE"]],
        ["REC_TIME", doc["REC_TIME"]],
    ]
    store.updateDb(doc, query)


def _find_core_row(store, mkt_symbol):
    rows = store.getDb(
        [["SOURCE", "MANUAL"], ["MKT_SYMBOL", mkt_symbol], ["STRATEGY", "CORE"]]
    )
    return rows[0] if rows else None


def _core_doc(mkt_symbol, security_id, qty, today, time_str):
    return {
        "STOCK": mkt_symbol,
        "SOURCE": "MANUAL",
        "MKT": "NSE",
        "MKT_SYMBOL": mkt_symbol,
        "SECURITY_ID": security_id,
        "STRATEGY": "CORE",
        "PRODUCT": "CASH",
        "BUY_SELL": "BUY",
        "REC_DATE": CORE_REC_DATE,
        "REC_TIME": CORE_REC_TIME,
        "REC_STATUS": "OPEN",
        "EXP_DATE": CORE_REC_DATE,
        "LOW_REC_PRICE": 1.0,
        "HIGH_REC_PRICE": 1.0,
        "TARGET": 999999.0,
        "STOP_LOSS": 0.01,
        "ACTION": "INIT_TRADE",
        "QTY": qty,
        "POS_QTY": 0,
        "HOLD_QTY": qty,
        "POS_HOLD_QTY": qty,
        "POS_HOLD_STATUS": "POSITION",
        "POS_DATE": today,
        "VISIBLE": "VISIBLE",
        "LATE_ADD": False,
        "OPEN_ORDERS": [
            {
                "BUY_SELL": "BUY",
                "ORDER_TYPE": "LMT",
                "LIMIT": 1.0,
                "QTY": qty,
                "TRADED_QTY": qty,
                "ORDER_NO": "Dummy",
                "ORDER_STATUS": "CLOSE",
                "ORDER_MESSAGE": "Dummy",
                "CREATE_TIME": time_str,
            }
        ],
        "CLOSE_ORDERS": [],
    }


def _upsert_core(store, mapper, mkt_symbol, qty, today, time_str):
    ok, sec_id, icici, mkt_sym, mkt, lot, product = mapper.mapICICSymbolToMktSymbol(
        mkt_symbol, mkt_symbol, "CASH", "NSE"
    )
    if not ok:
        print(f"WARN: could not map symbol {mkt_symbol}")
        sec_id, mkt_sym = "", mkt_symbol
    else:
        mkt_symbol = mkt_sym
    doc = _core_doc(mkt_symbol, sec_id, qty, today, time_str)
    existing = _find_core_row(store, mkt_symbol)
    if existing:
        merged = {**existing, **doc}
        query = [
            ["SOURCE", "MANUAL"],
            ["MKT_SYMBOL", mkt_symbol],
            ["STRATEGY", "CORE"],
            ["REC_DATE", existing["REC_DATE"]],
            ["REC_TIME", existing["REC_TIME"]],
        ]
        store.updateDb(merged, query)
        print(f"Updated CORE {mkt_symbol} qty={qty}")
    else:
        store.insertDb(doc, None)
        print(f"Inserted CORE {mkt_symbol} qty={qty}")


def _consolidated_report(store):
    """What startup sync uses: non-CORE db qty + CORE qty per symbol."""
    trading = {}
    for doc in store.getDb([["PRODUCT", "!MARGIN"]]):
        if doc.get("STRATEGY") == "CORE":
            continue
        if doc.get("POS_QTY", 0) == 0 and doc.get("POS_HOLD_QTY", 0) == 0:
            continue
        sym = doc["MKT_SYMBOL"]
        trading[sym] = trading.get(sym, 0) + doc["POS_HOLD_QTY"] - doc["POS_QTY"]

    core = {}
    for doc in store.getDb([["SOURCE", "MANUAL"], ["STRATEGY", "CORE"]]):
        if doc.get("REC_STATUS") == "CLOSE" or int(doc.get("POS_HOLD_QTY") or 0) == 0:
            continue
        sym = doc["MKT_SYMBOL"]
        core[sym] = core.get(sym, 0) + int(doc.get("POS_HOLD_QTY") or doc.get("QTY") or 0)

    all_syms = sorted(set(trading) | set(core))
    print("\n=== Consolidated (for broker sync) ===")
    print(f"{'SYMBOL':<14} {'CORE':>8} {'TRADING':>8} {'NOTES'}")
    print("-" * 50)
    for sym in all_syms:
        c = core.get(sym, 0)
        t = trading.get(sym, 0)
        note = ""
        if t > 0:
            strategies = [
                d["STRATEGY"]
                for d in store.getDb([["MKT_SYMBOL", sym], ["PRODUCT", "!MARGIN"]])
                if d.get("STRATEGY") != "CORE"
                and (d.get("POS_QTY", 0) != 0 or d.get("POS_HOLD_QTY", 0) != 0)
            ]
            note = "trading: " + ", ".join(sorted(set(strategies)))
        if c > 0 and t == 0:
            note = note or "core only"
        print(f"{sym:<14} {c:>8} {t:>8} {note}")

    print("\n=== Open non-CORE rows (detail) ===")
    for doc in sorted(
        store.getDb([["PRODUCT", "!MARGIN"]]),
        key=lambda d: (d["MKT_SYMBOL"], d["STRATEGY"], d["REC_DATE"]),
    ):
        if doc.get("STRATEGY") == "CORE":
            continue
        if doc.get("POS_QTY", 0) == 0 and doc.get("POS_HOLD_QTY", 0) == 0:
            continue
        print(
            f"  {doc['MKT_SYMBOL']:<12} {doc['STRATEGY']:<18} "
            f"hold={doc['POS_HOLD_QTY']} pos={doc['POS_QTY']} "
            f"{doc['REC_STATUS']}/{doc['POS_HOLD_STATUS']} {doc['REC_DATE']}"
        )


def main():
    db = ROOT / "src/paytm/db/payTmMoney.db"
    store = persistence(None, db)
    mapper = MapIciciToNseStock(
        str(ROOT / "dataset/NSEScripMaster.txt"),
        str(ROOT / "dataset/BSEScripMaster.txt"),
        str(ROOT / "dataset/FONSEScripMaster.txt"),
    )
    today = datetime.datetime.today().strftime("%d-%b-%Y")
    time_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")

    core_closed = 0
    for doc in store.getDb([["SOURCE", "MANUAL"], ["STRATEGY", "CORE"]]):
        if doc["MKT_SYMBOL"] not in CLOSE_CORE_SYMBOLS:
            continue
        if doc.get("POS_HOLD_QTY", 0) == 0 and doc.get("REC_STATUS") == "CLOSE":
            continue
        _close_row(store, doc)
        core_closed += 1
        print(f"Closed CORE {doc['MKT_SYMBOL']}")

    closed = 0
    for doc in store.getDb([["PRODUCT", "!MARGIN"]]):
        if doc.get("STRATEGY") == "CORE":
            continue
        if doc["MKT_SYMBOL"] not in CLOSE_SYMBOLS:
            continue
        if doc.get("POS_QTY", 0) == 0 and doc.get("POS_HOLD_QTY", 0) == 0:
            continue
        _close_row(store, doc)
        closed += 1
        print(f"Closed {doc['MKT_SYMBOL']} {doc['STRATEGY']} {doc['REC_DATE']}")

    for sym, qty in sorted(BROKER_CORE_QTY.items()):
        _upsert_core(store, mapper, sym, qty, today, time_str)

    print(f"\nClosed {core_closed} CORE row(s), {closed} stale trading row(s).")
    _consolidated_report(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
