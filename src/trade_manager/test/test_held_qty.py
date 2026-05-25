import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from trade_manager.service import apply_held_qty_to_trade  # noqa: E402
from trade_manager.validation import ValidationError  # noqa: E402


def _base(qty=112, **overrides):
    doc = {
        "QTY": qty,
        "BUY_SELL": "BUY",
        "HIGH_REC_PRICE": 100.0,
        "REC_STATUS": "OPEN",
        "POS_HOLD_STATUS": "OPEN",
        "POS_HOLD_QTY": 0,
        "HOLD_QTY": 0,
        "POS_QTY": 5,
        "OPEN_ORDERS": [],
        "CLOSE_ORDERS": [],
    }
    doc.update(overrides)
    return doc


def test_held_zero_from_zero_keeps_open():
    out = apply_held_qty_to_trade(_base(), 0)
    assert out["POS_HOLD_STATUS"] == "OPEN"
    assert out["REC_STATUS"] == "OPEN"
    assert out["POS_HOLD_QTY"] == 0
    assert out["OPEN_ORDERS"] == []
    assert out["CLOSE_ORDERS"] == []


def test_held_zero_from_zero_position_becomes_open():
    out = apply_held_qty_to_trade(
        _base(POS_HOLD_STATUS="POSITION", ACTION="INIT_TRADE", POS_HOLD_QTY=0),
        0,
    )
    assert out["POS_HOLD_STATUS"] == "OPEN"
    assert "ACTION" not in out
    assert out["OPEN_ORDERS"] == []


def test_held_zero_from_zero_close_stays_close():
    out = apply_held_qty_to_trade(
        _base(POS_HOLD_STATUS="CLOSE", REC_STATUS="OPEN"),
        0,
    )
    assert out["POS_HOLD_STATUS"] == "CLOSE"
    assert out["REC_STATUS"] == "OPEN"


def test_held_zero_from_positive_closes_position_and_rec():
    stale = [{"ORDER_NO": "1", "ORDER_STATUS": "OPEN", "TRADED_QTY": 0, "QTY": 10}]
    out = apply_held_qty_to_trade(
        _base(POS_HOLD_QTY=10, HOLD_QTY=10, OPEN_ORDERS=stale),
        0,
    )
    assert out["POS_HOLD_STATUS"] == "CLOSE"
    assert out["REC_STATUS"] == "CLOSE"
    assert out["OPEN_ORDERS"] == []
    assert out["CLOSE_ORDERS"] == []


def test_held_positive_rejected_when_pos_hold_close():
    with pytest.raises(ValidationError):
        apply_held_qty_to_trade(_base(POS_HOLD_STATUS="CLOSE"), 10)


def test_held_full_position():
    out = apply_held_qty_to_trade(_base(112), 112)
    assert out["POS_HOLD_STATUS"] == "POSITION"
    assert out["HOLD_QTY"] == 112
    assert out["POS_QTY"] == 0
    assert out["ACTION"] == "INIT_TRADE"
    assert len(out["OPEN_ORDERS"]) == 1
    assert out["OPEN_ORDERS"][0]["TRADED_QTY"] == 112


def test_held_partial_open():
    out = apply_held_qty_to_trade(_base(112), 100)
    assert out["POS_HOLD_STATUS"] == "OPEN"
    assert out["HOLD_QTY"] == 100
    assert out["POS_QTY"] == 0
    assert out["OPEN_ORDERS"] == []


def test_held_exceeds_qty_rejected():
    with pytest.raises(ValidationError):
        apply_held_qty_to_trade(_base(112), 113)
