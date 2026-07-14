import configparser
import logging
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "common"))

import pytest  # noqa: E402

from common.workflow import Workflow  # noqa: E402
from trade_manager.service import TradeService  # noqa: E402
from trade_manager.trade_id import decode_trade_id, encode_trade_id  # noqa: E402
from trade_manager.validation import ValidationError  # noqa: E402


@pytest.fixture
def service():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    ini_path = Path(tmp) / "test.ini"
    cfg = configparser.ConfigParser()
    cfg["DATABASE"] = {"DB_EQUITY": str(db_path)}
    cfg["DATASET"] = {
        "ICICI_DATASET": "https://example.invalid/SecurityMaster.zip",
        "NSE_DATASET": str(ROOT / "dataset" / "NSEScripMaster.txt"),
        "BSE_DATASET": str(ROOT / "dataset" / "BSEScripMaster.txt"),
        "FNO_DATASET": str(ROOT / "dataset" / "FONSEScripMaster.txt"),
    }
    with open(ini_path, "w") as f:
        cfg.write(f)
    return TradeService(config_path=ini_path, refresh_dataset=False)


def _leg(i, rec_time=None, product="CASH", open_orders=None, **overrides):
    doc = {
        "MKT_SYMBOL": "TESTSYM",
        "STOCK": "TESTSYM",
        "SOURCE": "MANUAL",
        "STRATEGY": f"LEG{i}",
        "PRODUCT": product,
        "BUY_SELL": "BUY",
        "MKT": "NSE",
        "REC_DATE": "01-Jan-2024",
        "REC_TIME": rec_time if rec_time else f"10:{i:02d}",
        "EXP_DATE": "01-Jan-2024",
        "LOW_REC_PRICE": 90.0,
        "HIGH_REC_PRICE": 100.0,
        "TARGET": 120.0,
        "STOP_LOSS": 80.0,
        "QTY": 100,
        "SECURITY_ID": "SEC123",
        "ICICI_SYMBOL": "TESTSYM",
        "REC_STATUS": "OPEN",
        "VISIBLE": "VISIBLE",
        "POS_QTY": 0,
        "HOLD_QTY": 100,
        "POS_DATE": "01-Jan-2024",
        "OPEN_ORDERS": open_orders if open_orders is not None else [],
        "CLOSE_ORDERS": [],
        "LATE_ADD": False,
        "POS_HOLD_STATUS": "POSITION",
        "POS_HOLD_QTY": 100,
    }
    doc.update(overrides)
    return doc


def _insert_legs(store, docs):
    for d in docs:
        assert store.insertDb(d, None)
    return [encode_trade_id(d) for d in docs]


def test_aggregated_close_collapses_bucket_into_single_record(service):
    store = service._TradeService__store
    docs = [_leg(i) for i in range(10)]
    ids = _insert_legs(store, docs)

    result = service.close_portfolio_bucket(ids, total_qty=1000)

    assert result["member_count"] == 10
    assert result["total_qty"] == 1000
    assert result["security_id"] == "SEC123"

    rows = store.getDb([])
    # Only the aggregated record remains (original legs deleted in the same call).
    assert len(rows) == 1
    agg = rows[0]
    assert agg["REC_STATUS"] == "CLOSE"
    assert agg["POS_HOLD_STATUS"] == "POSITION"
    assert agg["POS_HOLD_QTY"] == 1000
    assert agg["QTY"] == 1000

    for mid in ids:
        found, _ = store.isInDb(decode_trade_id(mid))
        assert not found, f"leg {mid} was not deleted"


def test_aggregated_rec_time_is_real_and_unique(service):
    store = service._TradeService__store
    docs = [_leg(i) for i in range(10)]
    ids = _insert_legs(store, docs)

    result = service.close_portfolio_bucket(ids, total_qty=1000)
    agg = service.get_trade(result["agg_trade_id"])["trade"]

    assert re.match(r"^\d{2}:\d{2}$", agg["REC_TIME"]), agg["REC_TIME"]
    assert agg["REC_TIME"] != "xx:xx"

    key = (agg["MKT_SYMBOL"], agg["STRATEGY"], agg["REC_DATE"], agg["REC_TIME"])
    tuples = [
        (r["MKT_SYMBOL"], r["STRATEGY"], r["REC_DATE"], r["REC_TIME"])
        for r in store.getDb([])
    ]
    assert tuples.count(key) == 1


