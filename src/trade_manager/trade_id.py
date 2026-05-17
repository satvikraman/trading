import base64
import json


def encode_trade_id(doc):
    key = {
        "SOURCE": doc["SOURCE"],
        "MKT_SYMBOL": doc["MKT_SYMBOL"],
        "STRATEGY": doc["STRATEGY"],
        "REC_DATE": doc["REC_DATE"],
        "REC_TIME": doc["REC_TIME"],
    }
    raw = json.dumps(key, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_trade_id(trade_id):
    pad = "=" * (-len(trade_id) % 4)
    raw = base64.urlsafe_b64decode(trade_id + pad)
    key = json.loads(raw.decode("utf-8"))
    return [
        ["SOURCE", key["SOURCE"]],
        ["MKT_SYMBOL", key["MKT_SYMBOL"]],
        ["STRATEGY", key["STRATEGY"]],
        ["REC_DATE", key["REC_DATE"]],
        ["REC_TIME", key["REC_TIME"]],
    ]
