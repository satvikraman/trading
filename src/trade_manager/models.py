from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TradeCreate(BaseModel):
    mode: Literal["buy_fresh", "already_held"]
    MKT_SYMBOL: str
    STOCK: str = ""
    SOURCE: str = "MANUAL"
    STRATEGY: str
    PRODUCT: str = "CASH"
    BUY_SELL: str = "BUY"
    MKT: str = "NSE"
    REC_DATE: str
    REC_TIME: str = "xx:xx"
    EXP_DATE: str = ""
    LOW_REC_PRICE: float
    HIGH_REC_PRICE: float
    TARGET: float
    STOP_LOSS: float
    QTY: int
    SECURITY_ID: str = ""
    ICICI_SYMBOL: str = ""


class TradePatch(BaseModel):
    QTY: Optional[int] = None
    LOW_REC_PRICE: Optional[float] = None
    HIGH_REC_PRICE: Optional[float] = None
    TARGET: Optional[float] = None
    STOP_LOSS: Optional[float] = None


class TradeResponse(BaseModel):
    id: str
    trade: dict[str, Any]
