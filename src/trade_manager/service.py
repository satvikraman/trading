import configparser
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

from trade_manager.trade_id import decode_trade_id, encode_trade_id  # noqa: E402
from trade_manager.validation import ValidationError, validate_trade_payload  # noqa: E402


class TradeService:
    def __init__(self, config_path=None):
        root = Path(__file__).resolve().parents[2]
        config_path = config_path or root / "src/paytm/payTmMoney.ini"
        self.__config = configparser.ConfigParser()
        self.__config.read(config_path)
        self.__logger = logging.getLogger(__name__)
        db = self.__config["DATABASE"]["DB_EQUITY"]
        if not os.path.isabs(db):
            db = str(root / db)
        self.__store = persistence(self.__logger, db)
        self.__cache = {"data": None, "ts": 0.0}
        self.__ttl = 10.0
        mapper = MapIciciToNseStock(
            str(root / "dataset/NSEScripMaster.txt"),
            str(root / "dataset/BSEScripMaster.txt"),
            str(root / "dataset/FONSEScripMaster.txt"),
        )
        self.__mapper = mapper

    def _backup(self):
        db = self.__config["DATABASE"]["DB_EQUITY"]
        root = Path(__file__).resolve().parents[2]
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
        path = Path(__file__).resolve().parents[2] / "dataset" / "NSEScripMaster.txt"
        results = []
        if not path.exists():
            return results
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                sym = parts[2].strip().strip('"')
                if q in sym.upper():
                    results.append(sym)
                    if len(results) >= limit:
                        break
        out = []
        for sym in results:
            ok, sec_id, icici, mkt_sym, mkt, lot, product = self.__mapper.mapICICSymbolToMktSymbol(
                sym, sym, "CASH", "NSE"
            )
            if ok:
                out.append(
                    {
                        "MKT_SYMBOL": mkt_sym,
                        "SECURITY_ID": sec_id,
                        "ICICI_SYMBOL": icici,
                        "MKT": mkt,
                        "STOCK": sym,
                    }
                )
        return out

    def create_trade(self, payload):
        self._backup()
        validate_trade_payload(payload.model_dump(), is_create=True)
        doc = payload.model_dump()
        if not doc.get("SECURITY_ID"):
            ok, sec_id, icici, mkt_sym, mkt, lot, product = self.__mapper.mapICICSymbolToMktSymbol(
                doc["MKT_SYMBOL"], doc["MKT_SYMBOL"], doc["PRODUCT"], doc["MKT"]
            )
            if not ok:
                raise ValidationError([{"field": "MKT_SYMBOL", "message": "Unknown symbol"}])
            doc["SECURITY_ID"] = sec_id
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
