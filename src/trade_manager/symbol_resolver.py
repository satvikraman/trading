"""Resolve NSE/BSE symbols to Paytm SECURITY_ID (bare token) via NSEScripMaster."""
from __future__ import annotations

import csv
from pathlib import Path


def _normalize_security_id(security_id: str) -> str:
    """Paytm uses bare numeric tokens; strip market prefixes if present."""
    if not security_id:
        return ""
    sid = str(security_id).strip()
    if "!" in sid:
        return sid.rsplit("!", 1)[-1]
    return sid


def _lookup_nse_exchange_code(nse_master_path: Path, mkt_symbol: str) -> dict | None:
    """Match NSEScripMaster by ExchangeCode; prefer EQ series when duplicated."""
    sym = mkt_symbol.strip().upper()
    if not sym or not nse_master_path.is_file():
        return None

    eq_match = None
    any_match = None
    with open(nse_master_path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values = [v.strip().strip('"') for v in row.values()]
            if len(values) < 4:
                continue
            token, _short, series = values[0], values[1], values[2]
            exchange_code = values[-1]
            if exchange_code.upper() != sym:
                continue
            hit = {
                "SECURITY_ID": token,
                "MKT_SYMBOL": exchange_code,
                "MKT": "NSE",
                "ICICI_SYMBOL": _short or exchange_code,
                "STOCK": exchange_code,
            }
            if series.upper() == "EQ":
                eq_match = hit
                break
            if any_match is None:
                any_match = hit
    return eq_match or any_match


def resolve_symbol(
    mapper,
    store,
    mkt_symbol: str,
    *,
    product: str = "CASH",
    mkt: str = "NSE",
    security_id: str | None = None,
    nse_master_path: Path | None = None,
) -> tuple[bool, str, str, str, str]:
    """
    Returns: ok, security_id, icici_symbol, mkt_symbol, mkt
    """
    sym = (mkt_symbol or "").strip().upper()
    if not sym:
        return False, "", "", "", mkt

    if security_id:
        sid = _normalize_security_id(security_id)
        return bool(sid), sid, sym, sym, mkt

    ok, sec_id, icici, mkt_sym, mkt_out, _lot, _product = mapper.mapICICSymbolToMktSymbol(
        sym, sym, product, mkt
    )
    if ok and sec_id:
        return True, _normalize_security_id(sec_id), icici or sym, mkt_sym or sym, mkt_out or mkt

    root = Path(__file__).resolve().parents[2]
    nse_path = nse_master_path or (root / "dataset" / "NSEScripMaster.txt")
    nse_hit = _lookup_nse_exchange_code(nse_path, sym)
    if nse_hit:
        return (
            True,
            nse_hit["SECURITY_ID"],
            nse_hit["ICICI_SYMBOL"],
            nse_hit["MKT_SYMBOL"],
            nse_hit["MKT"],
        )

    if store is not None:
        for row in store.getDb([]):
            if (row.get("MKT_SYMBOL") or "").upper() != sym:
                continue
            sid = _normalize_security_id(row.get("SECURITY_ID") or "")
            if sid:
                return (
                    True,
                    sid,
                    row.get("ICICI_SYMBOL") or sym,
                    row["MKT_SYMBOL"],
                    row.get("MKT", mkt),
                )

    return False, "", "", sym, mkt
