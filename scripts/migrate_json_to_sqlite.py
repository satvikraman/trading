#!/usr/bin/env python3
"""Migrate payTmMoney.json (TinyDB) to payTmMoney.db (SQLite)."""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "common"))

from sqlite_persistence import SqlitePersistence  # noqa: E402


def main():
    json_path = ROOT / "src/paytm/db/payTmMoney.json"
    db_path = ROOT / "src/paytm/db/payTmMoney.db"
    backup_dir = ROOT / "src/paytm/db/backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not json_path.exists():
        print(f"Missing {json_path}")
        return 1

    stamp = datetime.now().strftime("%d-%b-%Y-%H-%M-%S")
    backup_path = backup_dir / f"payTmMoney-{stamp}.json"
    shutil.copy2(json_path, backup_path)
    print(f"Backed up JSON to {backup_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    docs = list(data.get("_default", data).values())
    print(f"Found {len(docs)} records in JSON")

    if db_path.exists():
        db_backup = backup_dir / f"payTmMoney-{stamp}.db"
        shutil.copy2(db_path, db_backup)
        print(f"Existing DB backed up to {db_backup}")
        db_path.unlink()

    store = SqlitePersistence(None, db_path)
    inserted = 0
    for doc in docs:
        if store.insertDb(doc, None):
            inserted += 1
    store.close()

    verify = SqlitePersistence(None, db_path)
    count = len(verify.getDb([]))
    verify.close()

    print(f"Inserted {inserted} records; DB now has {count} rows")
    if count != len(docs):
        print("WARNING: row count mismatch")
        return 1
    print(f"Done. Update payTmMoney.ini DB_EQUITY to: ./src/paytm/db/payTmMoney.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
