import json
import re
import sqlite3
import threading
from pathlib import Path


class SqlitePersistence:
    """SQLite backend with the same API as TinyDB persistence for workflow compatibility."""

    _INIT_SQL = """
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        mkt_symbol TEXT NOT NULL,
        strategy TEXT NOT NULL,
        rec_date TEXT NOT NULL,
        rec_time TEXT NOT NULL,
        product TEXT,
        rec_status TEXT,
        pos_hold_status TEXT,
        security_id TEXT,
        visible TEXT,
        data TEXT NOT NULL,
        UNIQUE(source, mkt_symbol, strategy, rec_date, rec_time)
    );
    CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source);
    CREATE INDEX IF NOT EXISTS idx_trades_rec_status ON trades(rec_status);
    CREATE INDEX IF NOT EXISTS idx_trades_pos_hold_status ON trades(pos_hold_status);
    CREATE INDEX IF NOT EXISTS idx_trades_mkt_symbol ON trades(mkt_symbol);
    """

    def __init__(self, logger, db_path):
        self.__logger = logger
        self.__db_path = str(db_path)
        self.__lock = threading.Lock()
        Path(self.__db_path).parent.mkdir(parents=True, exist_ok=True)
        self.__conn = sqlite3.connect(self.__db_path, check_same_thread=False)
        self.__conn.row_factory = sqlite3.Row
        self.__conn.execute("PRAGMA journal_mode=WAL")
        self.__conn.execute("PRAGMA busy_timeout=5000")
        self.__conn.executescript(self._INIT_SQL)
        self.__conn.commit()

    def __row_to_dict(self, row):
        if row is None:
            return {}
        return json.loads(row["data"])

    def __extract_index_fields(self, doc):
        return {
            "source": doc.get("SOURCE", ""),
            "mkt_symbol": doc.get("MKT_SYMBOL", ""),
            "strategy": doc.get("STRATEGY", ""),
            "rec_date": doc.get("REC_DATE", ""),
            "rec_time": doc.get("REC_TIME", ""),
            "product": doc.get("PRODUCT", ""),
            "rec_status": doc.get("REC_STATUS", ""),
            "pos_hold_status": doc.get("POS_HOLD_STATUS", ""),
            "security_id": str(doc.get("SECURITY_ID", "")),
            "visible": doc.get("VISIBLE", ""),
        }

    def __build_where(self, query_param_vals):
        clauses = []
        params = []
        for keyword, val in query_param_vals:
            inverse = False
            if "!" in val:
                inverse = True
                val = re.sub(r"!", "", val)

            col = keyword.lower()
            if "|" in val:
                parts = val.split("|")
                placeholders = ",".join("?" * len(parts))
                op = "NOT IN" if inverse else "IN"
                clauses.append(f"{col} {op} ({placeholders})")
                params.extend(parts)
            elif "&&" in val:
                parts = val.split("&&")
                for part in parts:
                    clauses.append(f"{col} != ?" if inverse else f"{col} = ?")
                    params.append(part)
            else:
                clauses.append(f"{col} != ?" if inverse else f"{col} = ?")
                params.append(val)
        where = " AND ".join(clauses) if clauses else "1=1"
        return where, params

    def getDb(self, query_param_vals):
        with self.__lock:
            where, params = self.__build_where(query_param_vals)
            cur = self.__conn.execute(f"SELECT data FROM trades WHERE {where}", params)
            return [self.__row_to_dict(row) for row in cur.fetchall()]

    def insertDb(self, doc, query_param_vals):
        if query_param_vals is not None:
            found, _ = self.isInDb(query_param_vals)
            if found:
                self.__logger.error("Record already in DB. Can't insert: %s", doc)
                return False
        if not doc:
            return False
        idx = self.__extract_index_fields(doc)
        payload = json.dumps(doc, separators=(",", ":"))
        try:
            with self.__lock:
                self.__conn.execute(
                    """
                    INSERT INTO trades (
                        source, mkt_symbol, strategy, rec_date, rec_time,
                        product, rec_status, pos_hold_status, security_id, visible, data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idx["source"],
                        idx["mkt_symbol"],
                        idx["strategy"],
                        idx["rec_date"],
                        idx["rec_time"],
                        idx["product"],
                        idx["rec_status"],
                        idx["pos_hold_status"],
                        idx["security_id"],
                        idx["visible"],
                        payload,
                    ),
                )
                self.__conn.commit()
            return True
        except sqlite3.IntegrityError:
            if self.__logger:
                self.__logger.error("Duplicate key on insert: %s", doc)
            return False

    def updateDb(self, doc, query_param_vals):
        existing = self.getDb(query_param_vals)
        if not existing:
            return False
        merged = {**existing[0], **doc}
        idx = self.__extract_index_fields(merged)
        payload = json.dumps(merged, separators=(",", ":"))
        where, params = self.__build_where(query_param_vals)
        with self.__lock:
            cur = self.__conn.execute(
                f"""
                UPDATE trades SET
                    source=?, mkt_symbol=?, strategy=?, rec_date=?, rec_time=?,
                    product=?, rec_status=?, pos_hold_status=?, security_id=?, visible=?, data=?
                WHERE {where}
                """,
                (
                    idx["source"],
                    idx["mkt_symbol"],
                    idx["strategy"],
                    idx["rec_date"],
                    idx["rec_time"],
                    idx["product"],
                    idx["rec_status"],
                    idx["pos_hold_status"],
                    idx["security_id"],
                    idx["visible"],
                    payload,
                    *params,
                ),
            )
            self.__conn.commit()
            return cur.rowcount > 0

    def removeKeyFromDb(self, key, query_param_vals):
        rows = self.getDb(query_param_vals)
        for row in rows:
            if key in row:
                del row[key]
                self.updateDb(row, query_param_vals)

    def removeFromDb(self, query_param_vals):
        where, params = self.__build_where(query_param_vals)
        with self.__lock:
            self.__conn.execute(f"DELETE FROM trades WHERE {where}", params)
            self.__conn.commit()

    def isInDb(self, query_param_vals):
        rows = self.getDb(query_param_vals)
        if len(rows) == 1:
            return True, rows[0]
        return False, {}

    def removeAll(self):
        with self.__lock:
            self.__conn.execute("DELETE FROM trades")
            self.__conn.commit()

    def close(self):
        with self.__lock:
            self.__conn.close()
