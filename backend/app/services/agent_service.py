"""
Agent Service — Faza 4.

Przepływ:
  run_analysis()
    → Trend Analyst   (IndicatorsService + RegimeService)
    → Pattern Analyst (PatternService)
    → Volume Analyst  (VolumeService)
    → Quant Analyst   (QuantService)
    → Orchestrator    (Claude API)
    → Risk Manager    (Claude API)
    → zapisz do historii, zwróć wynik

  chat(message, history)
    → Chat Agent (Claude API)
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

import anthropic

from app.core.config import get_settings
from app.services.indicators import IndicatorsService
from app.services.market_data import MarketDataService
from app.services.pattern_service import get_patterns
from app.services.quant_service import get_quant_snapshot
from app.services.volume_service import get_volume_analysis
from app.services import performance_service
from app.services.email_service import send_signal_alert

logger = logging.getLogger(__name__)

# ─── In-memory store ─────────────────────────────────────────────────────────

_signals_history: list[dict] = []
_position_state: dict = {
    "status": "FLAT",       # FLAT | LONG
    "entry_price": None,
    "entry_time": None,
    "stop_loss": None,
    "take_profit": None,
}

MAX_HISTORY = 50

# Auto-korekta progu confidence (Faza 6)
# Gdy win rate < 45% przez 30 dni → +5 do wymaganego confidence
_confidence_adjustment: int = 0


def get_signals_history() -> list[dict]:
    return _signals_history


def get_position() -> dict:
    return _position_state.copy()


# ─── Agenty algorytmiczne ─────────────────────────────────────────────────────

def _trend_analyst(interval: str) -> dict:
    try:
        settings = get_settings()
        svc = IndicatorsService(MarketDataService(finnhub_api_key=settings.finnhub_api_key))
        regime = svc.get_regime(interval=interval)
        inds   = svc.get_indicators(interval=interval, days=60)

        # Najnowsza wartość RSI i MACD histogram
        rsi_val  = inds["rsi"][-1]["value"]  if inds.get("rsi")  else None
        macd_pts = inds.get("macd", [])
        macd_h   = macd_pts[-1]["histogram"] if macd_pts else None
        adx_pts  = inds.get("adx",  [])
        adx_val  = adx_pts[-1]["adx"]        if adx_pts  else None

        return {
            "regime":          regime.get("regime", "UNKNOWN"),
            "confidence":      regime.get("confidence", 0),
            "rsi":             round(rsi_val,  2) if rsi_val  is not None else None,
            "macd_histogram":  round(macd_h,   4) if macd_h   is not None else None,
            "adx":             round(adx_val,  2) if adx_val  is not None else None,
            "above_sma50":     regime.get("above_sma_50",  False),
            "above_sma200":    regime.get("above_sma_200", False),
            "sma50":           regime.get("sma_50",  None),
            "sma200":          regime.get("sma_200", None),
            "current_price":   regime.get("price",   None),
            "error":           None,
        }
    except Exception as e:
        logger.error(f"Trend analyst error: {e}")
        return {"error": str(e)}


def _pattern_analyst(interval: str) -> dict:
    try:
        data = get_patterns(interval=interval, days=90)
        if "error" in data:
            return {"error": data["error"]}

        recent_pats = data["candle_patterns"][-5:] if data.get("candle_patterns") else []
        sr = data.get("support_resistance", [])
        current_price = data.get("current_price")

        # Znajdź najbliższy support i resistance
        price_ref = _position_state.get("entry_price")
        if price_ref is None and data.get("support_resistance"):
            pass  # use first levels

        supports    = [l for l in sr if l["type"] == "support"]
        resistances = [l for l in sr if l["type"] == "resistance"]

        pa = data.get("price_action", {})

        return {
            "recent_patterns":   [{"type": p["type"], "direction": p["direction"],
                                    "strength": p["strength"]} for p in recent_pats],
            "structure":         pa.get("structure", "UNKNOWN"),
            "bos":               pa.get("bos", []),
            "choch":             pa.get("choch", []),
            "divergences":       data.get("divergences", []),
            "nearest_support":   supports[0]    if supports    else None,
            "nearest_resistance":resistances[0] if resistances else None,
            "breakouts":         data.get("breakouts", []),
            "error":             None,
        }
    except Exception as e:
        logger.error(f"Pattern analyst error: {e}")
        return {"error": str(e)}


def _volume_analyst() -> dict:
    try:
        return get_volume_analysis(days=60)
    except Exception as e:
        logger.error(f"Volume analyst error: {e}")
        return {"error": str(e)}


def _quant_analyst() -> dict:
    try:
        snap = get_quant_snapshot()
        vol  = snap.get("volatility", {})
        stat = snap.get("statistical", {})
        brd  = snap.get("breadth", {})
        cross= snap.get("cross_market", {})
        return {
            "risk_score":       snap.get("risk_score"),
            "quant_signal":     snap.get("quant_signal"),
            "vix":              vol.get("vix"),
            "vix_regime":       vol.get("vix_regime"),
            "vix_term_structure": vol.get("vix_term_structure"),
            "pct_above_sma50":  brd.get("pct_above_sma50"),
            "pct_above_sma200": brd.get("pct_above_sma200"),
            "z_score_50d":      stat.get("z_score_50d"),
            "hurst":            stat.get("hurst_exponent"),
            "corr_sp500_tlt":   cross.get("corr_sp500_tlt_30d"),
            "credit_spread":    cross.get("credit_spread_30d"),
            "dxy_change_20d":   cross.get("dxy_change_20d"),
            "error":            None,
        }
    except Exception as e:
        logger.error(f"Quant analyst error: {e}")
        return {"error": str(e)}


# ─── Claude helpers ───────────────────────────────────────────────────────────

def _get_client() -> Optional[anthropic.Anthropic]:
    key = get_settings().anthropic_api_key
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def _parse_json(text: str) -> dict:
    """Wyodrębnij JSON z odpowiedzi Claude (może mieć markdown code block)."""
    text = text.strip()
    # Usuń ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ─── Orchestrator ─────────────────────────────────────────────────────────────

_ORCHESTRATOR_SYSTEM = """\
Jesteś profesjonalnym swing traderem analizującym S&P 500. Otrzymujesz raporty od 4 analityków \
i musisz podjąć decyzję: BUY / SELL / HOLD.

