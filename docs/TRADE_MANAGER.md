# Paytm Trade Manager

Local web UI and FastAPI service for managing equity trades in `src/paytm/db/payTmMoney.db`. `appPaytm` reads the same SQLite file on its reconcile loop (~1s).

## Prerequisites

- Python 3.11+ with `.venv` at repo root: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Node.js for UI dev: `cd ui && npm install`

## One-time migration (TinyDB JSON → SQLite)

```bash
.venv/bin/python scripts/migrate_json_to_sqlite.py
```

Optional: seed former `__core` holdings as MANUAL `INIT_TRADE` rows:

```bash
.venv/bin/python scripts/migrate_core_to_db.py
```

## Run API (port 5002)

From repo root:

```bash
export PYTHONPATH=src
.venv/bin/uvicorn trade_manager.api:app --host 127.0.0.1 --port 5002 --reload
```

## Run UI (dev, port 5173)

```bash
cd ui && npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to port 5002.

## Production-style (API serves built UI)

```bash
cd ui && npm run build
export PYTHONPATH=src
.venv/bin/uvicorn trade_manager.api:app --host 127.0.0.1 --port 5002
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
.venv/bin/pytest src/common/test/test_sqlite_persistence.py src/trade_manager/test/test_validation.py -q
```
