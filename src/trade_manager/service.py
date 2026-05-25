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
from circuit_limit_cache import (  # noqa: E402
    CircuitLimitCache,
    limit_price_out_of_circuit,
    order_limit_price_for_check,
)
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


def _dummy_filled_open_order(doc: dict, traded_qty: int) -> dict:
    time_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")
    return {
        "BUY_SELL": doc.get("BUY_SELL", "BUY"),
        "ORDER_TYPE": "LMT",
        "LIMIT": doc.get("HIGH_REC_PRICE", 0),
        "QTY": traded_qty,
        "TRADED_QTY": traded_qty,
        "ORDER_NO": "Dummy",
        "ORDER_STATUS": "CLOSE",
        "ORDER_MESSAGE": "Dummy",
        "CREATE_TIME": time_str,
    }


def _demote_pos_hold_status_on_zero_clear(status: str) -> str:
    """OPEN→OPEN, POSITION→OPEN, CLOSE→CLOSE when clearing at zero held."""
    if status == "POSITION":
        return "OPEN"
    return status or "OPEN"


def apply_held_qty_to_trade(doc: dict, pos_hold_qty: int) -> dict:
    """
    Set position fields from held quantity (POS_HOLD_QTY).

    held == 0, was 0  -> clear orders; POS_HOLD_STATUS demotes POSITION→OPEN only
    held == 0, was >0 -> POS_HOLD_STATUS and REC_STATUS CLOSE; clear all orders
    held == QTY        -> POSITION, dummy filled OPEN_ORDERS, ACTION=INIT_TRADE
    0 < held < QTY     -> OPEN, partial HOLD_QTY, clear OPEN_ORDERS
    held > 0 while POS_HOLD_STATUS CLOSE -> validation error
    """
    merged = {**doc}
    qty = int(merged.get("QTY") or 0)
    held = int(pos_hold_qty)
    prev_held = int(doc.get("POS_HOLD_QTY") or 0)
    if held < 0:
        raise ValidationError([{"field": "pos_hold_qty", "message": "Held quantity must be >= 0"}])
    if held > 0 and doc.get("POS_HOLD_STATUS") == "CLOSE":
        raise ValidationError(
            [
                {
                    "field": "pos_hold_qty",
                    "message": "Cannot set held quantity > 0 while POS_HOLD_STATUS is CLOSE",
                }
            ]
        )
    if qty <= 0 and held > 0:
        raise ValidationError(
            [
                {
                    "field": "pos_hold_qty",
                    "message": "Cannot set held quantity > 0 when trade QTY is 0",
                }
            ]
        )
    if qty > 0 and held > qty:
        raise ValidationError(
            [
                {
                    "field": "pos_hold_qty",
                    "message": f"Held quantity cannot exceed trade QTY ({qty})",
                }
            ]
        )

    merged["POS_HOLD_QTY"] = held
    merged["POS_QTY"] = 0
    if not merged.get("POS_DATE"):
        merged["POS_DATE"] = datetime.datetime.today().strftime("%d-%b-%Y")

    if held == 0:
        merged["HOLD_QTY"] = 0
        merged["OPEN_ORDERS"] = []
        merged["CLOSE_ORDERS"] = []
        if prev_held > 0:
            merged["POS_HOLD_STATUS"] = "CLOSE"
            merged["REC_STATUS"] = "CLOSE"
        else:
            merged["POS_HOLD_STATUS"] = _demote_pos_hold_status_on_zero_clear(
                doc.get("POS_HOLD_STATUS") or "OPEN",
            )
            merged.pop("ACTION", None)
    elif qty > 0 and held == qty:
        merged["POS_HOLD_STATUS"] = "POSITION"
        merged["HOLD_QTY"] = held
        merged["ACTION"] = "INIT_TRADE"
        merged["OPEN_ORDERS"] = [_dummy_filled_open_order(merged, held)]
    else:
        merged["POS_HOLD_STATUS"] = "OPEN"
        merged["HOLD_QTY"] = held
        merged["OPEN_ORDERS"] = []

    return merged


