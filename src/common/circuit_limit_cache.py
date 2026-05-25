"""In-memory Paytm security-master circuit limits (upper/lower) with lazy CSV load."""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any


def _parse_float(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip().strip('"')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def round_to_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(price / tick) * tick


def limit_price_out_of_circuit(
    limit_price: float,
    buy_sell: str,
    upper: float,
    lower: float,
) -> bool:
    """True if limit_price is outside exchange circuit band (before clamping)."""
    side = buy_sell.upper()
    if side == "BUY":
        return limit_price > upper or limit_price < lower
    return limit_price < lower or limit_price > upper


def order_limit_price_for_check(trade: dict[str, Any]) -> float | None:
    """Limit price used when opening a position (mirrors workflow.__getQtyLimitPrice)."""
    buy_sell = str(trade.get("BUY_SELL") or "BUY").upper()
    key = "HIGH_REC_PRICE" if buy_sell == "BUY" else "LOW_REC_PRICE"
    return _parse_float(trade.get(key))


def clamp_limit_to_circuit(
    limit_price: float,
    buy_sell: str,
    upper: float,
    lower: float,
    tick: float,
) -> float:
    """
    Clamp a limit order price into [lower, upper].
    When hitting the circuit band, use the exact upper/lower from the security master.
    Tick rounding applies only for prices still inside the band.
    """
    side = buy_sell.upper()
    if side == "BUY":
        if limit_price > upper:
            return round(upper, 4)
        if limit_price < lower:
            return round(lower, 4)
        clamped = limit_price
    else:
        if limit_price < lower:
            return round(lower, 4)
        if limit_price > upper:
            return round(upper, 4)
        clamped = limit_price

    if tick > 0:
        clamped = round_to_tick(clamped, tick)
        clamped = min(clamped, upper)
        clamped = max(clamped, lower)
    return round(clamped, 4)


class CircuitLimitCache:
    def __init__(
        self,
        *,
        nse_csv: Path | str,
        bse_csv: Path | str,
        logger: logging.Logger | None = None,
    ) -> None:
        self._paths = {
            "NSE": Path(nse_csv).resolve(),
            "BSE": Path(bse_csv).resolve(),
        }
        self._logger = logger or logging.getLogger(__name__)
        self._limits: dict[tuple[str, str], dict[str, float]] = {}
        self._exchange_loaded: set[str] = set()
        self._clamp_logged: set[tuple[str, str, str]] = set()
        self._missing_logged: set[str] = set()

    def preload_active_recs(self, db_dicts: list[dict[str, Any]]) -> None:
        for db_dict in db_dicts:
            security_id = str(db_dict.get("SECURITY_ID") or "").strip()
            exchange = str(db_dict.get("MKT") or "NSE").strip().upper()
            if not security_id:
                continue
            self.get_limits(security_id, exchange)

    def get_limits(self, security_id: str, exchange: str) -> dict[str, float] | None:
        security_id = str(security_id).strip()
        exchange = str(exchange or "NSE").strip().upper()
        if not security_id:
            return None
        key = (security_id, exchange)
        if key in self._limits:
            return self._limits[key]
        self._load_exchange(exchange)
        return self._limits.get(key)

    def clamp_for_open_order(
        self,
        db_dict: dict[str, Any],
        limit_price: float,
        buy_sell: str,
    ) -> float:
        security_id = str(db_dict.get("SECURITY_ID") or "").strip()
        exchange = str(db_dict.get("MKT") or "NSE").strip().upper()
        if not security_id:
            self._log_missing_once(
                security_id or "(empty)",
                db_dict,
                "SECURITY_ID missing; placing limit without circuit clamp",
            )
            return limit_price

        limits = self.get_limits(security_id, exchange)
        if limits is None:
            self._log_missing_once(
                security_id,
                db_dict,
                f"Circuit limits not found for security_id={security_id} exchange={exchange}; "
                "placing limit without circuit clamp",
            )
            return limit_price

        clamped = clamp_limit_to_circuit(
            limit_price,
            buy_sell,
            limits["upper"],
            limits["lower"],
            limits["tick"],
        )
        if abs(clamped - limit_price) > 1e-6:
            trade_key = (
                db_dict["MKT_SYMBOL"],
                db_dict["REC_DATE"],
                db_dict["REC_TIME"],
            )
            if trade_key not in self._clamp_logged:
                self._clamp_logged.add(trade_key)
                self._logger.warning(
                    "Circuit clamp %s %s-%s-%s-%s: limit %.4f -> %.4f "
                    "(band %.4f - %.4f, tick %.4f)",
                    buy_sell,
                    db_dict["MKT_SYMBOL"],
                    db_dict["STRATEGY"],
                    db_dict["REC_DATE"],
                    db_dict["REC_TIME"],
                    limit_price,
                    clamped,
                    limits["lower"],
                    limits["upper"],
                    limits["tick"],
                )
        return clamped

    def _log_missing_once(
        self,
        security_id: str,
        db_dict: dict[str, Any],
        message: str,
    ) -> None:
        log_key = f"{security_id}:{db_dict.get('MKT', 'NSE')}"
        if log_key in self._missing_logged:
            return
        self._missing_logged.add(log_key)
        self._logger.warning(
            "%s (%s-%s-%s-%s)",
            message,
            db_dict.get("MKT_SYMBOL"),
            db_dict.get("STRATEGY"),
            db_dict.get("REC_DATE"),
            db_dict.get("REC_TIME"),
        )

    def _load_exchange(self, exchange: str) -> None:
        exchange = exchange.upper()
        if exchange in self._exchange_loaded:
            return
        self._exchange_loaded.add(exchange)
        path = self._paths.get(exchange)
        if path is None or not path.is_file():
            self._logger.warning(
                "Paytm security master for %s not found at %s",
                exchange,
                path,
            )
            return
        loaded = 0
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row_exchange = (row.get("exchange") or "").strip().upper()
                if row_exchange != exchange:
                    continue
                security_id = (row.get("security_id") or "").strip().strip('"')
                if not security_id:
                    continue
                upper = _parse_float(row.get("upper_limit"))
                lower = _parse_float(row.get("lower_limit"))
                if upper is None or lower is None:
                    continue
                tick = _parse_float(row.get("tick_size")) or 0.05
                self._limits[(security_id, exchange)] = {
                    "upper": upper,
                    "lower": lower,
                    "tick": tick,
                }
                loaded += 1
        self._logger.info(
            "Loaded %d circuit limit rows for %s from %s",
            loaded,
            exchange,
            path,
        )
