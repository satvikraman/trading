from typing import Any


class ValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))


def _err(field, message):
    return {"field": field, "message": message}


def validate_trade_payload(payload: dict, existing: dict | None = None, is_create=False):
    errors = []
    buy_sell = (payload.get("BUY_SELL") or (existing or {}).get("BUY_SELL") or "BUY").upper()

    for field in ("MKT_SYMBOL", "SOURCE", "STRATEGY", "REC_DATE", "REC_TIME"):
        if is_create and not payload.get(field):
            errors.append(_err(field, "Required"))

    try:
        low = float(payload.get("LOW_REC_PRICE", (existing or {}).get("LOW_REC_PRICE")))
        high = float(payload.get("HIGH_REC_PRICE", (existing or {}).get("HIGH_REC_PRICE")))
        target = float(payload.get("TARGET", (existing or {}).get("TARGET")))
        stop = float(payload.get("STOP_LOSS", (existing or {}).get("STOP_LOSS")))
    except (TypeError, ValueError):
        errors.append(_err("prices", "Prices must be numeric"))
        raise ValidationError(errors)

    if low <= 0 or high <= 0:
        errors.append(_err("LOW_REC_PRICE", "Prices must be positive"))
    if low > high:
        errors.append(_err("LOW_REC_PRICE", "LOW_REC_PRICE must be <= HIGH_REC_PRICE"))

    if buy_sell == "BUY":
        if stop >= high:
            errors.append(_err("STOP_LOSS", "BUY stop loss must be below HIGH_REC_PRICE"))
        if target <= high:
            errors.append(_err("TARGET", "BUY target must be above HIGH_REC_PRICE"))
    else:
        if stop <= low:
            errors.append(_err("STOP_LOSS", "SELL stop loss must be above LOW_REC_PRICE"))
        if target >= low:
            errors.append(_err("TARGET", "SELL target must be below LOW_REC_PRICE"))

    if "QTY" in payload:
        try:
            qty = int(payload["QTY"])
            if qty <= 0:
                errors.append(_err("QTY", "QTY must be a positive integer"))
            if existing and qty < int(existing.get("POS_HOLD_QTY", 0)):
                errors.append(_err("QTY", "QTY cannot be less than POS_HOLD_QTY already held"))
        except (TypeError, ValueError):
            errors.append(_err("QTY", "QTY must be an integer"))

    if errors:
        raise ValidationError(errors)

    return {
        "LOW_REC_PRICE": low,
        "HIGH_REC_PRICE": high,
        "TARGET": target,
        "STOP_LOSS": stop,
    }
