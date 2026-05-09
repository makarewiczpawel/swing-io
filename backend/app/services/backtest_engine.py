"""
Silnik backtestingowy dla swing.io.

Architektura:
- Strategie: RSI_OVERSOLD, MACD_CROSSOVER, SMA_CROSSOVER, BB_REVERSION (Trend)
             BULLISH_ENGULFING, MORNING_STAR (Pattern)
             VOLUME_BREAKOUT (Volume)
- Symulacja LONG-only z prowizją i slippage
- max_hold_bars: wymuszony limit czasu trwania pozycji
- Podział train/test z detekcją overfittingu
- Walk-forward testing (7 rund)
"""

import pandas as pd
import numpy as np
import ta
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100_000.0
COMMISSION = 0.001   # 0.1% per side
SLIPPAGE = 0.0005    # 0.05% per side

STRATEGIES = {
    "RSI_OVERSOLD": {
        "description": "BUY gdy RSI < próg wyprzedania, SELL gdy RSI > próg wykupienia",
        "default_params": {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
        "param_labels": {
            "rsi_period": {"label": "Okres RSI", "min": 5, "max": 50, "step": 1},
            "rsi_oversold": {"label": "Próg wyprzedania", "min": 10, "max": 45, "step": 1},
            "rsi_overbought": {"label": "Próg wykupienia", "min": 55, "max": 90, "step": 1},
        },
    },
    "MACD_CROSSOVER": {
        "description": "BUY gdy MACD przekroczy linię sygnału od dołu (bullish crossover)",
        "default_params": {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9},
        "param_labels": {
            "macd_fast": {"label": "MACD Fast", "min": 5, "max": 20, "step": 1},
            "macd_slow": {"label": "MACD Slow", "min": 15, "max": 50, "step": 1},
            "macd_signal": {"label": "MACD Signal", "min": 3, "max": 15, "step": 1},
        },
    },
    "SMA_CROSSOVER": {
        "description": "BUY na Golden Cross (SMA50 > SMA200), SELL na Death Cross",
        "default_params": {"sma_fast": 50, "sma_slow": 200},
        "param_labels": {
            "sma_fast": {"label": "SMA Fast", "min": 10, "max": 100, "step": 5},
            "sma_slow": {"label": "SMA Slow", "min": 50, "max": 300, "step": 10},
        },
    },
    "BB_REVERSION": {
        "description": "BUY gdy cena zamknie się poniżej dolnego BB, SELL gdy powyżej górnego BB",
        "default_params": {"bb_period": 20, "bb_std": 2},
        "param_labels": {
            "bb_period": {"label": "Okres BB", "min": 10, "max": 50, "step": 1},
            "bb_std": {"label": "Odch. std.", "min": 1, "max": 3, "step": 0.5},
        },
    },

    # ── Pattern strategies ─────────────────────────────────────────
    "BULLISH_ENGULFING": {
        "description": "BUY na Bullish Engulfing, SELL na Bearish Engulfing lub RSI > próg",
        "default_params": {"rsi_period": 14, "rsi_overbought": 70, "hold_bars": 15},
        "param_labels": {
            "rsi_period":    {"label": "Okres RSI",               "min": 5,  "max": 30, "step": 1},
            "rsi_overbought":{"label": "RSI wyjście",             "min": 55, "max": 85, "step": 1},
            "hold_bars":     {"label": "Max. czas trwania (świece)", "min": 5,  "max": 40, "step": 5},
        },
    },
    "MORNING_STAR": {
        "description": "BUY na Morning Star (3-świecowy), SELL na Evening Star lub RSI > próg",
        "default_params": {"rsi_exit": 65, "hold_bars": 15},
        "param_labels": {
            "rsi_exit": {"label": "RSI wyjście",               "min": 55, "max": 80, "step": 1},
            "hold_bars":{"label": "Max. czas trwania (świece)", "min": 5,  "max": 40, "step": 5},
        },
    },

    # ── Volume strategies ──────────────────────────────────────────
    "VOLUME_BREAKOUT": {
        "description": "BUY gdy cena bije N-dniowy szczyt z wolumenem > X× SMA20, SELL gdy spadek poniżej EMA10",
        "default_params": {"lookback": 20, "vol_mult": 1.5, "hold_bars": 20},
        "param_labels": {
            "lookback":  {"label": "Lookback szczyt (świece)", "min": 10, "max": 60, "step": 5},
            "vol_mult":  {"label": "Mnożnik wolumenu",        "min": 1.0, "max": 3.0, "step": 0.1},
            "hold_bars": {"label": "Max. czas trwania",       "min": 5,  "max": 40, "step": 5},
        },
    },
}

WALK_FORWARD_ROUNDS = [
    {"train_from": "2010-01-01", "train_to": "2018-12-31", "test_from": "2019-01-01", "test_to": "2019-12-31"},
    {"train_from": "2011-01-01", "train_to": "2019-12-31", "test_from": "2020-01-01", "test_to": "2020-12-31"},
    {"train_from": "2012-01-01", "train_to": "2020-12-31", "test_from": "2021-01-01", "test_to": "2021-12-31"},
    {"train_from": "2013-01-01", "train_to": "2021-12-31", "test_from": "2022-01-01", "test_to": "2022-12-31"},
    {"train_from": "2014-01-01", "train_to": "2022-12-31", "test_from": "2023-01-01", "test_to": "2023-12-31"},
    {"train_from": "2015-01-01", "train_to": "2023-12-31", "test_from": "2024-01-01", "test_to": "2024-12-31"},
    {"train_from": "2016-01-01", "train_to": "2024-12-31", "test_from": "2025-01-01", "test_to": "2025-12-31"},
]


# ─── Dane ───────────────────────────────────────────────────────────

def _fetch_df(from_date: str, to_date: str, interval: str = "1D") -> pd.DataFrame:
    """Pobierz dane OHLCV z yfinance z buforem na warmup wskaźników."""
    warmup = timedelta(days=300)
    start = datetime.strptime(from_date, "%Y-%m-%d") - warmup

    yf_map = {"1D": "1d", "1W": "1wk", "4h": "1h", "1h": "1h"}
    df = yf.Ticker("^GSPC").history(
        start=start.strftime("%Y-%m-%d"),
        end=to_date,
        interval=yf_map.get(interval, "1d"),
        auto_adjust=True,
    )

    if df.empty:
        return df

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    return df


# ─── Wskaźniki i sygnały ─────────────────────────────────────────────

def _compute_indicators(df: pd.DataFrame, strategy: str, params: dict) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    o = df["Open"]
    h = df["High"]
    lo = df["Low"]

    if strategy == "RSI_OVERSOLD":
        df["rsi"] = ta.momentum.RSIIndicator(c, window=int(params["rsi_period"])).rsi()

    elif strategy == "MACD_CROSSOVER":
        m = ta.trend.MACD(c, window_fast=int(params["macd_fast"]),
                          window_slow=int(params["macd_slow"]),
                          window_sign=int(params["macd_signal"]))
        df["macd"] = m.macd()
        df["macd_sig"] = m.macd_signal()

    elif strategy == "SMA_CROSSOVER":
        df["sma_fast"] = ta.trend.SMAIndicator(c, window=int(params["sma_fast"])).sma_indicator()
        df["sma_slow"] = ta.trend.SMAIndicator(c, window=int(params["sma_slow"])).sma_indicator()

    elif strategy == "BB_REVERSION":
        bb = ta.volatility.BollingerBands(c, window=int(params["bb_period"]),
                                          window_dev=float(params["bb_std"]))
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()

    elif strategy == "BULLISH_ENGULFING":
        body     = (c - o).abs()
        prev_c   = c.shift(1)
        prev_o   = o.shift(1)
        prev_body = body.shift(1)
        df["bullish_eng"] = (
            (prev_c < prev_o) & (c > o) &        # prev bearish, curr bullish
            (o <= prev_c) & (c >= prev_o) &       # curr engulfs prev
            (body > prev_body)
        )
        df["bearish_eng"] = (
            (prev_c > prev_o) & (c < o) &
            (o >= prev_c) & (c <= prev_o) &
            (body > prev_body)
        )
        df["rsi"] = ta.momentum.RSIIndicator(c, window=int(params.get("rsi_period", 14))).rsi()

    elif strategy == "MORNING_STAR":
        body = (c - o).abs()
        rng  = (h - lo).replace(0, 1e-6)
        p2_bear    = (c.shift(2) < o.shift(2)) & (body.shift(2) / rng.shift(2) > 0.5)
        p1_small   = (body.shift(1) / rng.shift(1) < 0.35)
        curr_bull  = (c > o) & (body / rng > 0.45) & (c > (o.shift(2) + c.shift(2)) / 2)
        df["morning_star"] = p2_bear & p1_small & curr_bull

        p2_bull    = (c.shift(2) > o.shift(2)) & (body.shift(2) / rng.shift(2) > 0.5)
        curr_bear  = (c < o) & (body / rng > 0.45) & (c < (o.shift(2) + c.shift(2)) / 2)
        df["evening_star"] = p2_bull & p1_small & curr_bear
        df["rsi"] = ta.momentum.RSIIndicator(c, window=14).rsi()

    elif strategy == "VOLUME_BREAKOUT":
        lookback = int(params.get("lookback", 20))
        vol_mult = float(params.get("vol_mult", 1.5))
        df["rolling_max"] = h.shift(1).rolling(lookback).max()
        df["vol_sma20"]   = df["Volume"].rolling(20).mean()
        df["breakout"]    = (c > df["rolling_max"]) & (df["Volume"] > df["vol_sma20"] * vol_mult)
        df["ema10"]       = ta.trend.EMAIndicator(c, window=10).ema_indicator()

    return df.dropna()


def _signals(df: pd.DataFrame, strategy: str, params: dict) -> pd.Series:
    """Zwróć Series: 1=BUY, -1=SELL, 0=HOLD."""
    s = pd.Series(0, index=df.index)

    if strategy == "RSI_OVERSOLD":
        s[df["rsi"] < params["rsi_oversold"]] = 1
        s[df["rsi"] > params["rsi_overbought"]] = -1

    elif strategy == "MACD_CROSSOVER":
        prev_m, prev_s = df["macd"].shift(1), df["macd_sig"].shift(1)
        s[(df["macd"] > df["macd_sig"]) & (prev_m <= prev_s)] = 1
        s[(df["macd"] < df["macd_sig"]) & (prev_m >= prev_s)] = -1

    elif strategy == "SMA_CROSSOVER":
        prev_f, prev_sl = df["sma_fast"].shift(1), df["sma_slow"].shift(1)
        s[(df["sma_fast"] > df["sma_slow"]) & (prev_f <= prev_sl)] = 1
        s[(df["sma_fast"] < df["sma_slow"]) & (prev_f >= prev_sl)] = -1

    elif strategy == "BB_REVERSION":
        s[df["Close"] < df["bb_lower"]] = 1
        s[df["Close"] > df["bb_upper"]] = -1

    elif strategy == "BULLISH_ENGULFING":
        rsi_exit = float(params.get("rsi_overbought", 70))
        s[df["bullish_eng"]] = 1
        s[df["bearish_eng"] | (df["rsi"] > rsi_exit)] = -1

    elif strategy == "MORNING_STAR":
        rsi_exit = float(params.get("rsi_exit", 65))
        s[df["morning_star"]] = 1
        s[df["evening_star"] | (df["rsi"] > rsi_exit)] = -1

    elif strategy == "VOLUME_BREAKOUT":
        s[df["breakout"]] = 1
        s[df["Close"] < df["ema10"]] = -1

    return s


# ─── Symulacja ───────────────────────────────────────────────────────

def _simulate(
    df: pd.DataFrame,
    sig: pd.Series,
    initial_capital: float = INITIAL_CAPITAL,
    commission: float = COMMISSION,
    slippage: float = SLIPPAGE,
    max_hold_bars: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Symulacja LONG-only.
    Wejście na OPEN świecy i+1 po sygnale na świecy i.
    max_hold_bars: wymuś zamknięcie pozycji po N barach.
    """
    capital = initial_capital
    pos = None  # None = flat | dict = open long
    trades: list[dict] = []
    equity: list[dict] = []

    opens = df["Open"].values
    closes = df["Close"].values
    idx = df.index
    sigs = sig.values

    for i in range(len(df) - 1):
        bar_sig = sigs[i]
        # Wymuś wyjście po max_hold_bars świecach
        if pos is not None and max_hold_bars is not None:
            if (i - pos["entry_bar"]) >= max_hold_bars:
                bar_sig = -1

        next_open = opens[i + 1]
        ts = int(idx[i + 1].timestamp()) if hasattr(idx[i + 1], "timestamp") else int(pd.Timestamp(idx[i + 1]).timestamp())

        # Wejście
        if bar_sig == 1 and pos is None:
            entry_px = next_open * (1 + slippage)
            shares = (capital * (1 - commission)) / entry_px
            pos = {
                "entry_date": str(idx[i + 1])[:10],
                "entry_ts": ts,
                "entry_px": round(entry_px, 2),
                "shares": shares,
                "capital_at_entry": capital,
                "entry_bar": i + 1,
            }
            capital = 0.0

        # Wyjście
        elif bar_sig == -1 and pos is not None:
            exit_px = next_open * (1 - slippage)
            gross = pos["shares"] * exit_px
            net = gross * (1 - commission)
            pnl_pct = (net / pos["capital_at_entry"] - 1) * 100

            trades.append({
                "entry_date": pos["entry_date"],
                "exit_date": str(idx[i + 1])[:10],
                "entry_price": pos["entry_px"],
                "exit_price": round(exit_px, 2),
                "pnl_pct": round(pnl_pct, 3),
                "pnl_amount": round(net - pos["capital_at_entry"], 2),
                "bars_held": (i + 1) - pos["entry_bar"],
                "exit_reason": "SIGNAL",
            })
            capital = net
            pos = None

        # Equity curve
        if pos is not None:
            equity.append({"time": ts, "value": round(pos["shares"] * closes[i + 1], 2)})
        else:
            equity.append({"time": ts, "value": round(capital, 2)})

    # Zamknij otwartą pozycję na końcu okresu
    if pos is not None:
        exit_px = closes[-1] * (1 - slippage)
        gross = pos["shares"] * exit_px
        net = gross * (1 - commission)
        pnl_pct = (net / pos["capital_at_entry"] - 1) * 100
        trades.append({
            "entry_date": pos["entry_date"],
            "exit_date": str(idx[-1])[:10],
            "entry_price": pos["entry_px"],
            "exit_price": round(exit_px, 2),
            "pnl_pct": round(pnl_pct, 3),
            "pnl_amount": round(net - pos["capital_at_entry"], 2),
            "bars_held": len(df) - pos["entry_bar"],
            "exit_reason": "EOD",
        })
        capital = net

    return trades, equity


# ─── Metryki ─────────────────────────────────────────────────────────

def _metrics(trades: list[dict], equity: list[dict], initial_capital: float) -> dict:
    if not trades:
        return {
            "total_trades": 0, "winning_trades": 0, "win_rate": 0.0,
            "profit_factor": 0.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0,
            "total_return_pct": 0.0, "avg_trade_duration_bars": 0.0,
            "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
            "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
        }

    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else (999.0 if wins else 0.0)

    # Sharpe z dziennych stóp zwrotu equity curve (poprawna metoda)
    equities = pd.Series([e["value"] for e in equity])
    daily_returns = equities.pct_change().dropna()
    sharpe = float(daily_returns.mean() / daily_returns.std() * (252 ** 0.5)) if len(daily_returns) > 1 and daily_returns.std() > 0 else 0.0

    peak = equities.cummax()
    max_dd = float(((equities - peak) / peak * 100).min()) if len(equities) > 0 else 0.0

    final = equity[-1]["value"] if equity else initial_capital
    total_return = (final / initial_capital - 1) * 100

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(min(profit_factor, 999.0), 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "total_return_pct": round(total_return, 2),
        "avg_trade_duration_bars": round(sum(t["bars_held"] for t in trades) / len(trades), 1),
        "avg_win_pct": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss_pct": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "best_trade_pct": round(max(pnls), 2),
        "worst_trade_pct": round(min(pnls), 2),
    }


# ─── Publiczne API ───────────────────────────────────────────────────

def run_backtest(
    strategy: str,
    interval: str = "1D",
    train_from: str = "2010-01-01",
    train_to: str = "2021-12-31",
    test_from: str = "2022-01-01",
    test_to: str = "2026-12-31",
    params: dict | None = None,
    initial_capital: float = INITIAL_CAPITAL,
    commission_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> dict:
    """Uruchom backtest z podziałem train/test. Zwróć wyniki + detekcja overfittingu."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Nieznana strategia: {strategy}")

    params = params or STRATEGIES[strategy]["default_params"].copy()
    commission = commission_pct / 100
    slippage = slippage_pct / 100

    # Fetch raz dla obu zbiorów
    df_all = _fetch_df(train_from, test_to, interval)
    if df_all.empty:
        raise RuntimeError("Brak danych z yfinance")

    df_all = _compute_indicators(df_all, strategy, params)

    train_mask = (df_all.index >= pd.Timestamp(train_from)) & (df_all.index <= pd.Timestamp(train_to))
    test_mask  = (df_all.index >= pd.Timestamp(test_from))  & (df_all.index <= pd.Timestamp(test_to))

    df_train = df_all[train_mask]
    df_test  = df_all[test_mask]

    logger.info(f"Backtest {strategy} | train={len(df_train)} bars | test={len(df_test)} bars")

    max_hold = int(params["hold_bars"]) if "hold_bars" in params else None
    train_trades, train_eq = _simulate(df_train, _signals(df_train, strategy, params), initial_capital, commission, slippage, max_hold)
    test_trades,  test_eq  = _simulate(df_test,  _signals(df_test,  strategy, params), initial_capital, commission, slippage, max_hold)

    train_m = _metrics(train_trades, train_eq, initial_capital)
    test_m  = _metrics(test_trades,  test_eq,  initial_capital)

    # Detekcja overfittingu
    deg_win = None
    deg_sharpe = None
    is_overfit = False

    if train_m["win_rate"] > 0:
        deg_win = round((train_m["win_rate"] - test_m["win_rate"]) / train_m["win_rate"] * 100, 1)
        if deg_win > 20:
            is_overfit = True

    if train_m["sharpe_ratio"] > 0:
        deg_sharpe = round((train_m["sharpe_ratio"] - test_m["sharpe_ratio"]) / train_m["sharpe_ratio"] * 100, 1)
        if deg_sharpe > 30:
            is_overfit = True

    return {
        "strategy": strategy,
        "strategy_description": STRATEGIES[strategy]["description"],
        "interval": interval,
        "params": params,
        "train_from": train_from,
        "train_to": train_to,
        "test_from": test_from,
        "test_to": test_to,
        "initial_capital": initial_capital,
        "commission_pct": commission_pct,
        "slippage_pct": slippage_pct,
        "train_metrics": train_m,
        "test_metrics": test_m,
        "train_equity": train_eq,
        "test_equity": test_eq,
        "train_trades": train_trades,
        "test_trades": test_trades,
        "degradation_win_rate": deg_win,
        "degradation_sharpe": deg_sharpe,
        "is_overfit": is_overfit,
    }


def run_walk_forward(
    strategy: str,
    interval: str = "1D",
    params: dict | None = None,
    initial_capital: float = INITIAL_CAPITAL,
) -> dict:
    """Walk-forward testing — 7 rund przesuwającego się okna."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Nieznana strategia: {strategy}")

    params = params or STRATEGIES[strategy]["default_params"].copy()

    # Fetch raz — pokrywa cały zakres 2010–2025
    df_all = _fetch_df("2010-01-01", "2026-01-01", interval)
    if df_all.empty:
        raise RuntimeError("Brak danych z yfinance")
    df_all = _compute_indicators(df_all, strategy, params)

    results = []
    for i, r in enumerate(WALK_FORWARD_ROUNDS):
        try:
            tm = (df_all.index >= pd.Timestamp(r["train_from"])) & (df_all.index <= pd.Timestamp(r["train_to"]))
            te = (df_all.index >= pd.Timestamp(r["test_from"]))  & (df_all.index <= pd.Timestamp(r["test_to"]))
            df_tr = df_all[tm]
            df_te = df_all[te]

            max_hold = int(params["hold_bars"]) if "hold_bars" in params else None
            tr_trades, tr_eq = _simulate(df_tr, _signals(df_tr, strategy, params), initial_capital, max_hold_bars=max_hold)
            te_trades, te_eq = _simulate(df_te, _signals(df_te, strategy, params), initial_capital, max_hold_bars=max_hold)
            tr_m = _metrics(tr_trades, tr_eq, initial_capital)
            te_m = _metrics(te_trades, te_eq, initial_capital)

            deg = None
            if tr_m["win_rate"] > 0:
                deg = round((tr_m["win_rate"] - te_m["win_rate"]) / tr_m["win_rate"] * 100, 1)

            results.append({
                "round": i + 1,
                "train_from": r["train_from"], "train_to": r["train_to"],
                "test_from": r["test_from"],   "test_to": r["test_to"],
                "train_win_rate": tr_m["win_rate"],
                "test_win_rate":  te_m["win_rate"],
                "test_return_pct": te_m["total_return_pct"],
                "test_sharpe": te_m["sharpe_ratio"],
                "test_max_drawdown": te_m["max_drawdown_pct"],
                "test_total_trades": te_m["total_trades"],
                "degradation_win_rate": deg,
                "is_overfit": deg is not None and deg > 20,
            })
        except Exception as e:
            logger.warning(f"Walk-forward runda {i+1} błąd: {e}")
            results.append({"round": i + 1, "error": str(e)})

    valid = [r for r in results if "error" not in r]
    return {
        "strategy": strategy,
        "rounds": results,
        "summary": {
            "avg_test_win_rate": round(sum(r["test_win_rate"] for r in valid) / len(valid), 1) if valid else 0,
            "avg_test_return_pct": round(sum(r["test_return_pct"] for r in valid) / len(valid), 2) if valid else 0,
            "avg_test_sharpe": round(sum(r["test_sharpe"] for r in valid) / len(valid), 2) if valid else 0,
            "overfit_rounds": sum(1 for r in valid if r.get("is_overfit")),
            "total_rounds": len(results),
            "robust": all(not r.get("is_overfit") for r in valid),
        },
    }
