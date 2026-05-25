#!/usr/bin/env python3
"""Insert or update MANUAL/CORE INIT_TRADE rows (run after migrate_json_to_sqlite.py)."""
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "common"))
sys.path.insert(0, str(ROOT / "src"))

from persistence import persistence  # noqa: E402
from mapIciciToNseStock import MapIciciToNseStock  # noqa: E402

# From master appPaytm.__core as of 17-May-2026
CORE = [
    {"MKT_SYMBOL": "IGIL", "SECURITY_ID": "28378", "QTY": 35},
    {"MKT_SYMBOL": "AADHARHFC", "SECURITY_ID": "23729", "QTY": 77},
    {"MKT_SYMBOL": "ADANIPORTS", "SECURITY_ID": "15083", "QTY": 114},
    {"MKT_SYMBOL": "ATHERENERG", "SECURITY_ID": "757645", "QTY": 22},
    {"MKT_SYMBOL": "CESC", "SECURITY_ID": "628", "QTY": 265},
    {"MKT_SYMBOL": "CGCL", "SECURITY_ID": "20329", "QTY": 40},
    {"MKT_SYMBOL": "FINCABLES", "SECURITY_ID": "1038", "QTY": 89},
    {"MKT_SYMBOL": "GRAVITA", "SECURITY_ID": "20534", "QTY": 43},
    {"MKT_SYMBOL": "THELEELA", "SECURITY_ID": "757014", "QTY": 69},
    {"MKT_SYMBOL": "NUVAMA", "SECURITY_ID": "18721", "QTY": 9},
    {"MKT_SYMBOL": "PFC", "SECURITY_ID": "14299", "QTY": 83},
    {"MKT_SYMBOL": "SAGILITY", "SECURITY_ID": "27052", "QTY": 136},
    {"MKT_SYMBOL": "SUZLON", "SECURITY_ID": "12018", "QTY": 1294},
    {"MKT_SYMBOL": "WELCORP", "SECURITY_ID": "11821", "QTY": 10},
    {"MKT_SYMBOL": "GOLDBETA", "SECURITY_ID": "14535", "QTY": 10663},
    {"MKT_SYMBOL": "SILVER", "SECURITY_ID": "8003", "QTY": 7702},
    {"MKT_SYMBOL": "HNGSNGBEES", "SECURITY_ID": "18284", "QTY": 180},
    {"MKT_SYMBOL": "MON100", "SECURITY_ID": "22739", "QTY": 76},
]

CORE_REC_DATE = "17-May-2026"
CORE_REC_TIME = "xx:xx"


def _find_core_row(store, mkt_symbol):
    rows = store.getDb(
        [
            ["SOURCE", "MANUAL"],
            ["MKT_SYMBOL", mkt_symbol],
            ["STRATEGY", "CORE"],
        ]
    )
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        return rows[0]
    return None


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

    for core in CORE:
        doc = {
            "STOCK": core["MKT_SYMBOL"],
            "SOURCE": "MANUAL",
            "MKT": "NSE",
            "MKT_SYMBOL": core["MKT_SYMBOL"],
            "SECURITY_ID": core["SECURITY_ID"],
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
            "QTY": core["QTY"],
            "POS_QTY": 0,
            "HOLD_QTY": core["QTY"],
            "POS_HOLD_QTY": core["QTY"],
            "POS_HOLD_STATUS": "POSITION",
            "POS_DATE": today,
            "VISIBLE": "VISIBLE",
            "LATE_ADD": False,
            "OPEN_ORDERS": [
                {
                    "BUY_SELL": "BUY",
                    "ORDER_TYPE": "LMT",
                    "LIMIT": 1.0,
                    "QTY": core["QTY"],
                    "TRADED_QTY": core["QTY"],
                    "ORDER_NO": "Dummy",
                    "ORDER_STATUS": "CLOSE",
                    "ORDER_MESSAGE": "Dummy",
                    "CREATE_TIME": time_str,
                }
            ],
            "CLOSE_ORDERS": [],
        }
        ok, sec_id, icici, mkt_sym, mkt, lot, product = mapper.mapICICSymbolToMktSymbol(
            core["MKT_SYMBOL"], core["MKT_SYMBOL"], "CASH", "NSE"
        )
        if ok:
            doc["SECURITY_ID"] = sec_id
            doc["MKT_SYMBOL"] = mkt_sym

        existing = _find_core_row(store, doc["MKT_SYMBOL"])
        if existing:
            merged = {**existing, **doc}
            query = [
                ["SOURCE", "MANUAL"],
                ["MKT_SYMBOL", doc["MKT_SYMBOL"]],
                ["STRATEGY", "CORE"],
                ["REC_DATE", existing["REC_DATE"]],
                ["REC_TIME", existing["REC_TIME"]],
            ]
            store.updateDb(merged, query)
            print(f"Updated CORE {doc['MKT_SYMBOL']} qty={core['QTY']}")
            continue

        if not store.insertDb(doc, None):
            print(f"Skip duplicate CORE {doc['MKT_SYMBOL']}")
            continue
        print(f"Inserted CORE {doc['MKT_SYMBOL']} qty={core['QTY']}")
    print("Done.")


if __name__ == "__main__":
    main()