def preview_held_qty_adjustment(doc: dict, pos_hold_qty: int) -> dict:
    """Return before/after summary for UI confirm (does not mutate DB)."""
    after = apply_held_qty_to_trade(doc, pos_hold_qty)
    return {
        "pos_hold_qty": int(pos_hold_qty),
        "trade_qty": int(doc.get("QTY") or 0),
        "before": {
            "POS_HOLD_STATUS": doc.get("POS_HOLD_STATUS"),
            "POS_HOLD_QTY": doc.get("POS_HOLD_QTY"),
            "HOLD_QTY": doc.get("HOLD_QTY"),
            "POS_QTY": doc.get("POS_QTY"),
            "REC_STATUS": doc.get("REC_STATUS"),
        },
        "after": {
            "POS_HOLD_STATUS": after.get("POS_HOLD_STATUS"),
            "POS_HOLD_QTY": after.get("POS_HOLD_QTY"),
            "HOLD_QTY": after.get("HOLD_QTY"),
            "POS_QTY": after.get("POS_QTY"),
            "REC_STATUS": after.get("REC_STATUS"),
            "OPEN_ORDERS": len(after.get("OPEN_ORDERS") or []),
            "CLOSE_ORDERS": len(after.get("CLOSE_ORDERS") or []),
        },
        "adds_dummy_open_order": bool(after.get("OPEN_ORDERS")),
        "clears_all_orders": int(pos_hold_qty) == 0,
        "closes_recommendation": after.get("REC_STATUS") == "CLOSE"
        and doc.get("REC_STATUS") != "CLOSE",
    }


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
        self.__circuit_cache: CircuitLimitCache | None = None
        self._init_circuit_cache(preload=True)

    def _init_circuit_cache(self, *, preload: bool = False) -> None:
        dataset_root = self.__root / "dataset"
        self.__circuit_cache = CircuitLimitCache(
            nse_csv=dataset_root / "nse_security_master.csv",
            bse_csv=dataset_root / "bse_security_master.csv",
            logger=self.__logger,
        )
        if preload:
            rows = self.__store.getDb([])
            active = [r for r in rows if r.get("POS_HOLD_STATUS") != "CLOSE"]
            self.__circuit_cache.preload_active_recs(active)

    def _enrich_circuit_fields(self, trade: dict) -> dict:
        enriched = {**trade}
        security_id = str(trade.get("SECURITY_ID") or "").strip()
        exchange = str(trade.get("MKT") or "NSE").strip().upper()
        limits = None
        if security_id and self.__circuit_cache is not None:
            limits = self.__circuit_cache.get_limits(security_id, exchange)
        if limits:
            enriched["CIRCUIT_UPPER"] = limits["upper"]
            enriched["CIRCUIT_LOWER"] = limits["lower"]
        else:
            enriched["CIRCUIT_UPPER"] = None
            enriched["CIRCUIT_LOWER"] = None
        enriched["CIRCUIT_LIMIT_OUT_OF_BAND"] = False
        if (
            limits
            and trade.get("POS_HOLD_STATUS") == "OPEN"
            and trade.get("REC_STATUS") == "OPEN"
        ):
            limit_price = order_limit_price_for_check(trade)
            if limit_price is not None:
                enriched["CIRCUIT_LIMIT_OUT_OF_BAND"] = limit_price_out_of_circuit(
                    limit_price,
                    str(trade.get("BUY_SELL") or "BUY"),
                    limits["upper"],
                    limits["lower"],
                )
        return enriched

    def _download_paytm_security_master(self, force: bool = False) -> dict[str, Path]:
        dataset_root = self.__root / "dataset"
        return {
            "NSE": dataset_root / "nse_security_master.csv",
            "BSE": dataset_root / "bse_security_master.csv",
        }

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
        self._init_circuit_cache(preload=True)
        self._invalidate()
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
        return [{"id": encode_trade_id(r), "trade": self._enrich_circuit_fields(r)} for r in filtered]

    def get_trade(self, trade_id):
        query = decode_trade_id(trade_id)
        found, doc = self.__store.isInDb(query)
        if not found:
            return None
        return {"id": trade_id, "trade": self._enrich_circuit_fields(doc)}

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
        provided_sec = str(doc.get("SECURITY_ID") or "").strip()
        if not provided_sec:
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
            # SECURITY_ID was provided by the client - ensure it matches the requested MKT_SYMBOL
            ok, sec_id, icici, mkt_sym, mkt = self._resolve_symbol(
                doc["MKT_SYMBOL"],
                product=doc.get("PRODUCT", "CASH"),
                mkt=doc.get("MKT", "NSE"),
            )
            if not ok:
                raise ValidationError(
                    [
                        {"field": "MKT_SYMBOL", "message": f"Unknown symbol '{doc['MKT_SYMBOL']}'."}
                    ]
                )
            if str(sec_id) != provided_sec:
                raise ValidationError(
                    [
                        {
                            "field": "SECURITY_ID",
                            "message": (
                                "SECURITY_ID does not match MKT_SYMBOL. "
                                "Clear SECURITY_ID or select the symbol from lookup to populate the correct id."
                            ),
                        }
                    ]
                )
            doc["SECURITY_ID"] = provided_sec
            doc["ICICI_SYMBOL"] = icici
            doc["MKT_SYMBOL"] = mkt_sym
            doc["MKT"] = mkt
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
            doc = apply_held_qty_to_trade(doc, doc["QTY"])
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

    def preview_adjust_held_qty(self, trade_id: str, pos_hold_qty: int):
        current = self.get_trade(trade_id)
        if not current:
            return None
        return preview_held_qty_adjustment(current["trade"], pos_hold_qty)

    def adjust_held_qty(self, trade_id: str, pos_hold_qty: int):
        self._backup()
        current = self.get_trade(trade_id)
        if not current:
            return None
        existing = current["trade"]
        if existing.get("REC_STATUS") == "CLOSE":
            raise ValidationError(
                [{"field": "REC_STATUS", "message": "Cannot adjust held qty on a closed recommendation"}]
            )
        merged = apply_held_qty_to_trade(existing, pos_hold_qty)
        query = decode_trade_id(trade_id)
        if not self.__store.updateDb(merged, query):
            return None
        self._invalidate()
        return self.get_trade(trade_id)
