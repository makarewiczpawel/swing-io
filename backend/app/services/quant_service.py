"""
Quant Analytics Service — wskaźniki kwantowe dla swing.io.

Kategorie:
  1. Zmienność:    VIX, VIX percentyl, VIX term structure, HV 20d, IV-HV spread, ATR percentyl
  2. Breadth:      % spółek S&P 500 > SMA 50/200, A/D ratio (proxy)
  3. Statystyczne: Z-Score 50d/200d, Hurst Exponent
  4. Sentiment:    Put/Call ratio (placeholder — CBOE paywall)
  5. Cross-market: korelacje S&P/TLT/GLD, credit spread HYG-LQD, DXY change

Risk Score (0–100): agregat wszystkich kategorii.
Quant Signal: EXTREME_GREED | RISK_ON | NEUTRAL | RISK_OFF | EXTREME_FEAR
"""

import pandas as pd
import numpy as np
import yfinance as yf
import ta
import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─── Top-50 S&P 500 komponentów (proxy dla breadth) ──────────────
SP500_PROXY = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","UNH","XOM",
    "JPM","JNJ","V","PG","HD","MA","AVGO","CVX","LLY","ABBV",
    "MRK","PEP","COST","ADBE","AMD","CSCO","TMO","ABT","ACN","CRM",
    "DIS","NEE","NKE","QCOM","BMY","MDT","ORCL","NFLX","TXN","WMT",
    "MCD","RTX","HON","LOW","CAT","SPGI","GS","AXP","BKNG","AMGN",
]

# Cache z lockiem — zapobiega podwójnym obliczeniom przy concurrent requests
_cache: dict = {}
_cache_lock = threading.Lock()
_cache_compute_locks: dict[str, threading.Lock] = {}
CACHE_TTL = 3600  # 1 h


def _cached(key: str, fn, ttl: int = CACHE_TTL):
    # Fast path bez locka
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < ttl:
        return entry["data"]
    # Per-key lock — concurrent requests dla różnych kluczy nie blokują się
    with _cache_lock:
        compute_lock = _cache_compute_locks.setdefault(key, threading.Lock())
    with compute_lock:
        entry = _cache.get(key)
        if entry and time.time() - entry["ts"] < ttl:
            return entry["data"]
        result = fn()
        _cache[key] = {"data": result, "ts": time.time()}
        return result


def _fetch(tickers: list[str], period_days: int = 365) -> pd.DataFrame:
    """Batch download OHLCV dla wielu tickerów (Close only)."""
    start = (datetime.now() - timedelta(days=period_days + 10)).strftime("%Y-%m-%d")
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw["Close"]
    else:
        closes = raw[["Close"]] if "Close" in raw.columns else raw
    if closes.index.tz is not None:
        closes.index = closes.index.tz_localize(None)
    return closes.dropna(how="all")


def _fetch_single(ticker: str, period_days: int = 400) -> pd.DataFrame:
    start = (datetime.now() - timedelta(days=period_days + 10)).strftime("%Y-%m-%d")
    df = yf.Ticker(ticker).history(start=start, auto_adjust=True)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


# ─── 1. Zmienność ─────────────────────────────────────────────────

def _volatility_snapshot() -> dict:
    gspc = _fetch_single("^GSPC", 300)
    vix  = _fetch_single("^VIX",  300)
    vix3m = _fetch_single("^VIX3M", 30)

    close_gspc = gspc["Close"]
    close_vix  = vix["Close"]

    current_vix = float(close_vix.iloc[-1])
    vix_sma20   = float(close_vix.rolling(20).mean().iloc[-1])

    # Percentyl VIX vs ostatnie 252 dni
    hist_252 = close_vix.tail(252)
    vix_pct = float((hist_252 < current_vix).sum() / len(hist_252) * 100)

    # VIX term structure
    vix3m_val = float(vix3m["Close"].iloc[-1]) if not vix3m.empty else None
    if vix3m_val:
        ratio = current_vix / vix3m_val
        if ratio < 0.9:
            vix_term = "CONTANGO"
        elif ratio > 1.05:
            vix_term = "BACKWARDATION"
        else:
            vix_term = "FLAT"
    else:
        vix_term = "UNKNOWN"

    # Historical Volatility 20d (annualized)
    log_ret = np.log(close_gspc / close_gspc.shift(1)).dropna()
    hv_20 = float(log_ret.tail(20).std() * np.sqrt(252) * 100)

    # IV-HV spread
    iv_hv_spread = round(current_vix - hv_20, 2)

    # ATR percentyl
    df_atr = gspc.copy()
    atr_series = ta.volatility.AverageTrueRange(df_atr["High"], df_atr["Low"], df_atr["Close"], window=14).average_true_range()
    atr_now = float(atr_series.iloc[-1])
    atr_hist = atr_series.dropna().tail(252)
    atr_pct  = float((atr_hist < atr_now).sum() / len(atr_hist) * 100)

    # VIX regime label
    if current_vix < 15:
        vix_regime = "LOW"
    elif current_vix < 25:
        vix_regime = "NORMAL"
    elif current_vix < 35:
        vix_regime = "ELEVATED"
    else:
        vix_regime = "PANIC"

    return {
        "vix": round(current_vix, 2),
        "vix_sma20": round(vix_sma20, 2),
        "vix_percentile_252d": round(vix_pct, 1),
        "vix_regime": vix_regime,
        "vix_term_structure": vix_term,
        "vix3m": round(vix3m_val, 2) if vix3m_val else None,
        "historical_vol_20d": round(hv_20, 2),
        "iv_hv_spread": iv_hv_spread,
        "atr": round(atr_now, 2),
        "atr_percentile_252d": round(atr_pct, 1),
    }