def test_leg_with_xx_xx_rec_time_is_deleted(service):
    store = service._TradeService__store
    docs = [_leg(i) for i in range(9)]
    docs.append(_leg(9, rec_time="xx:xx"))
    ids = _insert_legs(store, docs)

    service.close_portfolio_bucket(ids, total_qty=1000)

    for mid in ids:
        found, _ = store.isInDb(decode_trade_id(mid))
        assert not found, f"leg {mid} with REC_TIME was not deleted"


def test_negative_mixed_product_rejected(service):
    store = service._TradeService__store
    docs = [_leg(0), _leg(1, product="OPTION")]
    ids = _insert_legs(store, docs)

    with pytest.raises(ValidationError):
        service.close_portfolio_bucket(ids, total_qty=200)

    # Nothing mutated: both legs still present.
    assert len(store.getDb([])) == 2


def test_negative_pending_open_buy_rejected(service):
    store = service._TradeService__store
    pending = [
        {
            "ORDER_NO": "O1",
            "ORDER_STATUS": "OPEN",
            "TRADED_QTY": 0,
            "QTY": 10,
        }
    ]
    docs = [_leg(0), _leg(1, open_orders=pending)]
    ids = _insert_legs(store, docs)

    with pytest.raises(ValidationError):
        service.close_portfolio_bucket(ids, total_qty=200)

    assert len(store.getDb([])) == 2


def test_negative_unknown_member_rejected(service):
    missing = encode_trade_id(
        {
            "SOURCE": "GHOST",
            "MKT_SYMBOL": "NOPE",
            "STRATEGY": "X",
            "REC_DATE": "01-Jan-2024",
            "REC_TIME": "09:30",
        }
    )
    with pytest.raises(ValidationError):
        service.close_portfolio_bucket([missing], total_qty=100)


def test_reconcile_places_single_sell_order_for_aggregated_record(service):
    store = service._TradeService__store
    docs = [_leg(i) for i in range(10)]
    ids = _insert_legs(store, docs)

    result = service.close_portfolio_bucket(ids, total_qty=1000)
    agg = service.get_trade(result["agg_trade_id"])["trade"]

    class FakeParent:
        def __init__(self, security_id):
            self.calls = []
            self.cmp = {security_id: {"LTP": 100}}
            self.marketOpen = True

        def placeOrder(self, dbDict, qty, buySell, orderType, limitPrice, triggerPrice=None):
            self.calls.append((qty, buySell, orderType))
            return True, "ok", f"ORD{len(self.calls)}"

        def findOrderStatusAndQtyInfo(self, dbDict, orderNum):
            return True, 1000, 1000

    parent = FakeParent(agg["SECURITY_ID"])
    wf = Workflow(parent, logging.getLogger("test"))
    fake_store = type("S", (), {"updateDb": lambda *a, **k: True})()

    status, out, order_num = wf._Workflow__closePosition(fake_store, dict(agg), partial=False)

    # Exactly one SELL market order for the full combined quantity.
    assert len(parent.calls) == 1
    qty, buy_sell, order_type = parent.calls[0]
    assert qty == 1000
    assert buy_sell == "SELL"
    assert order_type == "MKT"

    assert len(out["CLOSE_ORDERS"]) == 1
    assert out["CLOSE_ORDERS"][0]["QTY"] == 1000

    # Simulate the broker fill: order completes, position recomputes to CLOSE.
    out["CLOSE_ORDERS"][0]["ORDER_STATUS"] = "CLOSE"
    out["CLOSE_ORDERS"][0]["TRADED_QTY"] = 1000
    out = wf._Workflow__getPosStatus(out)
    assert out["POS_HOLD_STATUS"] == "CLOSE"
    assert out["POS_HOLD_QTY"] == 0
