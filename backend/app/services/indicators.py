"""
Technical indicators service — obliczanie wskaźników na danych S&P 500.
Używa biblioteki `ta` (nie wymaga kompilacji C jak ta-lib).
"""

import pandas as pd
import numpy as np
import ta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Stałe ──────────────────────────────────────────────────────────
SMA_PERIODS = [9, 21, 50, 200]
EMA_PERIODS = [9, 21]
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
BB_PERIOD, BB_STD = 20, 2
ADX_PERIOD = 14


def _series_to_points(index: pd.Index, series: pd.Series) -> list[dict]:
    """Konwertuj Series do listy {time, value}, pomijając NaN."""
    result = []
    for ts, val in zip(index, series):
        if pd.isna(val):
            continue
        if hasattr(ts, "timestamp"):
            t = int(ts.timestamp())
        else:
            t = int(pd.Timestamp(ts).timestamp())
        result.append({"time": t, "value": round(float(val), 4)})
    return result


class IndicatorsService:
    """Oblicza wskaźniki techniczne na danych yfinance."""

    def __init__(self, market_service):
        self._market = market_service

    def _fetch_df(self, interval: str, days: int) -> pd.DataFrame:
        """Pobierz DataFrame ze świecami przez MarketDataService."""
        from datetime import datetime, timedelta
        import yfinance as yf

        ticker = yf.Ticker("^GSPC")
        # Dodaj bufor dla wskaźników wymagających historii (SMA200 = 200 świec)
        buffer_days = days + 300
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=buffer_days)

        yf_interval_map = {"1h": "1h", "4h": "1h", "1D": "1d", "1W": "1wk"}
        yf_interval = yf_interval_map.get(interval, "1d")

        df = ticker.history(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            interval=yf_interval,
            auto_adjust=True,
        )

        if df.empty:
            return df

        # Agreguj do 4h jeśli potrzeba
        if interval == "4h":
            df = self._aggregate_to_4h(df)

        # Ogranicz do żądanego zakresu (po naliczeniu wskaźników zwrócimy tylko ten zakres)
        return df

    def _aggregate_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df["_group"] = df.index.floor("4h")
        agg = df.groupby("_group").agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Volume=("Volume", "sum"),
        )
        counts = df.groupby("_group").size()
        valid = counts[counts >= 2].index
        return agg.loc[agg.index.isin(valid)]

    def get_indicators(self, interval: str = "1D", days: int = 365) -> dict:
        """
        Oblicz wszystkie wskaźniki i zwróć jako słownik serii czasowych.
        Każda seria to lista {time, value} gotowa do renderowania na wykresie.
        """
        df = self._fetch_df(interval, days)
        if df.empty:
            logger.warning("Empty DataFrame — brak danych do wskaźników")
            return {}

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        result: dict = {}

        # ─── SMA ────────────────────────────────────────────────────
        result["sma"] = {}
        for p in SMA_PERIODS:
            if len(close) >= p:
                sma = ta.trend.SMAIndicator(close, window=p).sma_indicator()
                result["sma"][str(p)] = _series_to_points(df.index, sma)

        # ─── EMA ────────────────────────────────────────────────────
        result["ema"] = {}
        for p in EMA_PERIODS:
            ema = ta.trend.EMAIndicator(close, window=p).ema_indicator()
            result["ema"][str(p)] = _series_to_points(df.index, ema)

        # ─── RSI ────────────────────────────────────────────────────
        rsi = ta.momentum.RSIIndicator(close, window=RSI_PERIOD).rsi()
        result["rsi"] = _series_to_points(df.index, rsi)

        # ─── MACD ───────────────────────────────────────────────────
        macd_ind = ta.trend.MACD(
            close,
            window_slow=MACD_SLOW,
            window_fast=MACD_FAST,
            window_sign=MACD_SIGNAL,
        )
        macd_line = macd_ind.macd()
        signal_line = macd_ind.macd_signal()
        histogram = macd_ind.macd_diff()

        macd_points = []
        for ts, m, s, h in zip(df.index, macd_line, signal_line, histogram):
            if any(pd.isna(x) for x in [m, s, h]):
                continue
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(pd.Timestamp(ts).timestamp())
            macd_points.append({
                "time": t,
                "macd": round(float(m), 4),
                "signal": round(float(s), 4),
                "histogram": round(float(h), 4),
            })
        result["macd"] = macd_points

        # ─── Bollinger Bands ────────────────────────────────────────
        bb = ta.volatility.BollingerBands(close, window=BB_PERIOD, window_dev=BB_STD)
        upper = bb.bollinger_hband()
        middle = bb.bollinger_mavg()
        lower = bb.bollinger_lband()
        bandwidth = bb.bollinger_wband()

        bb_points = []
        for ts, u, m, lo, bw in zip(df.index, upper, middle, lower, bandwidth):
            if any(pd.isna(x) for x in [u, m, lo]):
                continue
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(pd.Timestamp(ts).timestamp())
            bb_points.append({
                "time": t,
                "upper": round(float(u), 2),
                "middle": round(float(m), 2),
                "lower": round(float(lo), 2),
                "bandwidth": round(float(bw), 4) if not pd.isna(bw) else None,
            })
        result["bb"] = bb_points

        # ─── ADX ────────────────────────────────────────────────────
        adx_ind = ta.trend.ADXIndicator(high, low, close, window=ADX_PERIOD)
        adx_vals = adx_ind.adx()
        dmi_plus = adx_ind.adx_pos()
        dmi_minus = adx_ind.adx_neg()

        adx_points = []
        for ts, adx, dp, dm in zip(df.index, adx_vals, dmi_plus, dmi_minus):
            if any(pd.isna(x) for x in [adx, dp, dm]):
                continue
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(pd.Timestamp(ts).timestamp())
            adx_points.append({
                "time": t,
                "adx": round(float(adx), 2),
                "dmi_plus": round(float(dp), 2),
                "dmi_minus": round(float(dm), 2),
            })
        result["adx"] = adx_points

        # Ogranicz SMA/EMA do żądanego zakresu (ostatnie `days` dni)
        result = _trim_to_days(result, df.index, days)

        logger.info(
            f"Indicators computed | interval={interval} | "
            f"rsi={len(result.get('rsi', []))} pts, "
            f"macd={len(result.get('macd', []))} pts"
        )
        return result

    def get_regime(self, interval: str = "1D") -> dict:
        """
        Klasyfikuj aktualny reżim rynkowy na podstawie ADX, SMA50, SMA200.

        Algorytm (wg planu v2.1):
          UPTREND     — ADX > 25 AND cena > SMA50 > SMA200
          DOWNTREND   — ADX > 25 AND cena < SMA50 < SMA200
          SIDEWAYS    — ADX < 20 OR SMA50 ≈ SMA200 (w zakresie 1%)
          TRANSITIONING — ADX 20–25
        """
        df = self._fetch_df(interval, days=300)
        if df.empty or len(df) < 200:
            return {"regime": "UNKNOWN", "error": "insufficient data"}

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator().iloc[-1]
        sma200 = ta.trend.SMAIndicator(close, window=200).sma_indicator().iloc[-1]
        adx_ind = ta.trend.ADXIndicator(high, low, close, window=ADX_PERIOD)
        adx = adx_ind.adx().iloc[-1]
        dmi_plus = adx_ind.adx_pos().iloc[-1]
        dmi_minus = adx_ind.adx_neg().iloc[-1]
        rsi = ta.momentum.RSIIndicator(close, window=RSI_PERIOD).rsi().iloc[-1]
        price = float(close.iloc[-1])

        sma50_f = float(sma50)
        sma200_f = float(sma200)
        adx_f = float(adx)
        rsi_f = float(rsi)

        # Klasyfikacja reżimu
        sma_spread_pct = abs(sma50_f - sma200_f) / sma200_f * 100

        if adx_f < 20 or sma_spread_pct < 1.0:
            regime = "SIDEWAYS"
            confidence = max(0.0, (20 - adx_f) / 20 * 100)
        elif 20 <= adx_f <= 25:
            regime = "TRANSITIONING"
            confidence = 50.0
        elif adx_f > 25 and price > sma50_f > sma200_f:
            regime = "UPTREND"
            confidence = min(100.0, (adx_f - 25) / 25 * 100 + 50)
        elif adx_f > 25 and price < sma50_f < sma200_f:
            regime = "DOWNTREND"
            confidence = min(100.0, (adx_f - 25) / 25 * 100 + 50)
        else:
            # Mieszane warunki — np. cena > SMA50, ale SMA50 < SMA200
            regime = "TRANSITIONING"
            confidence = 40.0

        descriptions = {
            "UPTREND": f"Trend wzrostowy: cena ({price:.0f}) > SMA50 ({sma50_f:.0f}) > SMA200 ({sma200_f:.0f}), ADX = {adx_f:.1f}",
            "DOWNTREND": f"Trend spadkowy: cena ({price:.0f}) < SMA50 ({sma50_f:.0f}) < SMA200 ({sma200_f:.0f}), ADX = {adx_f:.1f}",
            "SIDEWAYS": f"Konsolidacja: ADX = {adx_f:.1f} (< 20), SMA50/200 zbieżne ({sma_spread_pct:.1f}% spread)",
            "TRANSITIONING": f"Zmiana reżimu: ADX = {adx_f:.1f} (20–25), niejednoznaczny kierunek",
        }

        return {
            "regime": regime,
            "confidence": round(confidence, 1),
            "description": descriptions.get(regime, ""),
            "price": round(price, 2),
            "sma_50": round(sma50_f, 2),
            "sma_200": round(sma200_f, 2),
            "adx": round(adx_f, 2),
            "dmi_plus": round(float(dmi_plus), 2),
            "dmi_minus": round(float(dmi_minus), 2),
            "rsi": round(rsi_f, 2),
            "above_sma_50": price > sma50_f,
            "above_sma_200": price > sma200_f,
            "interval": interval,
        }


def _trim_to_days(result: dict, index: pd.Index, days: int) -> dict:
    """Ogranicz serie czasowe do ostatnich `days` dni (po obliczeniu wskaźników)."""
    if not hasattr(index, "to_series"):
        return result

    # Wyznacz cutoff timestamp
    cutoff = index[-1] - pd.Timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp()) if hasattr(cutoff, "timestamp") else 0

    def trim_list(points: list) -> list:
        if not points or not isinstance(points[0], dict):
            return points
        return [p for p in points if p.get("time", 0) >= cutoff_ts]

    trimmed = {}
    for key, val in result.items():
        if isinstance(val, list):
            trimmed[key] = trim_list(val)
        elif isinstance(val, dict):
            trimmed[key] = {k: trim_list(v) for k, v in val.items()}
        else:
            trimmed[key] = val

    return trimmed
