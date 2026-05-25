import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trade_manager.validation import ValidationError, validate_trade_payload  # noqa: E402


def test_buy_band_rules():
    validate_trade_payload(
        {
            "LOW_REC_PRICE": 100,
            "HIGH_REC_PRICE": 105,
            "TARGET": 120,
            "STOP_LOSS": 95,
            "BUY_SELL": "BUY",
        }
    )


def test_buy_stop_above_high_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_trade_payload(
            {
                "LOW_REC_PRICE": 100,
                "HIGH_REC_PRICE": 105,
                "TARGET": 120,
                "STOP_LOSS": 110,
                "BUY_SELL": "BUY",
            }
        )
    assert any(e["field"] == "STOP_LOSS" for e in exc.value.errors)


def test_qty_below_pos_hold_rejected():
    with pytest.raises(ValidationError):
        validate_trade_payload(
            {"QTY": 2},
            existing={"POS_HOLD_QTY": 5, "BUY_SELL": "BUY", "LOW_REC_PRICE": 1, "HIGH_REC_PRICE": 2, "TARGET": 10, "STOP_LOSS": 0.5},
        )
