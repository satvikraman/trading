import logging
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from sqlite_persistence import SqlitePersistence  # noqa: E402


def _q(**kwargs):
    return list(kwargs.items())


@pytest.fixture
def store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    p = SqlitePersistence(logging.getLogger("test_sqlite"), path)
    yield p
    p.removeAll()
    Path(path).unlink(missing_ok=True)


def test_insert_get_update(store):
    doc = {
        "SOURCE": "MANUAL",
        "MKT_SYMBOL": "RELIANCE",
        "STRATEGY": "TEST",
        "REC_DATE": "01-Jan-2026",
        "REC_TIME": "10:00",
        "QTY": 10,
        "OPEN_ORDERS": [{"ORDER_NO": "1"}],
        "CLOSE_ORDERS": [],
    }
    assert store.insertDb(doc, None) is True
    found, row = store.isInDb(
        _q(
            SOURCE="MANUAL",
            MKT_SYMBOL="RELIANCE",
            STRATEGY="TEST",
            REC_DATE="01-Jan-2026",
            REC_TIME="10:00",
        )
    )
    assert found
    assert row["QTY"] == 10
    assert isinstance(row["OPEN_ORDERS"], list)
    assert row["OPEN_ORDERS"][0]["ORDER_NO"] == "1"

    row["QTY"] = 12
    assert store.updateDb(
        row,
        _q(
            SOURCE="MANUAL",
            MKT_SYMBOL="RELIANCE",
            STRATEGY="TEST",
            REC_DATE="01-Jan-2026",
            REC_TIME="10:00",
        ),
    )
    rows = store.getDb([])
    assert rows[0]["QTY"] == 12


def test_duplicate_key_rejected(store):
    doc = {
        "SOURCE": "X",
        "MKT_SYMBOL": "ABC",
        "STRATEGY": "S",
        "REC_DATE": "01-Jan-2026",
        "REC_TIME": "xx:xx",
    }
    assert store.insertDb(doc, None) is True
    assert store.insertDb(doc, None) is False
