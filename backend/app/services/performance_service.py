"""
Performance Service — Faza 5.

Śledzi wirtualne pozycje otwierane przez sygnały agenta AI.
Dane trzymane w pamięci (brak DB w tej fazie).

Przepływ:
  run_analysis() → BUY + approved → open_position()
  get_performance() → check_and_close_positions() → metryki + equity curve
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ─── Konfiguracja ─────────────────────────────────────────────────────────────

INITIAL_CAPITAL = 100_000.0   # $
EXPIRY_DAYS     = 10           # dni do auto-zamknięcia pozycji
TICKER          = "^GSPC"

# ─── Stan w pamięci ───────────────────────────────────────────────────────────

# Rejestr ocen sygnałów {signal_id → outcome}
_signal_outcomes: dict[str, dict] = {}

_portfolio: dict = {
    "initial_capital": INITIAL_CAPITAL,
    "closed_trades": [],   # list[dict]
    "open_positions": [],  # list[dict]  (max 1 w tej wersji)
    "equity_curve": [],    # list[{date, equity, benchmark}]
    "benchmark_entry": None,  # {date, price} – pierwszy trade wyznacza start benchmarka
}


# ─── API publiczne ────────────────────────────────────────────────────────────

def open_position(signal: dict) -> Optional[dict]:
    """Otwórz pozycję na podstawie zatwierdzonego sygnału BUY."""
    if _portfolio["open_positions"]:
        logger.info("Pozycja już otwarta — pomijam otwarcie nowej")
        return None

    entry_price = signal.get("entry_price")
    stop_loss   = signal.get("stop_loss")
    take_profit = signal.get("take_profit")
    size_pct    = signal.get("position_size_pct", 2.0)

    if not entry_price or not stop_loss:
        logger.warning("Brak entry_price lub stop_loss — nie otwieram pozycji")
        return None

    current_equity = _current_equity()
    capital_at_risk = current_equity * (size_pct / 100)
    shares = capital_at_risk / entry_price

    now = datetime.now(timezone.utc)
    pos = {
        "id":           signal.get("id", now.isoformat()),
        "signal_id":    signal.get("id"),
        "entry_date":   now.date().isoformat(),
        "entry_price":  entry_price,
        "stop_loss":    stop_loss,
        "take_profit":  take_profit,
        "size_pct":     size_pct,
        "shares":       shares,
        "capital_used": capital_at_risk,
        "expiry_date":  (now + timedelta(days=EXPIRY_DAYS)).date().isoformat(),
        "status":       "open",
    }
    _portfolio["open_positions"].append(pos)

    # Ustaw punkt startowy benchmarka przy pierwszym trade
    if _portfolio["benchmark_entry"] is None:
        _portfolio["benchmark_entry"] = {"date": now.date().isoformat(), "price": entry_price}

    logger.info(f"Otwarto pozycję: {shares:.4f} units @ {entry_price:.2f}, SL={stop_loss:.2f}, TP={take_profit}")
    return pos


def check_and_close_positions() -> list[dict]:
    """Sprawdź otwarte pozycje — zamknij te, które osiągnęły SL/TP/expiry."""
    closed = []
    remaining = []

    for pos in _portfolio["open_positions"]:
        result = _evaluate_position(pos)
        if result:
            _close_position(pos, **result)
            closed.append(pos)
        else:
            remaining.append(pos)

    _portfolio["open_positions"] = remaining
    return closed


def get_performance() -> dict:
    """Zwróć pełne dane performance: metryki, equity curve, pozycje."""
    check_and_close_positions()

    closed  = _portfolio["closed_trades"]
    open_p  = _portfolio["open_positions"]
    metrics = _compute_metrics(closed)
    equity_curve  = _build_equity_curve(closed)
    drawdown_curve = _build_drawdown(equity_curve)

    # Unrealized P&L dla otwartej pozycji
    unrealized = None
    if open_p:
        pos = open_p[0]
        price = _fetch_current_price()
        if price:
            pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
            unrealized = {
                "entry_price":  pos["entry_price"],
                "current_price": price,
                "pnl_pct":      round(pnl_pct, 2),
                "pnl_usd":      round(pos["shares"] * (price - pos["entry_price"]), 2),
                "stop_loss":    pos["stop_loss"],
                "take_profit":  pos["take_profit"],
                "expiry_date":  pos["expiry_date"],
                "days_open":    (datetime.now().date() - datetime.fromisoformat(pos["entry_date"]).date()).days,
            }

    return {
        "initial_capital": _portfolio["initial_capital"],
        "current_equity":  round(_current_equity(), 2),
        "total_return_pct": round((_current_equity() / _portfolio["initial_capital"] - 1) * 100, 2),
        "metrics":         metrics,
        "equity_curve":    equity_curve,
        "drawdown_curve":  drawdown_curve,
        "closed_trades":   list(reversed(closed)),   # najnowsze pierwsze
        "open_position":   unrealized,
        "benchmark_return_pct": _benchmark_return(),
    }


def set_initial_capital(amount: float) -> None:
    """Resetuj/ustaw kapitał startowy (resetuje też historię)."""
    _portfolio["initial_capital"] = amount
    _portfolio["closed_trades"]   = []
    _portfolio["open_positions"]  = []
    _portfolio["equity_curve"]    = []
    _portfolio["benchmark_entry"] = None


def evaluate_signal(signal_id: str, entry_date: str, entry_price: float,
                    stop_loss: Optional[float], take_profit: Optional[float]) -> dict:
    """
    Oceń sygnał BUY w oknie 5 dni wg reguł z planu:
      WIN      — TP hit przed SL LUB +2% przed SL
      LOSS     — SL hit przed TP LUB -1.5% przed TP
      BREAKEVEN— P&L w zakresie -0.3% do +0.3% po 5 dniach
      EXPIRED  — brak TP/SL w 5 dni, P&L na zamknięciu dnia 5
    """
    if signal_id in _signal_outcomes:
        return _signal_outcomes[signal_id]

    try:
        end = (datetime.fromisoformat(entry_date) + timedelta(days=8)).date().isoformat()
        df  = yf.download(TICKER, start=entry_date, end=end,
                          interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return {"outcome": "PENDING", "pnl_pct": None}

        bars = df.iloc[1:6]  # dni 1–5 po wejściu
        if len(bars) == 0:
            return {"outcome": "PENDING", "pnl_pct": None}

        WIN_PCT  =  2.0
        LOSS_PCT = -1.5

        for bar_date, row in bars.iterrows():
            high  = float(row["High"])
            low   = float(row["Low"])
            close = float(row["Close"])
            pnl_h = (high  - entry_price) / entry_price * 100
            pnl_l = (low   - entry_price) / entry_price * 100

            # TP hit
            if take_profit and high >= take_profit:
                outcome = {"outcome": "WIN", "reason": "TP", "pnl_pct": round((take_profit - entry_price) / entry_price * 100, 2), "close_date": str(bar_date.date())}
                _signal_outcomes[signal_id] = outcome
                return outcome
            # +2% hit before SL
            if pnl_h >= WIN_PCT and (stop_loss is None or low > stop_loss):
                outcome = {"outcome": "WIN", "reason": "+2%", "pnl_pct": round(WIN_PCT, 2), "close_date": str(bar_date.date())}
                _signal_outcomes[signal_id] = outcome
                return outcome
            # SL hit
            if stop_loss and low <= stop_loss:
                outcome = {"outcome": "LOSS", "reason": "SL", "pnl_pct": round((stop_loss - entry_price) / entry_price * 100, 2), "close_date": str(bar_date.date())}
                _signal_outcomes[signal_id] = outcome
                return outcome
            # -1.5% hit before TP
            if pnl_l <= LOSS_PCT:
                outcome = {"outcome": "LOSS", "reason": "-1.5%", "pnl_pct": round(LOSS_PCT, 2), "close_date": str(bar_date.date())}
                _signal_outcomes[signal_id] = outcome
                return outcome

        # Dzień 5 — expiry
        final_close = float(bars.iloc[-1]["Close"])
        pnl = (final_close - entry_price) / entry_price * 100
        if -0.3 <= pnl <= 0.3:
            outcome_label = "BREAKEVEN"
        else:
            outcome_label = "EXPIRED"
        outcome = {"outcome": outcome_label, "reason": "5d", "pnl_pct": round(pnl, 2), "close_date": str(bars.index[-1].date())}
        _signal_outcomes[signal_id] = outcome
        return outcome

    except Exception as e:
        logger.error(f"Błąd oceny sygnału {signal_id}: {e}")
        return {"outcome": "PENDING", "pnl_pct": None}


def get_recent_outcomes(signals_history: list, n: int = 20) -> list[dict]:
    """Zwróć ostatnie n sygnałów BUY z wynikami (do context injection)."""
    results = []
    for s in signals_history[:n]:
        if s.get("signal") != "BUY" or not s.get("entry_price"):
            results.append({**s, "outcome": "N/A", "outcome_pnl": None})
            continue
        ev = evaluate_signal(
            signal_id   = s["id"],
            entry_date  = s["timestamp"][:10],
            entry_price = s["entry_price"],
            stop_loss   = s.get("stop_loss"),
            take_profit = s.get("take_profit"),
        )
        results.append({**s, "outcome": ev["outcome"], "outcome_pnl": ev.get("pnl_pct")})
    return results


def get_win_rate(signals_history: list, days: int = 30) -> Optional[float]:
    """Win rate z ostatnich `days` dni (tylko zamknięte sygnały BUY)."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    evaluated = [
        s for s in signals_history
        if s.get("signal") == "BUY"
        and s.get("timestamp", "") >= cutoff
        and s.get("id") in _signal_outcomes
        and _signal_outcomes[s["id"]]["outcome"] not in ("PENDING",)
    ]
    if not evaluated:
        return None
    wins = sum(1 for s in evaluated if _signal_outcomes[s["id"]]["outcome"] == "WIN")
    return round(wins / len(evaluated) * 100, 1)