def _volatility_history(days: int = 252) -> dict:
    """Zwróć historyczne serie VIX i HV dla wykresów."""
    vix_df = _fetch_single("^VIX", days + 30)
    gspc   = _fetch_single("^GSPC", days + 30)

    vix_series = vix_df["Close"].tail(days)
    log_ret    = np.log(gspc["Close"] / gspc["Close"].shift(1)).dropna()
    hv_series  = (log_ret.rolling(20).std() * np.sqrt(252) * 100).tail(days)

    def to_points(series):
        out = []
        for ts, v in series.items():
            if pd.isna(v): continue
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(pd.Timestamp(ts).timestamp())
            out.append({"time": t, "value": round(float(v), 2)})
        return out

    return {
        "vix": to_points(vix_series),
        "hv_20d": to_points(hv_series),
    }


# ─── 2. Breadth ───────────────────────────────────────────────────

def _breadth_snapshot() -> dict:
    """Oblicz % spółek proxy S&P 500 powyżej SMA 50 i SMA 200."""
    def compute():
        logger.info(f"Computing breadth for {len(SP500_PROXY)} stocks...")
        closes = _fetch(SP500_PROXY, 320)  # 320 dni kalendarzowych ≈ 220+ sesji handlowych
        above50, above200, total = 0, 0, 0
        for col in closes.columns:
            s = closes[col].dropna()
            if len(s) < 50: continue
            total += 1
            sma50  = s.tail(50).mean()
            above50  += int(s.iloc[-1] > sma50)
            if len(s) >= 200:
                sma200 = s.tail(200).mean()
                above200 += int(s.iloc[-1] > sma200)

        pct50  = round(above50  / total * 100, 1) if total else 50.0
        pct200 = round(above200 / total * 100, 1) if total else 50.0
        return {"pct_above_sma50": pct50, "pct_above_sma200": pct200, "sample_size": total}

    return _cached("breadth", compute, ttl=3600)


# ─── 3. Statystyczne ─────────────────────────────────────────────

def _statistical_snapshot() -> dict:
    gspc = _fetch_single("^GSPC", 300)
    close = gspc["Close"]

    price = float(close.iloc[-1])

    # Z-Score
    sma50  = float(close.tail(50).mean())
    std50  = float(close.tail(50).std())
    z50    = round((price - sma50)  / std50,  3) if std50  > 0 else 0.0

    sma200 = float(close.tail(200).mean()) if len(close) >= 200 else sma50
    std200 = float(close.tail(200).std())  if len(close) >= 200 else std50
    z200   = round((price - sma200) / std200, 3) if std200 > 0 else 0.0

    # Hurst Exponent (R/S analysis)
    hurst = _hurst_exponent(close.values, window=100)

    return {
        "z_score_50d":   z50,
        "z_score_200d":  z200,
        "hurst_exponent": hurst,
        "hurst_interpretation": (
            "Trending"       if hurst > 0.55 else
            "Random walk"    if hurst > 0.45 else
            "Mean-reverting"
        ),
    }


