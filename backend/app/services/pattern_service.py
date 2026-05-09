"""
Pattern recognition service — formacje świecowe, S/R, dywergencje, Price Action.
"""

import pandas as pd
import numpy as np
import ta
import logging
from datetime import datetime, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

BUFFER_DAYS = 250  # warmup dla SMA200 i wolumenu


def _ts(dt_index_val) -> int:
    """Timestamp → Unix int."""
    if hasattr(dt_index_val, "timestamp"):
        return int(dt_index_val.timestamp())
    return int(pd.Timestamp(dt_index_val).timestamp())


def _fetch_df(interval: str, days: int) -> pd.DataFrame:
    ticker = yf.Ticker("^GSPC")
    yf_map = {"1h": "1h", "4h": "1h", "1D": "1d", "1W": "1wk"}
    yf_interval = yf_map.get(interval, "1d")

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days + BUFFER_DAYS)

    df = ticker.history(
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        interval=yf_interval,
    )
    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                             "Close": "close", "Volume": "volume"})
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.index = pd.to_datetime(df.index)

    # 4h: aggregate 1h → 4h
    if interval == "4h":
        df = df.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna()

    df = df.dropna(subset=["close"])
    return df


def _trim(df: pd.DataFrame, days: int) -> pd.DataFrame:
    cutoff = pd.Timestamp.now(tz=df.index.tz) - pd.Timedelta(days=days)
    return df[df.index >= cutoff].copy()


# ─── Główna funkcja ──────────────────────────────────────────────────────────

