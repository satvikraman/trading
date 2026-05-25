# Paytm Trade Manager

Local web UI and FastAPI service for managing equity trades in `src/paytm/db/payTmMoney.db`. `appPaytm` reads the same SQLite file on its reconcile loop (~1s).

## Prerequisites

- Python 3.11+ with `.venv` at repo root: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Node.js for UI dev: `cd ui && npm install`
- Network on first run of the day (or when `dataset/NSEScripMaster.txt` is missing): Trade Manager downloads the public ICICI [SecurityMaster.zip](https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip) into `dataset/`, same as `appIciciBreeze.py`. Symbol lookup uses `ExchangeCode` from `NSEScripMaster.txt` (no hardcoded symbol list).
- The same startup / `POST /api/dataset/refresh` also downloads Paytm `nse_security_master.csv` and `bse_security_master.csv` (daily circuit `upper_limit` / `lower_limit`). Row highlights: **blue** = OPEN order(s) still in DB during market hours (appPaytm will not place another open until cleared); **red** = same, outside market hours; **amber** = order limit outside circuit band on an entry row (`POS_HOLD_STATUS=OPEN`, `REC_STATUS=OPEN`). To clear rejected/stale OPEN orders without closing the trade: **Adjust held qty** with `POS_HOLD_QTY` **0→0** (allowed any time `REC_STATUS` is not `CLOSE`).

## Database on GitHub

`src/paytm/db/payTmMoney.db` is tracked in git (~1.4MB) so you can pull the same DB on another laptop. After `git pull`, use it directly (no migrate needed unless you only updated the JSON).

Rebuild from JSON when `payTmMoney.json` changes (always run both, in order):

```bash
.venv/bin/python scripts/migrate_json_to_sqlite.py
.venv/bin/python scripts/migrate_core_to_db.py
```

`appPaytm` subtracts MANUAL/CORE rows from broker holdings before startup sync (same as the old `__core` list).

## Adjust held quantity (offline / missed appPaytm)

In **Trade view**, **click the `POS_HOLD_QTY` cell** on a row (hover shows it is clickable). You set held quantity; the service derives position fields. Changes require preview + typed **YES** confirm. Held qty cannot exceed trade `QTY`.

| Held qty change | POS_HOLD_STATUS | REC_STATUS | Orders |
|-----------------|-----------------|------------|--------|
| `0` → `0` (was 0) | `OPEN`→`OPEN`, `POSITION`→`OPEN`, `CLOSE`→`CLOSE` | unchanged | clear OPEN + CLOSE |
| `>0` → `0` | `CLOSE` | `CLOSE` | clear OPEN + CLOSE |
| `=` trade `QTY` | `POSITION` | unchanged | dummy filled buy |
| `1` … `QTY-1` | `OPEN` | unchanged | clear OPEN |
| `>0` while `POS_HOLD_STATUS` is `CLOSE` | — | — | rejected |

Example: SILVER CORE stuck at `OPEN`/`OPEN` → click `POS_HOLD_QTY`, set to trade `QTY`, confirm (same as **Already held** on create).

Other read-only columns can use the same click-to-edit pattern later (`CELL_FIELD_ACTIONS` in `App.jsx`).

## Run API (port 5004)

From repo root:

```bash
export PYTHONPATH=src
.venv/bin/uvicorn trade_manager.api:app --host 127.0.0.1 --port 5004 --reload
```

## Run UI (dev, port 5173)

```bash
cd ui && npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to port 5004.

## Production-style (API serves built UI)

```bash
cd ui && npm run build
export PYTHONPATH=src
.venv/bin/uvicorn trade_manager.api:app --host 127.0.0.1 --port 5004
```

Open http://127.0.0.1:5002

## Run appPaytm (unchanged)

```bash
export PYTHONPATH=src
.venv/bin/python src/paytm/appPaytm.py
```

Ensure `src/paytm/payTmMoney.ini` has `DB_EQUITY = ./src/paytm/db/payTmMoney.db`.

## Tests

```bash
export PYTHONPATH=src
.venv/bin/pytest src/common/test/test_sqlite_persistence.py src/trade_manager/test/test_validation.py src/trade_manager/test/test_held_qty.py -q
```
