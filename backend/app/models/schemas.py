"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class Candle(BaseModel):
    timestamp: int
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class CandlesResponse(BaseModel):
    ticker: str = "^GSPC"
    interval: str
    count: int
    candles: list[Candle]


class QuoteResponse(BaseModel):
    price: float
    change: float = 0
    change_pct: float = 0
    high: float = 0
    low: float = 0
    open: float = 0
    prev_close: float = 0
    timestamp: int = 0
    source: str = "yfinance"
    error: Optional[str] = None


class MarketInfoResponse(BaseModel):
    name: str = "S&P 500"
    ticker: str = "^GSPC"
    current_price: float = 0
    high_52w: float = 0
    low_52w: float = 0
    sma_50: float = 0
    sma_200: float = 0
    above_sma_50: bool = False
    above_sma_200: bool = False
    distance_from_high_pct: float = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    services: dict = {}


class RegimeResponse(BaseModel):
    regime: str                    # UPTREND | DOWNTREND | SIDEWAYS | TRANSITIONING | UNKNOWN
    confidence: float = 0.0
    description: str = ""
    price: float = 0.0
    sma_50: float = 0.0
    sma_200: float = 0.0
    adx: float = 0.0
    dmi_plus: float = 0.0
    dmi_minus: float = 0.0
    rsi: float = 0.0
    above_sma_50: bool = False
    above_sma_200: bool = False
    interval: str = "1D"
    error: Optional[str] = None


class IndicatorsResponse(BaseModel):
    interval: str
    days: int
    sma: dict = {}
    ema: dict = {}
    rsi: list = []
    macd: list = []
    bb: list = []
    adx: list = []


# ─── Backtesting ─────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    strategy: str
    interval: str = "1D"
    train_from: str = "2010-01-01"
    train_to: str = "2021-12-31"
    test_from: str = "2022-01-01"
    test_to: str = "2026-12-31"
    params: dict = {}
    initial_capital: float = 100_000.0
    commission_pct: float = 0.1
    slippage_pct: float = 0.05


class WalkForwardRequest(BaseModel):
    strategy: str
    interval: str = "1D"
    params: dict = {}
    initial_capital: float = 100_000.0