# ─── Logika wewnętrzna ────────────────────────────────────────────────────────

def _current_equity() -> float:
    base = _portfolio["initial_capital"]
    return base + sum(t["pnl_usd"] for t in _portfolio["closed_trades"])


def _evaluate_position(pos: dict) -> Optional[dict]:
    """
    Pobierz dane dzienne od entry_date do dziś.
    Sprawdź kolejno każdy bar: low <= SL → SL hit, high >= TP → TP hit,
    data >= expiry → zamknięcie po close.
    """
    try:
        entry_date = datetime.fromisoformat(pos["entry_date"]).date()
        today      = datetime.now().date()
        expiry     = datetime.fromisoformat(pos["expiry_date"]).date()

        fetch_end = (today + timedelta(days=1)).isoformat()
        df = yf.download(TICKER, start=pos["entry_date"], end=fetch_end,
                         interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return None

        # Pomiń pierwszy bar (bar wejścia — nie zamykamy w dniu otwarcia)
        bars = df.iloc[1:] if len(df) > 1 else df.iloc[0:0]

        for bar_date, row in bars.iterrows():
            bar_date = bar_date.date() if hasattr(bar_date, "date") else bar_date
            low  = float(row["Low"])
            high = float(row["High"])
            close = float(row["Close"])

            if low <= pos["stop_loss"]:
                return {"close_price": pos["stop_loss"], "close_date": str(bar_date), "close_reason": "SL"}
            if pos["take_profit"] and high >= pos["take_profit"]:
                return {"close_price": pos["take_profit"], "close_date": str(bar_date), "close_reason": "TP"}
            if bar_date >= expiry:
                return {"close_price": close, "close_date": str(bar_date), "close_reason": "EXPIRY"}

        # Pozycja nadal otwarta
        return None
    except Exception as e:
        logger.error(f"Błąd oceny pozycji: {e}")
        return None


def _close_position(pos: dict, close_price: float, close_date: str, close_reason: str) -> None:
    pnl_usd = pos["shares"] * (close_price - pos["entry_price"])
    pnl_pct = (close_price - pos["entry_price"]) / pos["entry_price"] * 100
    rr = None
    if pos.get("stop_loss") and pos.get("take_profit"):
        risk   = pos["entry_price"] - pos["stop_loss"]
        reward = pos["take_profit"] - pos["entry_price"]
        rr = round(reward / risk, 2) if risk > 0 else None

    pos.update({
        "status":       "closed",
        "close_date":   close_date,
        "close_price":  close_price,
        "close_reason": close_reason,
        "pnl_usd":      round(pnl_usd, 2),
        "pnl_pct":      round(pnl_pct, 2),
        "rr_actual":    rr,
        "win":          pnl_usd > 0,
    })
    _portfolio["closed_trades"].append(pos)
    logger.info(f"Zamknięto pozycję: {close_reason} @ {close_price:.2f}, P&L={pnl_usd:.2f} ({pnl_pct:.2f}%)")


def _compute_metrics(trades: list) -> dict:
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0, "avg_pnl_pct": 0,
            "avg_win_pct": 0, "avg_loss_pct": 0, "avg_rr": 0,
            "max_drawdown_pct": 0, "sharpe": 0, "profit_factor": 0,
        }

    wins   = [t for t in trades if t["win"]]
    losses = [t for t in trades if not t["win"]]
    pnls   = [t["pnl_pct"] for t in trades]

    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss   = abs(sum(t["pnl_usd"] for t in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    # Sharpe (annualized, daily returns, rf=0)
    sharpe = 0.0
    if len(pnls) >= 2:
        mean_r = sum(pnls) / len(pnls)
        std_r  = math.sqrt(sum((r - mean_r) ** 2 for r in pnls) / (len(pnls) - 1))
        if std_r > 0:
            sharpe = round((mean_r / std_r) * math.sqrt(252 / 10), 2)  # ~10 days/trade

    return {
        "total_trades":   len(trades),
        "win_rate":       round(len(wins) / len(trades) * 100, 1),
        "avg_pnl_pct":    round(sum(pnls) / len(pnls), 2),
        "avg_win_pct":    round(sum(t["pnl_pct"] for t in wins)   / len(wins),   2) if wins   else 0,
        "avg_loss_pct":   round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
        "profit_factor":  profit_factor,
        "sharpe":         sharpe,
    }


def _build_equity_curve(trades: list) -> list[dict]:
    """Equity curve jako lista {date, equity, benchmark}."""
    if not trades:
        return []

    equity = _portfolio["initial_capital"]
    points = [{"date": trades[0]["entry_date"], "equity": round(equity, 2), "benchmark": None}]

    bench_price_start = _portfolio["benchmark_entry"]["price"] if _portfolio["benchmark_entry"] else None

    sorted_trades = sorted(trades, key=lambda t: t.get("close_date", ""))
    for t in sorted_trades:
        equity += t["pnl_usd"]
        bench = None
        if bench_price_start:
            # Pobierz cenę S&P w dniu zamknięcia transakcji
            bench_price = _fetch_price_on_date(t["close_date"])
            if bench_price:
                bench = round(_portfolio["initial_capital"] * bench_price / bench_price_start, 2)
        points.append({"date": t["close_date"], "equity": round(equity, 2), "benchmark": bench})

    return points


def _build_drawdown(equity_curve: list) -> list[dict]:
    if not equity_curve:
        return []
    peak = equity_curve[0]["equity"]
    result = []
    for p in equity_curve:
        if p["equity"] > peak:
            peak = p["equity"]
        dd = (p["equity"] - peak) / peak * 100
        result.append({"date": p["date"], "drawdown": round(dd, 2)})
    return result


def _benchmark_return() -> Optional[float]:
    if not _portfolio["benchmark_entry"] or not _portfolio["closed_trades"]:
        return None
    start_price = _portfolio["benchmark_entry"]["price"]
    current = _fetch_current_price()
    if current and start_price:
        return round((current / start_price - 1) * 100, 2)
    return None


def _fetch_current_price() -> Optional[float]:
    try:
        df = yf.download(TICKER, period="2d", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _fetch_price_on_date(date_str: str) -> Optional[float]:
    try:
        end = (datetime.fromisoformat(date_str) + timedelta(days=2)).date().isoformat()
        df  = yf.download(TICKER, start=date_str, end=end,
                          interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            return float(df["Close"].iloc[0])
    except Exception:
        pass
    return None