Zasady:
- NIE generuj BUY jeśli position_status to LONG.
- Próg pewności do działania: ≥ 65. Poniżej → HOLD.
- Korekty Risk Score: 0-20 (EXTREME_GREED) → -15 pewności dla BUY; \
80-100 (EXTREME_FEAR) → +10 dla BUY (contrarian); 60-80 (RISK_OFF) → -10 dla BUY.
- Jeśli pct_above_sma50 < 40: zablokuj BUY (dywergencja szerokości rynku).
- Stop loss: najbliższy support - 0,5%. Take profit: entry + 2× (entry - SL).

Odpowiedz wyłącznie prawidłowym JSON (bez markdown, bez tekstu poza JSON).
Pola "reasoning" i "key_factors" MUSZĄ być po polsku:
{
  "signal": "BUY"|"SELL"|"HOLD",
  "confidence": 0-100,
  "entry_price": float or null,
  "stop_loss": float or null,
  "take_profit": float or null,
  "reasoning": "wyjaśnienie w 2-3 zdaniach po polsku",
  "key_factors": ["czynnik1 po polsku", "czynnik2 po polsku", "czynnik3 po polsku"]
}\
"""


def _call_orchestrator(
    trend: dict, pattern: dict, volume: dict, quant: dict,
    position: dict, recent_signals: list,
    signal_outcomes: list, win_rate: Optional[float],
    confidence_adjustment: int,
) -> dict:
    client = _get_client()
    if client is None:
        return {"error": "ANTHROPIC_API_KEY nie skonfigurowany", "signal": "HOLD", "confidence": 0}

    context = {
        "position_status":       position.get("status", "FLAT"),
        "position_entry":        position.get("entry_price"),
        "trend_analyst":         trend,
        "pattern_analyst":       pattern,
        "volume_analyst":        volume,
        "quant_analyst":         quant,
        "recent_signals":        recent_signals[-5:] if recent_signals else [],
        "recent_signal_outcomes": [
            {"signal": s.get("signal"), "confidence": s.get("confidence"),
             "outcome": s.get("outcome"), "pnl_pct": s.get("outcome_pnl")}
            for s in (signal_outcomes[:10] if signal_outcomes else [])
        ],
        "win_rate_30d":          win_rate,
        "confidence_threshold":  65 + confidence_adjustment,
    }

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_ORCHESTRATOR_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(context, default=str)}],
        )
        return _parse_json(resp.content[0].text)
    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        return {"error": str(e), "signal": "HOLD", "confidence": 0}


# ─── Risk Manager ─────────────────────────────────────────────────────────────

_RISK_MANAGER_SYSTEM = """\
Jesteś zarządzającym ryzykiem w swing tradingu na S&P 500. Oceniasz proponowany sygnał.

