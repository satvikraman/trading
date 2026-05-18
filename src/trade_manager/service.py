import configparser
import csv
import datetime
import logging
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from persistence import persistence  # noqa: E402
from mapIciciToNseStock import MapIciciToNseStock  # noqa: E402
from security_master_sync import (  # noqa: E402
    DEFAULT_ICICI_ZIP_URL,
    ensure_icici_security_master,
    resolve_repo_path,
)

from .symbol_resolver import resolve_symbol  # noqa: E402
from .trade_id import decode_trade_id, encode_trade_id  # noqa: E402
from .validation import ValidationError, validate_trade_payload  # noqa: E402


def _symbol_lookup_rank(sym: str, q: str) -> tuple[int, str]:
    """Rank: exact match, then prefix, then substring; alphabetical within tier."""
    s = sym.upper()
    query = q.upper()
    if s == query:
        return (0, s)
    if s.startswith(query):
        return (1, s)
    return (2, s)


def _symbol_matches_lookup_query(sym: str, q: str) -> bool:
    s = sym.upper()
    if s == q or s.startswith(q):
        return True
    if len(q) <= 2:
        return False
    return q in s


def _load_dataset_config(config, root: Path) -> dict[str, str]:
    if config.has_section("DATASET"):
        return {
            "zip_url": config.get("DATASET", "ICICI_DATASET", fallback=DEFAULT_ICICI_ZIP_URL),
            "nse": config.get("DATASET", "NSE_DATASET", fallback="./dataset/NSEScripMaster.txt"),
            "bse": config.get("DATASET", "BSE_DATASET", fallback="./dataset/BSEScripMaster.txt"),
            "fno": config.get("DATASET", "FNO_DATASET", fallback="./dataset/FONSEScripMaster.txt"),
        }
    # Fallback to ICICI config used by appIciciBreeze
    icici_ini = root / "src/icici/iciciDirect.ini"
    if icici_ini.is_file():
        icici = configparser.ConfigParser()
        icici.read(icici_ini)
        if icici.has_section("DATASET"):
            return {
                "zip_url": icici.get("DATASET", "ICICI_DATASET", fallback=DEFAULT_ICICI_ZIP_URL),
                "nse": icici.get("DATASET", "NSE_DATASET", fallback="./dataset/NSEScripMaster.txt"),
                "bse": icici.get("DATASET", "BSE_DATASET", fallback="./dataset/BSEScripMaster.txt"),
                "fno": icici.get("DATASET", "FNO_DATASET", fallback="./dataset/FONSEScripMaster.txt"),
            }
    return {
        "zip_url": DEFAULT_ICICI_ZIP_URL,
        "nse": "./dataset/NSEScripMaster.txt",
        "bse": "./dataset/BSEScripMaster.txt",
        "fno": "./dataset/FONSEScripMaster.txt",
    }


