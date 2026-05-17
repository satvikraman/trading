import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .models import TradeCreate, TradePatch
from .service import TradeService
from .validation import ValidationError

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Paytm Trade Manager", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = TradeService()


def _validation_http(exc: ValidationError):
    raise HTTPException(status_code=422, detail={"errors": exc.errors})


@app.get("/api/trades")
def list_trades(
    source: str | None = None,
    rec_status: str | None = None,
    pos_hold_status: str | None = None,
    mkt_symbol: str | None = None,
    active_only: bool = False,
):
    return service.list_trades(source, rec_status, pos_hold_status, mkt_symbol, active_only)


@app.get("/api/trades/{trade_id}")
def get_trade(trade_id: str):
    row = service.get_trade(trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@app.get("/api/sources")
def list_sources():
    return service.list_sources()


@app.get("/api/symbols/lookup")
def lookup_symbols(q: str = Query("", min_length=1)):
    return service.lookup_symbol(q)


@app.post("/api/trades")
def create_trade(payload: TradeCreate):
    try:
        return service.create_trade(payload)
    except ValidationError as e:
        _validation_http(e)


@app.patch("/api/trades/{trade_id}")
def patch_trade(trade_id: str, payload: TradePatch):
    try:
        row = service.patch_trade(trade_id, payload)
    except ValidationError as e:
        _validation_http(e)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@app.post("/api/trades/{trade_id}/close")
def close_trade(trade_id: str):
    try:
        row = service.close_trade(trade_id)
    except ValidationError as e:
        _validation_http(e)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


ui_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
if ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")