Zasady:
- Minimalny stosunek R/R: 1:1,5 (odrzuć jeśli niższy)
- Maksymalne ryzyko na transakcję: 2% kapitału
- Jeśli VIX > 30: position_size_pct = 1,0 (redukcja o 50%)
- Jeśli pewność < 65: odrzuć

Odpowiedz wyłącznie prawidłowym JSON. Pole "notes" i "reject_reason" MUSZĄ być po polsku:
{
  "approved": true|false,
  "reject_reason": null or "powód odrzucenia po polsku",
  "position_size_pct": 1.0-2.0,
  "rr_ratio": float,
  "notes": "krótka notatka po polsku"
}\
"""


def _call_risk_manager(
    signal: dict, quant: dict, capital: float = 100_000.0
) -> dict:
    client = _get_client()
    if client is None:
        return {"approved": True, "position_size_pct": 2.0, "rr_ratio": 0.0,
                "reject_reason": None, "notes": "API key missing — auto-approved"}

    if signal.get("signal") == "HOLD" or signal.get("error"):
        return {"approved": True, "position_size_pct": 0.0, "rr_ratio": 0.0,
                "reject_reason": None, "notes": "HOLD — no trade"}

    entry = signal.get("entry_price") or 0
    sl    = signal.get("stop_loss")   or 0
    tp    = signal.get("take_profit") or 0
    risk  = abs(entry - sl) if entry and sl else 0
    reward= abs(tp - entry)  if tp and entry else 0

    context = {
        "proposed_signal":   signal.get("signal"),
        "confidence":        signal.get("confidence", 0),
        "entry_price":       entry,
        "stop_loss":         sl,
        "take_profit":       tp,
        "risk_per_share":    round(risk, 2),
        "reward_per_share":  round(reward, 2),
        "vix":               quant.get("vix"),
        "risk_score":        quant.get("risk_score"),
        "capital":           capital,
    }

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_RISK_MANAGER_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(context, default=str)}],
        )
        return _parse_json(resp.content[0].text)
    except Exception as e:
        logger.error(f"Risk manager error: {e}")
        return {"approved": True, "position_size_pct": 2.0, "rr_ratio": 0.0,
                "reject_reason": None, "notes": f"Błąd Risk Manager: {e}"}


# ─── Publiczne API ────────────────────────────────────────────────────────────

def run_analysis(interval: str = "1D") -> dict:
    """Pełna analiza: 4 agenty algorytmiczne → Orchestrator → Risk Manager."""
    logger.info(f"Starting analysis for interval={interval}")
    ts = datetime.now().isoformat()

    # 1. Agenty algorytmiczne
    trend   = _trend_analyst(interval)
    pattern = _pattern_analyst(interval)
    volume  = _volume_analyst()
    quant   = _quant_analyst()

    # 2. Feedback loop context
    signal_outcomes = performance_service.get_recent_outcomes(_signals_history, n=20)
    win_rate        = performance_service.get_win_rate(_signals_history, days=30)
    _update_confidence_adjustment(win_rate)

    # 3. Orchestrator (Claude)
    signal = _call_orchestrator(
        trend, pattern, volume, quant,
        _position_state, _signals_history,
        signal_outcomes, win_rate, _confidence_adjustment,
    )

    # 4. Risk Manager (Claude)
    risk = _call_risk_manager(signal, quant)

    # 5. Złóż wynik
    final_signal = signal.get("signal", "HOLD")
    approved     = risk.get("approved", True)

    # Jeśli Risk Manager odrzucił → zmień na HOLD
    if not approved:
        final_signal = "HOLD"

    result = {
        "id":              ts,
        "timestamp":       ts,
        "interval":        interval,
        "signal":          final_signal,
        "confidence":      signal.get("confidence", 0),
        "entry_price":     signal.get("entry_price"),
        "stop_loss":       signal.get("stop_loss"),
        "take_profit":     signal.get("take_profit"),
        "reasoning":       signal.get("reasoning", ""),
        "key_factors":     signal.get("key_factors", []),
        "risk_approved":   approved,
        "risk_reject_reason": risk.get("reject_reason"),
        "position_size_pct":  risk.get("position_size_pct", 2.0),
        "rr_ratio":           risk.get("rr_ratio", 0.0),
        "analysts": {
            "trend":   trend,
            "pattern": pattern,
            "volume":  volume,
            "quant":   quant,
        },
    }

    # 6. Zaktualizuj pozycję
    _update_position(result)

    # 7. Performance tracking
    performance_service.check_and_close_positions()
    if final_signal == "BUY" and approved:
        performance_service.open_position(result)

    # 8. Email alert
    if final_signal in ("BUY", "SELL"):
        send_signal_alert(result)

    # 9. Zapisz do historii
    _signals_history.insert(0, {
        "id":          ts,
        "timestamp":   ts,
        "interval":    interval,
        "signal":      final_signal,
        "confidence":  signal.get("confidence", 0),
        "entry_price": signal.get("entry_price"),
        "stop_loss":   signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "reasoning":   signal.get("reasoning", ""),
        "key_factors": signal.get("key_factors", []),
    })
    if len(_signals_history) > MAX_HISTORY:
        _signals_history.pop()

    return result


def _update_confidence_adjustment(win_rate: Optional[float]) -> None:
    global _confidence_adjustment
    if win_rate is None:
        return
    if win_rate < 45.0:
        _confidence_adjustment = min(_confidence_adjustment + 5, 20)
        logger.info(f"Auto-korekta: win rate {win_rate}% < 45% → confidence_adjustment={_confidence_adjustment}")
    elif win_rate >= 55.0:
        _confidence_adjustment = max(_confidence_adjustment - 5, 0)


def _update_position(result: dict):
    sig = result.get("signal")
    if sig == "BUY" and _position_state["status"] == "FLAT":
        _position_state.update({
            "status":      "LONG",
            "entry_price": result.get("entry_price"),
            "entry_time":  result.get("timestamp"),
            "stop_loss":   result.get("stop_loss"),
            "take_profit": result.get("take_profit"),
        })
    elif sig in ("SELL", "HOLD") and _position_state["status"] == "LONG":
        if sig == "SELL":
            _position_state.update({
                "status": "FLAT", "entry_price": None,
                "entry_time": None, "stop_loss": None, "take_profit": None,
            })


# ─── Chat Agent ───────────────────────────────────────────────────────────────

_CHAT_SYSTEM = """\
Jesteś profesjonalnym asystentem swing tradingu specjalizującym się w analizie S&P 500. \
Masz dostęp do aktualnych danych rynkowych i najnowszej analizy. \
Odpowiadaj zwięźle, rzeczowo i konkretnie. \
ZAWSZE odpowiadaj wyłącznie po polsku — nigdy po angielsku, rosyjsku ani żadnym innym języku.\
"""


def chat(message: str, history: list[dict] | None = None) -> str:
    client = _get_client()
    if client is None:
        return "⚠️ ANTHROPIC_API_KEY nie skonfigurowany. Dodaj klucz do pliku .env."

    # Zbuduj kontekst rynkowy
    pos = _position_state
    last_sig = _signals_history[0] if _signals_history else None
    try:
        quant_snap = get_quant_snapshot()
        vix   = quant_snap.get("volatility", {}).get("vix", "N/A")
        score = quant_snap.get("risk_score", "N/A")
        signal_str = quant_snap.get("quant_signal", "N/A")
    except Exception:
        vix, score, signal_str = "N/A", "N/A", "N/A"

    context = f"""Aktualny kontekst rynkowy:
- Pozycja: {pos['status']}{f" @ {pos['entry_price']}" if pos.get('entry_price') else ""}
- VIX: {vix} | Risk Score: {score} | Sygnał kwantowy: {signal_str}
- Ostatni sygnał AI: {last_sig['signal'] if last_sig else 'brak'} (pewność: {last_sig['confidence'] if last_sig else 0})
- SL: {pos.get('stop_loss')} | TP: {pos.get('take_profit')}
"""

    messages = []
    if history:
        for h in history[-6:]:  # ostatnie 6 wiadomości
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": f"{context}\n\nPytanie: {message}"})

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_CHAT_SYSTEM,
            messages=messages,
        )
        return resp.content[0].text
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return f"Błąd: {e}"