class TradeService:
    def __init__(self, config_path=None, refresh_dataset: bool = True):
        root = Path(__file__).resolve().parents[2]
        self.__root = root
        config_path = config_path or root / "src/paytm/payTmMoney.ini"
        self.__config = configparser.ConfigParser()
        self.__config.read(config_path)
        self.__logger = logging.getLogger(__name__)

        dataset_cfg = _load_dataset_config(self.__config, root)
        if refresh_dataset:
            try:
                paths, _downloaded = ensure_icici_security_master(
                    root,
                    zip_url=dataset_cfg["zip_url"],
                    nse_dataset=dataset_cfg["nse"],
                    bse_dataset=dataset_cfg["bse"],
                    fno_dataset=dataset_cfg["fno"],
                    env_path=root / ".env",
                    logger=self.__logger,
                )
            except RuntimeError as exc:
                self.__logger.warning("%s", exc)
                paths = {
                    "NSE": resolve_repo_path(root, dataset_cfg["nse"]),
                    "BSE": resolve_repo_path(root, dataset_cfg["bse"]),
                    "FNO": resolve_repo_path(root, dataset_cfg["fno"]),
                }
        else:
            paths = {
                "NSE": resolve_repo_path(root, dataset_cfg["nse"]),
                "BSE": resolve_repo_path(root, dataset_cfg["bse"]),
                "FNO": resolve_repo_path(root, dataset_cfg["fno"]),
            }

        self.__nse_master = paths["NSE"]
        self.__mapper = MapIciciToNseStock(
            str(paths["NSE"]),
            str(paths["BSE"]),
            str(paths["FNO"]),
        )

        db = self.__config["DATABASE"]["DB_EQUITY"]
        if not os.path.isabs(db):
            db = str(root / db)
        self.__store = persistence(self.__logger, db)
        self.__cache = {"data": None, "ts": 0.0}
        self.__ttl = 10.0

    def refresh_security_master(self, force: bool = False) -> dict[str, str]:
        dataset_cfg = _load_dataset_config(self.__config, self.__root)
        paths, _downloaded = ensure_icici_security_master(
            self.__root,
            zip_url=dataset_cfg["zip_url"],
            nse_dataset=dataset_cfg["nse"],
            bse_dataset=dataset_cfg["bse"],
            fno_dataset=dataset_cfg["fno"],
            env_path=self.__root / ".env",
            logger=self.__logger,
            force=force,
        )
        self.__nse_master = paths["NSE"]
        self.__mapper = MapIciciToNseStock(
            str(paths["NSE"]),
            str(paths["BSE"]),
            str(paths["FNO"]),
        )
        return {k: str(v) for k, v in paths.items()}

    def _resolve_symbol(self, mkt_symbol, product="CASH", mkt="NSE", security_id=None):
        return resolve_symbol(
            self.__mapper,
            self.__store,
            mkt_symbol,
            product=product,
            mkt=mkt,
            security_id=security_id,
            nse_master_path=self.__nse_master,
        )

    def _backup(self):
        db = self.__config["DATABASE"]["DB_EQUITY"]
        root = self.__root
        if not os.path.isabs(db):
            db = str(root / db)
        backup_dir = Path(db).parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        if Path(db).exists():
            stamp = datetime.datetime.now().strftime("%d-%b-%Y-%H-%M-%S")
            ext = Path(db).suffix
            shutil.copy2(db, backup_dir / f"{Path(db).stem}-{stamp}{ext}")

    def _invalidate(self):
        self.__cache["data"] = None

    def _trade_rows_for_symbol(self, mkt_symbol: str, active_only: bool = False):
        sym = mkt_symbol.strip().upper()
        rows = self.__store.getDb([])
        matched = [r for r in rows if (r.get("MKT_SYMBOL") or "").upper() == sym]
        if active_only:
            matched = [r for r in matched if r.get("POS_HOLD_STATUS") != "CLOSE"]
        return matched

    def preview_symbol_rename(
        self,
        from_mkt_symbol: str,
        to_mkt_symbol: str,
        *,
        update_security_id: bool = True,
        active_only: bool = False,
    ):
        from_sym = from_mkt_symbol.strip().upper()
        to_sym = to_mkt_symbol.strip().upper()
        if not from_sym or not to_sym:
            raise ValidationError(
                [
                    {"field": "from_mkt_symbol", "message": "From and to symbols are required"},
                    {"field": "to_mkt_symbol", "message": "From and to symbols are required"},
                ]
            )
        if from_sym == to_sym:
            raise ValidationError(
                [{"field": "to_mkt_symbol", "message": "From and to symbols must be different"}]
            )

        ok, sec_id, icici, mkt_sym, mkt = self._resolve_symbol(to_sym)
        if not ok:
            raise ValidationError(
                [
                    {
                        "field": "to_mkt_symbol",
                        "message": f"'{to_sym}' not found in NSEScripMaster (ExchangeCode)",
                    }
                ]
            )

        rows = self._trade_rows_for_symbol(from_sym, active_only)
        conflicts = []
        would_update = []
        for row in rows:
            new_key = [
                ["SOURCE", row["SOURCE"]],
                ["MKT_SYMBOL", mkt_sym],
                ["STRATEGY", row["STRATEGY"]],
                ["REC_DATE", row["REC_DATE"]],
                ["REC_TIME", row["REC_TIME"]],
            ]
            exists, existing = self.__store.isInDb(new_key)
            old_key = [
                ["SOURCE", row["SOURCE"]],
                ["MKT_SYMBOL", row["MKT_SYMBOL"]],
                ["STRATEGY", row["STRATEGY"]],
                ["REC_DATE", row["REC_DATE"]],
                ["REC_TIME", row["REC_TIME"]],
            ]
            if exists and encode_trade_id(existing) != encode_trade_id(row):
                conflicts.append(
                    {
                        "from": encode_trade_id(row),
                        "reason": "Target row already exists with same source/strategy/date/time",
                        "existing_id": encode_trade_id(existing),
                    }
                )
            else:
                would_update.append(
                    {
                        "id": encode_trade_id(row),
                        "SOURCE": row["SOURCE"],
                        "STRATEGY": row["STRATEGY"],
                        "REC_DATE": row["REC_DATE"],
                        "REC_TIME": row["REC_TIME"],
                        "POS_HOLD_QTY": row.get("POS_HOLD_QTY", 0),
                    }
                )

        return {
            "from_mkt_symbol": from_sym,
            "to_mkt_symbol": mkt_sym,
            "security_id": sec_id if update_security_id else None,
            "mkt": mkt,
            "icici_symbol": icici,
            "match_count": len(rows),
            "would_update_count": len(would_update),
            "conflict_count": len(conflicts),
            "would_update": would_update[:20],
            "conflicts": conflicts[:20],
        }

    def rename_symbol(
        self,
        from_mkt_symbol: str,
        to_mkt_symbol: str,
        *,
        update_security_id: bool = True,
        active_only: bool = False,
    ):
        preview = self.preview_symbol_rename(
            from_mkt_symbol,
            to_mkt_symbol,
            update_security_id=update_security_id,
            active_only=active_only,
        )
        if preview["conflict_count"] > 0:
            raise ValidationError(
                [
                    {
                        "field": "to_mkt_symbol",
                        "message": (
                            f"{preview['conflict_count']} row(s) would collide with an existing "
                            f"{preview['to_mkt_symbol']} trade (same source/strategy/date/time). "
                            "Resolve duplicates first."
                        ),
                    }
                ]
            )

        self._backup()
        to_sym = preview["to_mkt_symbol"]
        sec_id = preview["security_id"]
        icici = preview["icici_symbol"]
        mkt = preview["mkt"]
        updated = 0

        for row in self._trade_rows_for_symbol(preview["from_mkt_symbol"], active_only):
            query = [
                ["SOURCE", row["SOURCE"]],
                ["MKT_SYMBOL", row["MKT_SYMBOL"]],
                ["STRATEGY", row["STRATEGY"]],
                ["REC_DATE", row["REC_DATE"]],
                ["REC_TIME", row["REC_TIME"]],
            ]
            merged = {**row, "MKT_SYMBOL": to_sym, "STOCK": to_sym}
            if update_security_id and sec_id:
                merged["SECURITY_ID"] = sec_id
                merged["ICICI_SYMBOL"] = icici
                merged["MKT"] = mkt
            if not self.__store.updateDb(merged, query):
                raise ValidationError(
                    [
                        {
                            "field": "from_mkt_symbol",
                            "message": f"Failed to update row {encode_trade_id(row)}",
                        }
                    ]
                )
            updated += 1

        self._invalidate()
        return {
            "updated": updated,
            "from_mkt_symbol": preview["from_mkt_symbol"],
            "to_mkt_symbol": to_sym,
            "security_id": sec_id if update_security_id else None,
        }

    def list_trades(
        self,
        source=None,
        rec_status=None,
        pos_hold_status=None,
        mkt_symbol=None,
        active_only=False,
    ):
        now = time.time()
        if self.__cache["data"] is not None and now - self.__cache["ts"] < self.__ttl:
            rows = self.__cache["data"]
        else:
            rows = self.__store.getDb([])
            self.__cache = {"data": rows, "ts": now}

        def match(row):
            if active_only and row.get("POS_HOLD_STATUS") == "CLOSE":
                return False
            if source and row.get("SOURCE") != source:
                return False
            if rec_status and row.get("REC_STATUS") != rec_status:
                return False
            if pos_hold_status and row.get("POS_HOLD_STATUS") != pos_hold_status:
                return False
            if mkt_symbol and mkt_symbol.upper() not in row.get("MKT_SYMBOL", "").upper():
                return False
            return True

        filtered = [r for r in rows if match(r)]
        return [{"id": encode_trade_id(r), "trade": r} for r in filtered]

    def get_trade(self, trade_id):
        query = decode_trade_id(trade_id)
        found, doc = self.__store.isInDb(query)
        if not found:
            return None
        return {"id": trade_id, "trade": doc}

    def list_sources(self):
        rows = self.__store.getDb([])
        return sorted({r.get("SOURCE", "") for r in rows if r.get("SOURCE")})

    def lookup_symbol(self, q, limit=20):
        q = (q or "").strip().upper()
        if len(q) < 1:
            return []
        matches: set[str] = set()

        if self.__nse_master.is_file():
            with open(self.__nse_master, encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    values = [v.strip().strip('"') for v in row.values()]
                    if len(values) < 4:
                        continue
                    exchange_code = values[-1].upper()
                    if _symbol_matches_lookup_query(exchange_code, q):
                        matches.add(exchange_code)

        for row in self.__store.getDb([]):
            sym = (row.get("MKT_SYMBOL") or "").upper()
            if sym and _symbol_matches_lookup_query(sym, q):
                matches.add(sym)

        ranked = sorted(matches, key=lambda s: _symbol_lookup_rank(s, q))

        out = []
        seen: set[str] = set()
        for sym in ranked:
            if sym in seen:
                continue
            ok, sec_id, icici, mkt_sym, mkt = self._resolve_symbol(sym)
            if not ok:
                continue
            seen.add(sym)
            out.append(
                {
                    "MKT_SYMBOL": mkt_sym,
                    "SECURITY_ID": sec_id,
                    "ICICI_SYMBOL": icici,
                    "MKT": mkt,
                    "STOCK": sym,
                }
            )
            if len(out) >= limit:
                break
        return out

    def create_trade(self, payload):
        self._backup()
        validate_trade_payload(payload.model_dump(), is_create=True)
        doc = payload.model_dump()
        if not doc.get("SECURITY_ID"):
            ok, sec_id, icici, mkt_sym, mkt = self._resolve_symbol(
                doc["MKT_SYMBOL"],
                product=doc.get("PRODUCT", "CASH"),
                mkt=doc.get("MKT", "NSE"),
            )
            if not ok:
                raise ValidationError(
                    [
                        {
                            "field": "MKT_SYMBOL",
                            "message": (
                                f"Unknown symbol '{doc['MKT_SYMBOL']}'. "
                                "Not found in NSEScripMaster (ExchangeCode). "
                                "Try Refresh or check the symbol."
                            ),
                        }
                    ]
                )
            doc["SECURITY_ID"] = sec_id
            doc["ICICI_SYMBOL"] = icici
            doc["MKT_SYMBOL"] = mkt_sym
            doc["MKT"] = mkt
        else:
            doc["SECURITY_ID"] = str(doc["SECURITY_ID"]).strip()
        if not doc.get("EXP_DATE"):
            doc["EXP_DATE"] = doc["REC_DATE"]
        doc["REC_STATUS"] = "OPEN"
        doc["VISIBLE"] = "VISIBLE"
        doc["POS_QTY"] = 0
        doc["HOLD_QTY"] = 0
        doc["POS_DATE"] = datetime.datetime.today().strftime("%d-%b-%Y")
        doc["OPEN_ORDERS"] = []
        doc["CLOSE_ORDERS"] = []
        doc["LATE_ADD"] = False

        if payload.mode == "already_held":
            doc["ACTION"] = "INIT_TRADE"
            doc["POS_HOLD_STATUS"] = "POSITION"
            doc["POS_HOLD_QTY"] = doc["QTY"]
            doc["HOLD_QTY"] = doc["QTY"]
            time_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")
            doc["OPEN_ORDERS"] = [
                {
                    "BUY_SELL": doc["BUY_SELL"],
                    "ORDER_TYPE": "LMT",
                    "LIMIT": doc["HIGH_REC_PRICE"],
                    "QTY": doc["QTY"],
                    "TRADED_QTY": doc["QTY"],
                    "ORDER_NO": "Dummy",
                    "ORDER_STATUS": "CLOSE",
                    "ORDER_MESSAGE": "Dummy",
                    "CREATE_TIME": time_str,
                }
            ]
        else:
            doc["POS_HOLD_STATUS"] = "OPEN"
            doc["POS_HOLD_QTY"] = 0

        if not self.__store.insertDb(doc, None):
            raise ValidationError([{"field": "key", "message": "Duplicate trade (same SOURCE/symbol/strategy/date/time)"}])
        self._invalidate()
        return self.get_trade(encode_trade_id(doc))

    def patch_trade(self, trade_id, patch):
        self._backup()
        current = self.get_trade(trade_id)
        if not current:
            return None
        existing = current["trade"]
        updates = {k: v for k, v in patch.model_dump().items() if v is not None}
        validate_trade_payload(updates, existing=existing)
        merged = {**existing, **updates}
        if (
            existing.get("POS_HOLD_STATUS") == "POSITION"
            and "QTY" in updates
            and updates["QTY"] > existing.get("QTY", 0)
        ):
            merged["POS_HOLD_STATUS"] = "OPEN"
        query = decode_trade_id(trade_id)
        if not self.__store.updateDb(merged, query):
            return None
        self._invalidate()
        return self.get_trade(trade_id)

    def close_trade(self, trade_id):
        self._backup()
        current = self.get_trade(trade_id)
        if not current:
            return None
        existing = current["trade"]
        if existing.get("REC_STATUS") not in ("OPEN", "PARTIAL_CLOSE"):
            raise ValidationError([{"field": "REC_STATUS", "message": "Trade is already closed"}])
        existing["REC_STATUS"] = "CLOSE"
        query = decode_trade_id(trade_id)
        self.__store.updateDb(existing, query)
        self._invalidate()
        return self.get_trade(trade_id)
