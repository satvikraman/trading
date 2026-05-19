import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .models import HeldQtyAdjustRequest, SymbolRenameRequest, TradeCreate, TradePatch
from .service import TradeService
from .validation import ValidationError

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Trade Manager", version="1.0")
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


@app.get("/api/symbols/rename/preview")
def preview_symbol_rename(
    from_mkt_symbol: str = Query(..., min_length=1),
    to_mkt_symbol: str = Query(..., min_length=1),
    update_security_id: bool = True,
    active_only: bool = False,
):
    try:
        return service.preview_symbol_rename(
            from_mkt_symbol,
            to_mkt_symbol,
            update_security_id=update_security_id,
            active_only=active_only,
        )
    except ValidationError as e:
        _validation_http(e)


@app.post("/api/symbols/rename")
def rename_symbol(payload: SymbolRenameRequest):
    try:
        return service.rename_symbol(
            payload.from_mkt_symbol,
            payload.to_mkt_symbol,
            update_security_id=payload.update_security_id,
            active_only=payload.active_only,
        )
    except ValidationError as e:
        _validation_http(e)


@app.post("/api/dataset/refresh")
def refresh_dataset(force: bool = False):
    """Re-download ICICI SecurityMaster zip (once per day unless force=true)."""
    try:
        paths = service.refresh_security_master(force=force)
        return {"status": "ok", "paths": paths}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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


@app.get("/api/trades/{trade_id}/held-qty/preview")
def preview_adjust_held_qty(trade_id: str, pos_hold_qty: int = Query(..., ge=0)):
    try:
        preview = service.preview_adjust_held_qty(trade_id, pos_hold_qty)
    except ValidationError as e:
        _validation_http(e)
    if not preview:
        raise HTTPException(status_code=404, detail="Not found")
    return preview


@app.post("/api/trades/{trade_id}/held-qty")
def adjust_held_qty(trade_id: str, payload: HeldQtyAdjustRequest):
    try:
        row = service.adjust_held_qty(trade_id, payload.pos_hold_qty)
    except ValidationError as e:
        _validation_http(e)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


ui_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
if ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")
