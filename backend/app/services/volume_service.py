"""
Volume Analyst — OBV trend, relative volume, climax/dry-up, OBV divergence.
Używa SPY (zamiast ^GSPC) bo indeks ma niestabilne dane wolumenowe.
"""

import pandas as pd
import numpy as np
import ta
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _fetch(ticker: str, days: int) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=days + 60)  # bufor
    df = yf.Ticker(ticker).history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1d",
    )
    if df.empty:
        return df
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def get_volume_analysis(days: int = 60) -> dict:
    """
    Returns:
      obv_trend       : RISING | FALLING | FLAT
      relative_volume : float  (today vs 20d avg)
      volume_regime   : CLIMAX | DRY_UP | NORMAL
      volume_confirmation : bool  (vol supports price move)
      obv_divergence  : None | "bullish" | "bearish"
      avg_volume_20d  : float
      current_volume  : float
    """
    try:
        spy = _fetch("SPY", days)
        if spy.empty or len(spy) < 25:
            return _empty("Brak danych SPY")

        spy["obv"]      = ta.volume.OnBalanceVolumeIndicator(spy["Close"], spy["Volume"]).on_balance_volume()
        spy["vol_sma20"] = spy["Volume"].rolling(20).mean()
        spy = spy.dropna(subset=["obv", "vol_sma20"])

        if len(spy) < 5:
            return _empty("Za mało danych po dropna")

        last      = spy.iloc[-1]
        prev5     = spy.iloc[-6:-1]
        curr_vol  = float(last["Volume"])
        avg_vol   = float(last["vol_sma20"])
        rel_vol   = curr_vol / avg_vol if avg_vol > 0 else 1.0

        # OBV trend — slope over last 10 bars
        obv_series  = spy["obv"].tail(10)
        obv_slope   = float(np.polyfit(range(len(obv_series)), obv_series.values, 1)[0])
        price_range = float(spy["Close"].tail(10).max() - spy["Close"].tail(10).min()) or 1.0
        obv_trend   = "RISING" if obv_slope > 0 else "FALLING" if obv_slope < 0 else "FLAT"

        # Volume regime
        candle_body = abs(float(last["Close"]) - float(last["Open"]))
        candle_rng  = (float(last["High"]) - float(last["Low"])) or 1e-6
        if rel_vol >= 2.0 and candle_body / candle_rng > 0.5:
            volume_regime = "CLIMAX"
        elif rel_vol <= 0.5:
            volume_regime = "DRY_UP"
        else:
            volume_regime = "NORMAL"

        # Volume confirmation — price direction agrees with volume trend
        price_up     = float(last["Close"]) > float(spy.iloc[-2]["Close"])
        vol_confirm  = (price_up and obv_trend == "RISING") or (not price_up and obv_trend == "FALLING")

        # OBV divergence — compare last 2 significant swings (simplified)
        obv_div = _obv_divergence(spy)

        return {
            "obv_trend":           obv_trend,
            "relative_volume":     round(rel_vol, 2),
            "volume_regime":       volume_regime,
            "volume_confirmation": vol_confirm,
            "obv_divergence":      obv_div,
            "avg_volume_20d":      round(avg_vol / 1e6, 2),   # w milionach
            "current_volume":      round(curr_vol / 1e6, 2),  # w milionach
            "error":               None,
        }

    except Exception as e:
        logger.error(f"Volume analysis error: {e}", exc_info=True)
        return _empty(str(e))


def _obv_divergence(df: pd.DataFrame, window: int = 5) -> str | None:
    """Prosta detekcja dywergencji OBV vs cena na ostatnich ~30 barach."""
    recent = df.tail(30).reset_index(drop=True)
    n = len(recent)
    if n < window * 2 + 2:
        return None

    for i in range(window, n - 1):
        w = recent.iloc[i - window: i + 1]
        # Price high swing
        if recent.iloc[i]["High"] >= w["High"].max():
            prev_w = recent.iloc[max(0, i - 25): i - window]
            if len(prev_w) < 3:
                continue
            prev_hi_idx  = prev_w["High"].idxmax()
            if recent.iloc[i]["High"] > prev_w.loc[prev_hi_idx, "High"]:   # higher high
                if recent.iloc[i]["obv"] < prev_w.loc[prev_hi_idx, "obv"]: # OBV lower
                    return "bearish"
        # Price low swing
        if recent.iloc[i]["Low"] <= w["Low"].min():
            prev_w = recent.iloc[max(0, i - 25): i - window]
            if len(prev_w) < 3:
                continue
            prev_lo_idx  = prev_w["Low"].idxmin()
            if recent.iloc[i]["Low"] < prev_w.loc[prev_lo_idx, "Low"]:     # lower low
                if recent.iloc[i]["obv"] > prev_w.loc[prev_lo_idx, "obv"]: # OBV higher
                    return "bullish"
    return None


def _empty(error: str) -> dict:
    return {
        "obv_trend": "UNKNOWN", "relative_volume": 1.0,
        "volume_regime": "UNKNOWN", "volume_confirmation": False,
        "obv_divergence": None, "avg_volume_20d": 0.0,
        "current_volume": 0.0, "error": error,
    }