def _hurst_exponent(prices: np.ndarray, window: int = 100) -> float:
    """R/S analysis dla estymacji wykładnika Hursta."""
    if len(prices) < window + 10:
        return 0.5
    prices = prices[-window:]
    returns = np.log(prices[1:] / prices[:-1])

    lags, rs_vals = [], []
    for lag in range(2, window // 2, max(1, window // 20)):
        chunks = [returns[i:i+lag] for i in range(0, len(returns) - lag, lag)]
        chunk_rs = []
        for c in chunks:
            if len(c) < 2: continue
            std = c.std()
            if std == 0: continue
            cum = np.cumsum(c - c.mean())
            chunk_rs.append((cum.max() - cum.min()) / std)
        if chunk_rs:
            lags.append(np.log(lag))
            rs_vals.append(np.log(np.mean(chunk_rs)))

    if len(lags) < 3:
        return 0.5
    H = float(np.polyfit(lags, rs_vals, 1)[0])
    return round(float(np.clip(H, 0.1, 0.9)), 3)


def _zscore_history(days: int = 252) -> dict:
    """Historia Z-Score dla wykresów."""
    gspc = _fetch_single("^GSPC", days + 220)
    close = gspc["Close"]

    z50_series  = (close - close.rolling(50).mean()) / close.rolling(50).std()
    z200_series = (close - close.rolling(200).mean()) / close.rolling(200).std()

    def to_points(s):
        s = s.dropna().tail(days)
        out = []
        for ts, v in s.items():
            if pd.isna(v): continue
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(pd.Timestamp(ts).timestamp())
            out.append({"time": t, "value": round(float(v), 3)})
        return out

    return {"z_score_50d": to_points(z50_series), "z_score_200d": to_points(z200_series)}


# ─── 4. Sentiment (placeholder) ───────────────────────────────────

def _sentiment_snapshot() -> dict:
    # CBOE Put/Call ratio nie jest dostępne na darmowym tierze.
    # Zwracamy None — frontend wyświetli "N/A".
    return {"put_call_ratio": None, "put_call_sma10": None, "source": "unavailable"}


# ─── 5. Cross-Market ─────────────────────────────────────────────

def _crossmarket_snapshot() -> dict:
    tickers = ["^GSPC", "TLT", "GLD", "DX-Y.NYB", "HYG", "LQD"]
    closes = _fetch(tickers, 100)

    gspc = closes.get("^GSPC", closes.iloc[:, 0])
    tlt  = closes.get("TLT",  None)
    gld  = closes.get("GLD",  None)
    dxy  = closes.get("DX-Y.NYB", None)
    hyg  = closes.get("HYG", None)
    lqd  = closes.get("LQD", None)

    def corr30(a, b):
        if a is None or b is None: return None
        df = pd.concat([a, b], axis=1).dropna()
        if len(df) < 20: return None
        r = df.tail(30).corr().iloc[0, 1]
        return round(float(r), 3)

    # Credit spread proxy: HYG return minus LQD return (30d)
    credit_spread = None
    credit_spread_change = None
    if hyg is not None and lqd is not None:
        df_cr = pd.concat([hyg, lqd], axis=1).dropna()
        if len(df_cr) >= 30:
            hyg_ret = float((df_cr.iloc[-1, 0] / df_cr.iloc[-30, 0] - 1) * 100)
            lqd_ret = float((df_cr.iloc[-1, 1] / df_cr.iloc[-30, 1] - 1) * 100)
            credit_spread = round(hyg_ret - lqd_ret, 3)
            if len(df_cr) >= 60:
                hyg_ret_prev = float((df_cr.iloc[-30, 0] / df_cr.iloc[-60, 0] - 1) * 100)
                lqd_ret_prev = float((df_cr.iloc[-30, 1] / df_cr.iloc[-60, 1] - 1) * 100)
                credit_spread_change = round(credit_spread - (hyg_ret_prev - lqd_ret_prev), 3)

    # DXY change 20d
    dxy_change_20d = None
    if dxy is not None and len(dxy) >= 20:
        dxy_change_20d = round(float((dxy.iloc[-1] / dxy.iloc[-20] - 1) * 100), 2)

    return {
        "corr_sp500_tlt_30d":  corr30(gspc, tlt),
        "corr_sp500_gold_30d": corr30(gspc, gld),
        "credit_spread_30d":   credit_spread,
        "credit_spread_change": credit_spread_change,
        "dxy_change_20d":      dxy_change_20d,
        "tlt_price":  round(float(tlt.iloc[-1]),  2) if tlt  is not None else None,
        "gld_price":  round(float(gld.iloc[-1]),  2) if gld  is not None else None,
        "dxy_price":  round(float(dxy.iloc[-1]),  2) if dxy  is not None else None,
        "hyg_price":  round(float(hyg.iloc[-1]),  2) if hyg  is not None else None,
        "lqd_price":  round(float(lqd.iloc[-1]),  2) if lqd  is not None else None,
    }


def _correlations_history(days: int = 252) -> dict:
    """Historyczne korelacje rolling 30d do wykresów."""
    tickers = ["^GSPC", "TLT", "GLD", "DX-Y.NYB"]
    closes = _fetch(tickers, days + 40)

    gspc = closes["^GSPC"] if "^GSPC" in closes.columns else closes.iloc[:, 0]

    def rolling_corr(other_col):
        if other_col not in closes.columns:
            return []
        df = pd.concat([gspc, closes[other_col]], axis=1).dropna()
        rc = df.iloc[:, 0].rolling(30).corr(df.iloc[:, 1]).tail(days)
        out = []
        for ts, v in rc.items():
            if pd.isna(v): continue
            t = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(pd.Timestamp(ts).timestamp())
            out.append({"time": t, "value": round(float(v), 3)})
        return out

    return {
        "sp500_tlt":  rolling_corr("TLT"),
        "sp500_gold": rolling_corr("GLD"),
        "sp500_dxy":  rolling_corr("DX-Y.NYB"),
    }


# ─── Risk Score ───────────────────────────────────────────────────

def _risk_score(vol: dict, breadth: dict, stat: dict, sentiment: dict, cross: dict) -> tuple[int, str]:
    score = 50

    # Zmienność
    vix = vol.get("vix", 20)
    if vix > 30:   score += 15
    elif vix > 25: score += 10
    elif vix < 15: score -= 10

    # VIX term structure
    vts = vol.get("vix_term_structure", "CONTANGO")
    if vts == "BACKWARDATION": score += 10
    elif vts == "CONTANGO":    score -= 5

    # Breadth
    pct50 = breadth.get("pct_above_sma50", 50)
    if pct50 < 30:   score += 15
    elif pct50 > 70: score -= 10

    # Sentiment (P/C ratio)
    pc = sentiment.get("put_call_ratio")
    if pc:
        if pc > 1.2:  score += 10
        elif pc < 0.6: score -= 10

    # Cross-market
    corr_tlt = cross.get("corr_sp500_tlt_30d")
    if corr_tlt and corr_tlt > 0.3: score += 10

    cs_change = cross.get("credit_spread_change")
    if cs_change and cs_change > 0.5: score += 10

    # Z-Score
    z50 = stat.get("z_score_50d", 0)
    if z50 > 2:   score += 5
    elif z50 < -2: score -= 5

    score = max(0, min(100, round(score)))

    if score <= 20:   signal = "EXTREME_GREED"
    elif score <= 40: signal = "RISK_ON"
    elif score <= 60: signal = "NEUTRAL"
    elif score <= 80: signal = "RISK_OFF"
    else:             signal = "EXTREME_FEAR"

    return score, signal


# ─── Publiczne API ────────────────────────────────────────────────

def get_quant_snapshot() -> dict:
    """Pełny snapshot wskaźników kwantowych."""
    logger.info("Computing quant snapshot...")
    vol       = _cached("vol",   _volatility_snapshot,  300)
    breadth   = _cached("breadth", _breadth_snapshot,  3600)
    stat      = _cached("stat",  _statistical_snapshot, 300)
    sentiment = _cached("sent",  _sentiment_snapshot,   300)
    cross     = _cached("cross", _crossmarket_snapshot, 300)

    score, signal = _risk_score(vol, breadth, stat, sentiment, cross)

    return {
        "timestamp": datetime.now().isoformat(),
        "risk_score":   score,
        "quant_signal": signal,
        "volatility":   vol,
        "breadth":      breadth,
        "statistical":  stat,
        "sentiment":    sentiment,
        "cross_market": cross,
    }


def get_risk_score() -> dict:
    snap = get_quant_snapshot()
    return {
        "risk_score":   snap["risk_score"],
        "quant_signal": snap["quant_signal"],
        "vix":          snap["volatility"]["vix"],
        "vix_regime":   snap["volatility"]["vix_regime"],
        "pct_above_sma50":  snap["breadth"].get("pct_above_sma50"),
        "pct_above_sma200": snap["breadth"].get("pct_above_sma200"),
        "z_score_50d":  snap["statistical"]["z_score_50d"],
        "hurst":        snap["statistical"]["hurst_exponent"],
        "timestamp":    snap["timestamp"],
    }


def get_vix_history(days: int = 252) -> dict:
    return _cached(f"vix_hist_{days}", lambda: _volatility_history(days), 300)


def get_zscore_history(days: int = 252) -> dict:
    return _cached(f"zscore_hist_{days}", lambda: _zscore_history(days), 300)


def get_correlations_history(days: int = 252) -> dict:
    return _cached(f"corr_hist_{days}", lambda: _correlations_history(days), 300)