def get_patterns(interval: str = "1D", days: int = 180) -> dict:
    df = _fetch_df(interval, days)
    if df.empty:
        return {"error": "Brak danych"}

    # Wskaźniki do dywergencji (na pełnym df z buforem)
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd_line"] = macd.macd()
    df["macd_hist"] = macd.macd_diff()
    df["vol_sma20"] = df["volume"].rolling(20).mean()

    def _reset(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.reset_index()
        frame = frame.rename(columns={frame.columns[0]: "dt"})
        return frame

    df_full = _reset(df)        # pełna historia (days + BUFFER) → S/R
    df = _reset(_trim(df, days))  # przycięty zakres → candle patterns, dywergencje, PA

    if len(df) < 5:
        return {"error": "Za mało danych"}

    # S/R na pełnej historii, filtrujem do n_levels najbliższych bieżącej cenie
    sr_levels = _find_sr(df_full)

    return {
        "interval": interval,
        "days": days,
        "count": len(df),
        "candle_patterns": _candle_patterns(df),
        "support_resistance": sr_levels,
        "divergences": _divergences(df),
        "price_action": _price_action(df),
        "breakouts": _breakouts(df, sr_levels),
    }


# ─── Formacje świecowe ───────────────────────────────────────────────────────

def _candle_patterns(df: pd.DataFrame) -> list:
    patterns = []
    n = len(df)

    for i in range(2, n):
        r  = df.iloc[i]
        p  = df.iloc[i - 1]
        p2 = df.iloc[i - 2]

        o, h, l, c = r.open, r.high, r.low, r.close
        po, ph, pl, pc = p.open, p.high, p.low, p.close
        p2o, p2h, p2l, p2c = p2.open, p2.high, p2.low, p2.close

        body   = abs(c - o)
        rng    = (h - l) or 1e-6
        p_body = abs(pc - po)
        p_rng  = (ph - pl) or 1e-6

        lower_shd = min(o, c) - l
        upper_shd = h - max(o, c)
        t = _ts(r["dt"])

        # Doji
        if body / rng < 0.1:
            patterns.append(_pat(t, "DOJI", "neutral", 1,
                                 "Doji — niezdecydowanie rynku"))

        # Hammer (bullish, long lower shadow)
        if body > 0 and lower_shd >= 2 * body and upper_shd <= body and c > o:
            patterns.append(_pat(t, "HAMMER", "bullish", 2,
                                 "Hammer — potencjalne odwrócenie wzrostowe"))

        # Hanging Man (bearish — wygląda jak hammer, ale w uptrendzie)
        if body > 0 and lower_shd >= 2 * body and upper_shd <= body and c < o:
            patterns.append(_pat(t, "HANGING_MAN", "bearish", 2,
                                 "Hanging Man — ostrzeżenie w uptrendzie"))

        # Shooting Star (bearish, long upper shadow)
        if body > 0 and upper_shd >= 2 * body and lower_shd <= body and c < o:
            patterns.append(_pat(t, "SHOOTING_STAR", "bearish", 2,
                                 "Shooting Star — potencjalne odwrócenie spadkowe"))

        # Inverted Hammer (bullish)
        if body > 0 and upper_shd >= 2 * body and lower_shd <= body and c > o:
            patterns.append(_pat(t, "INVERTED_HAMMER", "bullish", 1,
                                 "Inverted Hammer — potencjalne odwrócenie"))

        # Bullish Engulfing
        if (pc < po and c > o                         # prev bearish, curr bullish
                and o < pc and c > po                 # curr engulfs prev
                and body > p_body):
            patterns.append(_pat(t, "BULLISH_ENGULFING", "bullish", 3,
                                 "Bullish Engulfing — silny sygnał wzrostu"))

        # Bearish Engulfing
        if (pc > po and c < o
                and o > pc and c < po
                and body > p_body):
            patterns.append(_pat(t, "BEARISH_ENGULFING", "bearish", 3,
                                 "Bearish Engulfing — silny sygnał spadku"))

        # Morning Star (3-świecowy, byczý)
        p2_bear = p2c < p2o and abs(p2c - p2o) / p2_rng(p2h, p2l) > 0.5
        p1_small = p_body / p_rng < 0.35
        curr_bull = c > o and body / rng > 0.45 and c > (p2o + p2c) / 2
        if p2_bear and p1_small and curr_bull:
            patterns.append(_pat(t, "MORNING_STAR", "bullish", 3,
                                 "Morning Star — silne odwrócenie wzrostowe"))

        # Evening Star (3-świecowy, niedźwiedzi)
        p2_bull = p2c > p2o and abs(p2c - p2o) / p2_rng(p2h, p2l) > 0.5
        curr_bear = c < o and body / rng > 0.45 and c < (p2o + p2c) / 2
        if p2_bull and p1_small and curr_bear:
            patterns.append(_pat(t, "EVENING_STAR", "bearish", 3,
                                 "Evening Star — silne odwrócenie spadkowe"))

        # Three White Soldiers (okno 3)
        if (c > o and pc > po and p2c > p2o
                and body / rng > 0.5 and p_body / p_rng > 0.5
                and abs(p2c - p2o) / p2_rng(p2h, p2l) > 0.5
                and c > pc > p2c):
            patterns.append(_pat(t, "THREE_WHITE_SOLDIERS", "bullish", 3,
                                 "Three White Soldiers — silna kontynuacja wzrostu"))

        # Three Black Crows (okno 3)
        if (c < o and pc < po and p2c < p2o
                and body / rng > 0.5 and p_body / p_rng > 0.5
                and abs(p2c - p2o) / p2_rng(p2h, p2l) > 0.5
                and c < pc < p2c):
            patterns.append(_pat(t, "THREE_BLACK_CROWS", "bearish", 3,
                                 "Three Black Crows — silna kontynuacja spadku"))

    return patterns


def _pat(time, type_, direction, strength, description):
    return {"time": time, "type": type_, "direction": direction,
            "strength": strength, "description": description}


def p2_rng(h, l):
    return (h - l) or 1e-6


# ─── Support / Resistance ────────────────────────────────────────────────────

def _find_sr(df: pd.DataFrame, window: int = 8, n_levels: int = 10) -> list:
    n = len(df)
    current_price = float(df.iloc[-1].close)
    raw = []

    for i in range(window, n - window):
        row = df.iloc[i]
        win = df.iloc[i - window: i + window + 1]

        if row.high >= win.high.max():
            raw.append({"price": float(row.high), "type": "resistance",
                        "time": _ts(row["dt"]), "age": n - i})

        if row.low <= win.low.min():
            raw.append({"price": float(row.low), "type": "support",
                        "time": _ts(row["dt"]), "age": n - i})

    # Cluster levels within 0.6%
    merged = _cluster_levels(raw, tol=0.006)

    # Sort by proximity to current price
    merged.sort(key=lambda x: abs(x["price"] - current_price))
    return merged[:n_levels]


def _cluster_levels(levels: list, tol: float = 0.006) -> list:
    if not levels:
        return []

    levels = sorted(levels, key=lambda x: x["price"])
    clusters = []
    used = [False] * len(levels)

    for i, lev in enumerate(levels):
        if used[i]:
            continue
        group = [lev]
        for j in range(i + 1, len(levels)):
            if not used[j] and abs(levels[j]["price"] - lev["price"]) / lev["price"] <= tol:
                group.append(levels[j])
                used[j] = True
        used[i] = True

        avg_price = sum(g["price"] for g in group) / len(group)
        types = [g["type"] for g in group]
        dominant = "support" if types.count("support") >= types.count("resistance") else "resistance"
        # Most recent member
        youngest = min(group, key=lambda x: x["age"])

        clusters.append({
            "price": round(avg_price, 2),
            "type": dominant,
            "strength": len(group),
            "last_tested": youngest["time"],
            "age_bars": youngest["age"],
        })

    return clusters


# ─── Dywergencje ─────────────────────────────────────────────────────────────

def _divergences(df: pd.DataFrame, lookback: int = 60, sw_win: int = 5) -> list:
    recent = df.tail(lookback).reset_index(drop=True)
    n = len(recent)
    divs = []

    for i in range(sw_win, n):
        win = recent.iloc[i - sw_win: i + 1]
        t = _ts(recent.iloc[i]["dt"])

        # Price swing LOW (bullish divergence candidate)
        if recent.iloc[i].low <= win.low.min():
            search = recent.iloc[max(0, i - 40): i - sw_win]
            if len(search) < 3:
                continue
            prev_idx = search.low.idxmin()

            if recent.iloc[i].low < search.loc[prev_idx].low:   # price: lower low
                # RSI bullish divergence
                rsi_curr = recent.iloc[i].rsi
                rsi_prev = search.loc[prev_idx].rsi
                if pd.notna(rsi_curr) and pd.notna(rsi_prev) and rsi_curr > rsi_prev:
                    divs.append({
                        "time": t, "type": "bullish", "indicator": "RSI",
                        "description": f"Bycza dywergencja RSI: cena nowe dno ({recent.iloc[i].low:.0f}), RSI wyżej ({rsi_curr:.1f})",
                    })
                # MACD histogram bullish divergence
                m_curr = recent.iloc[i].macd_hist
                m_prev = search.loc[prev_idx].macd_hist
                if pd.notna(m_curr) and pd.notna(m_prev) and m_curr > m_prev:
                    divs.append({
                        "time": t, "type": "bullish", "indicator": "MACD",
                        "description": f"Bycza dywergencja MACD: cena nowe dno, histogram MACD wyżej",
                    })

        # Price swing HIGH (bearish divergence candidate)
        if recent.iloc[i].high >= win.high.max():
            search = recent.iloc[max(0, i - 40): i - sw_win]
            if len(search) < 3:
                continue
            prev_idx = search.high.idxmax()

            if recent.iloc[i].high > search.loc[prev_idx].high:  # price: higher high
                rsi_curr = recent.iloc[i].rsi
                rsi_prev = search.loc[prev_idx].rsi
                if pd.notna(rsi_curr) and pd.notna(rsi_prev) and rsi_curr < rsi_prev:
                    divs.append({
                        "time": t, "type": "bearish", "indicator": "RSI",
                        "description": f"Niedźwiedzia dywergencja RSI: cena nowy szczyt ({recent.iloc[i].high:.0f}), RSI niżej ({rsi_curr:.1f})",
                    })
                m_curr = recent.iloc[i].macd_hist
                m_prev = search.loc[prev_idx].macd_hist
                if pd.notna(m_curr) and pd.notna(m_prev) and m_curr < m_prev:
                    divs.append({
                        "time": t, "type": "bearish", "indicator": "MACD",
                        "description": f"Niedźwiedzia dywergencja MACD: cena nowy szczyt, histogram MACD niżej",
                    })

    # Deduplicate: one per (type, indicator) — keep most recent
    seen = {}
    for d in reversed(divs):
        key = (d["type"], d["indicator"])
        if key not in seen:
            seen[key] = d
    return list(reversed(seen.values()))


# ─── Price Action ─────────────────────────────────────────────────────────────

def _price_action(df: pd.DataFrame, sw_win: int = 8) -> dict:
    n = len(df)
    swing_highs = []
    swing_lows  = []

    for i in range(sw_win, n):
        win = df.iloc[max(0, i - sw_win): i + 1]
        row = df.iloc[i]
        if row.high >= win.high.max():
            swing_highs.append({"time": _ts(row["dt"]), "price": float(row.high), "idx": i})
        if row.low <= win.low.min():
            swing_lows.append({"time": _ts(row["dt"]), "price": float(row.low), "idx": i})

    # Struktura rynkowa z ostatnich 4 swingów
    hh = hl = lh = ll = False
    if len(swing_highs) >= 2:
        hh = swing_highs[-1]["price"] > swing_highs[-2]["price"]
        lh = swing_highs[-1]["price"] < swing_highs[-2]["price"]
    if len(swing_lows) >= 2:
        hl = swing_lows[-1]["price"] > swing_lows[-2]["price"]
        ll = swing_lows[-1]["price"] < swing_lows[-2]["price"]

    if hh and hl:
        structure = "UPTREND"
    elif lh and ll:
        structure = "DOWNTREND"
    else:
        structure = "RANGING"

    last_close = float(df.iloc[-1].close)
    last_time  = _ts(df.iloc[-1]["dt"])
    bos   = []
    choch = []

    # BOS — przebicie poprzedniego swing high/low
    if len(swing_highs) >= 2 and last_close > swing_highs[-2]["price"]:
        bos.append({
            "time": last_time, "direction": "bullish",
            "level": swing_highs[-2]["price"],
            "description": f"BOS wzrostowy: cena przebija swing high {swing_highs[-2]['price']:.0f}",
        })
    if len(swing_lows) >= 2 and last_close < swing_lows[-2]["price"]:
        bos.append({
            "time": last_time, "direction": "bearish",
            "level": swing_lows[-2]["price"],
            "description": f"BOS spadkowy: cena przebija swing low {swing_lows[-2]['price']:.0f}",
        })

    # CHOCH — zmiana struktury
    if structure == "UPTREND" and swing_lows and last_close < swing_lows[-1]["price"]:
        choch.append({
            "time": last_time, "direction": "bearish",
            "level": swing_lows[-1]["price"],
            "description": f"CHOCH niedźwiedzi: przebicie dna uptyrendu ({swing_lows[-1]['price']:.0f}) — potencjalne odwrócenie",
        })
    if structure == "DOWNTREND" and swing_highs and last_close > swing_highs[-1]["price"]:
        choch.append({
            "time": last_time, "direction": "bullish",
            "level": swing_highs[-1]["price"],
            "description": f"CHOCH bycza: przebicie szczytu downtrendu ({swing_highs[-1]['price']:.0f}) — potencjalne odwrócenie",
        })

    return {
        "structure": structure,
        "higher_highs": hh,
        "higher_lows": hl,
        "lower_highs": lh,
        "lower_lows": ll,
        "swing_highs": [{"time": s["time"], "price": s["price"]} for s in swing_highs[-6:]],
        "swing_lows":  [{"time": s["time"], "price": s["price"]} for s in swing_lows[-6:]],
        "bos":   bos,
        "choch": choch,
    }


# ─── Breakouty ───────────────────────────────────────────────────────────────

def _breakouts(df: pd.DataFrame, sr_levels: list) -> list:
    if len(df) < 2:
        return []

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    vol_sma = curr.vol_sma20 if curr.vol_sma20 and curr.vol_sma20 > 0 else None
    vol_ratio = float(curr.volume / vol_sma) if vol_sma else 1.0
    t = _ts(curr["dt"])
    breakouts = []

    for level in sr_levels:
        price = level["price"]
        # Bullish breakout above resistance
        if level["type"] == "resistance" and float(curr.close) > price >= float(prev.close):
            confirmed = vol_ratio >= 1.5
            breakouts.append({
                "time": t,
                "direction": "bullish",
                "level": price,
                "volume_ratio": round(vol_ratio, 2),
                "type": "CONFIRMED" if confirmed else "PENDING",
                "description": (
                    f"{'Potwierdzony' if confirmed else 'Oczekujący'} breakout wzrostowy "
                    f"powyżej {price:.0f} (wolumen {vol_ratio:.1f}×)"
                ),
            })
        # Bearish breakdown below support
        if level["type"] == "support" and float(curr.close) < price <= float(prev.close):
            confirmed = vol_ratio >= 1.5
            breakouts.append({
                "time": t,
                "direction": "bearish",
                "level": price,
                "volume_ratio": round(vol_ratio, 2),
                "type": "CONFIRMED" if confirmed else "PENDING",
                "description": (
                    f"{'Potwierdzony' if confirmed else 'Oczekujący'} breakdown "
                    f"poniżej {price:.0f} (wolumen {vol_ratio:.1f}×)"
                ),
            })

    return breakouts
