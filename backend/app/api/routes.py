"""API routes for S&P 500 market data."""

from fastapi import APIRouter, Query, HTTPException
from app.models.schemas import (
    CandlesResponse, QuoteResponse, MarketInfoResponse,
    IndicatorsResponse, RegimeResponse,
    BacktestRequest, WalkForwardRequest,
)
from app.services.market_data import MarketDataService
from app.services.indicators import IndicatorsService
from app.services.backtest_engine import (
    run_backtest, run_walk_forward, STRATEGIES,
)
from app.services.quant_service import (
    get_quant_snapshot, get_risk_score,
    get_vix_history, get_zscore_history, get_correlations_history,
)
from app.services.pattern_service import get_patterns
from app.services.agent_service import (
    run_analysis, chat as agent_chat,
    get_signals_history, get_position,
)
from app.services.performance_service import (
    get_performance, set_initial_capital, get_win_rate,
)
from app.services import email_service, state_store
from app.core.config import get_settings
from typing import Optional
import uuid, logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["market"])

# Singletony serwisów
_market_service: Optional[MarketDataService] = None
_indicators_service: Optional[IndicatorsService] = None

# Cache wyników backtestów (file-backed)
_backtest_results: dict = state_store.load("backtest_results") or {}


def get_market_service() -> MarketDataService:
    global _market_service
    if _market_service is None:
        settings = get_settings()
        _market_service = MarketDataService(
            finnhub_api_key=settings.finnhub_api_key
        )
    return _market_service


def get_indicators_service() -> IndicatorsService:
    global _indicators_service
    if _indicators_service is None:
        _indicators_service = IndicatorsService(get_market_service())
    return _indicators_service


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/candles", response_model=CandlesResponse)
def get_candles(
    interval: str = Query(
        default="1D",
        pattern="^(1h|4h|1D|1W)$",
        description="Interwał: 1h, 4h, 1D, 1W",
    ),
    days: int = Query(
        default=365,
        ge=1,
        le=3650,
        description="Ile dni wstecz",
    ),
    start: Optional[str] = Query(
        default=None,
        description="Data początkowa YYYY-MM-DD",
    ),
    end: Optional[str] = Query(
        default=None,
        description="Data końcowa YYYY-MM-DD",
    ),
):
    """Pobierz świece S&P 500 dla danego interwału."""
    try:
        service = get_market_service()
        candles = service.get_candles(
            interval=interval,
            days_back=days,
            start_date=start,
            end_date=end,
        )
        return CandlesResponse(
            interval=interval,
            count=len(candles),
            candles=candles,
        )
    except Exception as e:
        logger.error(f"Error in /candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote", response_model=QuoteResponse)
async def get_quote():
    """Pobierz aktualną cenę S&P 500."""
    try:
        service = get_market_service()
        quote = await service.get_current_quote()
        return QuoteResponse(**quote)
    except Exception as e:
        logger.error(f"Error in /quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-info", response_model=MarketInfoResponse)
def get_market_info():
    """Pobierz informacje o S&P 500 (52w high/low, SMA)."""
    try:
        service = get_market_service()
        info = service.get_market_info()
        if "error" in info:
            raise HTTPException(status_code=500, detail=info["error"])
        return MarketInfoResponse(**info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /market-info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicators", response_model=IndicatorsResponse)
def get_indicators(
    interval: str = Query(
        default="1D",
        pattern="^(1h|4h|1D|1W)$",
        description="Interwał: 1h, 4h, 1D, 1W",
    ),
    days: int = Query(
        default=365,
        ge=30,
        le=3650,
        description="Ile dni wstecz",
    ),
):
    """Pobierz wskaźniki techniczne (SMA, EMA, RSI, MACD, BB, ADX)."""
    try:
        svc = get_indicators_service()
        data = svc.get_indicators(interval=interval, days=days)
        return IndicatorsResponse(
            interval=interval,
            days=days,
            sma=data.get("sma", {}),
            ema=data.get("ema", {}),
            rsi=data.get("rsi", []),
            macd=data.get("macd", []),
            bb=data.get("bb", []),
            adx=data.get("adx", []),
        )
    except Exception as e:
        logger.error(f"Error in /indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime/current", response_model=RegimeResponse)
def get_regime(
    interval: str = Query(
        default="1D",
        pattern="^(1h|4h|1D|1W)$",
        description="Interwał: 1h, 4h, 1D, 1W",
    ),
):
    """Pobierz aktualny reżim rynkowy (UPTREND / DOWNTREND / SIDEWAYS / TRANSITIONING)."""
    try:
        svc = get_indicators_service()
        regime = svc.get_regime(interval=interval)
        if "error" in regime and regime.get("regime") == "UNKNOWN":
            raise HTTPException(status_code=503, detail=regime["error"])
        return RegimeResponse(**regime)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /regime/current: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/strategies")
def get_strategies():
    """Zwróć listę dostępnych strategii z domyślnymi parametrami."""
    return {
        name: {
            "description": s["description"],
            "default_params": s["default_params"],
            "param_labels": s["param_labels"],
        }
        for name, s in STRATEGIES.items()
    }


@router.post("/backtest/run")
def backtest_run(req: BacktestRequest):
    """Uruchom backtest z podziałem train/test."""
    try:
        params = req.params or {}
        result = run_backtest(
            strategy=req.strategy,
            interval=req.interval,
            train_from=req.train_from,
            train_to=req.train_to,
            test_from=req.test_from,
            test_to=req.test_to,
            params=params if params else None,
            initial_capital=req.initial_capital,
            commission_pct=req.commission_pct,
            slippage_pct=req.slippage_pct,
        )
        run_id = str(uuid.uuid4())[:8]
        result["id"] = run_id
        result["created_at"] = datetime.now().isoformat()
        _backtest_results[run_id] = result
        # Trzymaj max 20 ostatnich (LRU prosty)
        if len(_backtest_results) > 20:
            oldest = sorted(_backtest_results.items(), key=lambda kv: kv[1].get("created_at", ""))[0][0]
            _backtest_results.pop(oldest, None)
        state_store.save("backtest_results", _backtest_results)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/{run_id}")
def get_backtest_result(run_id: str):
    """Pobierz wynik backtestingu po ID."""
    result = _backtest_results.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Backtest {run_id} nie znaleziony")
    return result


@router.post("/backtest/walk-forward")
def backtest_walk_forward(req: WalkForwardRequest):
    """Walk-forward testing — 7 rund przesuwającego się okna."""
    try:
        params = req.params or None
        result = run_walk_forward(
            strategy=req.strategy,
            interval=req.interval,
            params=params,
            initial_capital=req.initial_capital,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Walk-forward error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quant/current")
def quant_current():
    """Pełny snapshot wskaźników kwantowych."""
    try:
        return get_quant_snapshot()
    except Exception as e:
        logger.error(f"Quant snapshot error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quant/risk-score")
def quant_risk_score():
    """Aktualny Risk Score + Quant Signal."""
    try:
        return get_risk_score()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quant/vix")
def quant_vix(days: int = Query(default=252, ge=30, le=1000)):
    """Historia VIX i Historical Volatility."""
    try:
        return get_vix_history(days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quant/zscore")
def quant_zscore(days: int = Query(default=252, ge=30, le=1000)):
    """Historia Z-Score 50d i 200d."""
    try:
        return get_zscore_history(days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quant/correlations")
def quant_correlations(days: int = Query(default=252, ge=30, le=1000)):
    """Historia korelacji cross-market (rolling 30d)."""
    try:
        return get_correlations_history(days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns")
def get_pattern_analysis(
    interval: str = Query(default="1D", pattern="^(1h|4h|1D|1W)$"),
    days: int = Query(default=180, ge=30, le=730),
):
    """Formacje świecowe, S/R, dywergencje, Price Action, breakouty."""
    try:
        result = get_patterns(interval=interval, days=days)
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pattern analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/signals/analyze")
def signals_analyze(
    interval: str = Query(default="1D", pattern="^(1h|4h|1D|1W)$"),
):
    """Uruchom pełną analizę: 4 agenty + Orchestrator + Risk Manager."""
    try:
        return run_analysis(interval=interval)
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
def signals_list():
    """Zwróć historię sygnałów (ostatnie 50)."""
    return {"signals": get_signals_history(), "position": get_position()}


@router.post("/chat")
def chat_endpoint(body: dict):
    """Chat z agentem AI."""
    message = body.get("message", "").strip()
    history = body.get("history", [])
    if not message:
        raise HTTPException(status_code=400, detail="Brak wiadomości")
    try:
        response = agent_chat(message, history)
        return {"response": response}
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
def performance():
    """Zwróć dane performance: equity curve, metryki, transakcje."""
    try:
        return get_performance()
    except Exception as e:
        logger.error(f"Performance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance/capital")
def set_capital(body: dict):
    """Ustaw kapitał startowy (resetuje historię)."""
    amount = body.get("amount", 100_000.0)
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise HTTPException(status_code=400, detail="Nieprawidłowa kwota")
    set_initial_capital(float(amount))
    return {"ok": True, "initial_capital": amount}


@router.get("/feedback/status")
def feedback_status():
    """Stan feedback loop: win rate, confidence adjustment."""
    from app.services.agent_service import get_signals_history, _confidence_adjustment
    signals = get_signals_history()
    wr_30 = get_win_rate(signals, days=30)
    wr_7  = get_win_rate(signals, days=7)
    return {
        "win_rate_30d":          wr_30,
        "win_rate_7d":           wr_7,
        "confidence_adjustment": _confidence_adjustment,
        "effective_threshold":   65 + _confidence_adjustment,
        "total_evaluated":       sum(1 for s in signals if s.get("signal") == "BUY" and s.get("entry_price")),
    }


@router.post("/alerts/config")
def set_alerts_config(body: dict):
    """Skonfiguruj alerty email — zapis do state_store + override env."""
    import os
    from app.services import state_store
    enabled  = bool(body.get("enabled", False))
    password = body.get("smtp_password", "")

    # Persist do JSON (przeżyje restart)
    saved = state_store.load("alerts_config") or {}
    saved["alerts_enabled"] = enabled
    if password:
        saved["smtp_password"] = password
    state_store.save("alerts_config", saved)

    # Zaaplikuj natychmiast do bieżącego procesu
    os.environ["ALERTS_ENABLED"] = str(enabled).lower()
    if password:
        os.environ["SMTP_PASSWORD"] = password
    get_settings.cache_clear()
    settings = get_settings()
    return {
        "alerts_enabled": settings.alerts_enabled,
        "recipient":      settings.alert_recipient,
        "smtp_user":      settings.smtp_user,
    }


@router.post("/alerts/test")
def test_alert():
    """Wyślij testowy email synchronicznie — pokaż faktyczny wynik SMTP."""
    mock_result = {
        "id": "test", "timestamp": datetime.now().isoformat(),
        "signal": "BUY", "confidence": 72,
        "entry_price": 5450.0, "stop_loss": 5370.0, "take_profit": 5610.0,
        "rr_ratio": 2.0, "position_size_pct": 2.0,
        "risk_approved": True, "risk_reject_reason": None,
        "reasoning": "To jest testowy alert z swing.io.",
        "key_factors": ["Test alertu", "Konfiguracja SMTP"],
    }
    settings = get_settings()
    if not settings.alerts_enabled:
        return {"sent": False, "reason": "Alerty wyłączone (ALERTS_ENABLED=false)"}
    if not settings.alert_recipient:
        return {"sent": False, "reason": "Brak ALERT_RECIPIENT"}

    has_resend = bool(settings.resend_api_key)
    has_smtp   = all([settings.smtp_host, settings.smtp_user, settings.smtp_password])
    if not has_resend and not has_smtp:
        return {"sent": False, "reason": "Brak konfiguracji: ustaw RESEND_API_KEY (preferowane) lub SMTP_HOST/USER/PASSWORD"}

    try:
        sent = email_service._send_sync(mock_result, raise_on_error=True)
        err = None
    except Exception as e:
        sent = False
        err = f"{type(e).__name__}: {e}"
    return {
        "sent": sent,
        "error": err,
        "provider": "resend" if has_resend else "smtp",
        "recipient": settings.alert_recipient,
    }


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "app": "swing.io",
    }


@router.get("/_debug/quant")
def debug_quant():
    """Diagnostyka stanu quant cache."""
    import time as _time
    from app.services import quant_service
    now = _time.time()
    ram_cache = {
        k: {
            "age_s": round(now - v["ts"], 1),
            "has_data": bool(v.get("data")),
        }
        for k, v in quant_service._cache.items()
    }
    disk_keys = []
    try:
        for k in ["breadth", "quant_vol", "quant_stat", "quant_cross"]:
            d = state_store.load(k)
            if d is not None:
                disk_keys.append({
                    "key": k,
                    "computed_at_age_s": round(now - d.get("computed_at", d.get("ts", 0)), 1) if isinstance(d, dict) else "n/a",
                })
    except Exception as e:
        disk_keys = [{"error": str(e)}]
    return {
        "ram_cache_keys": list(quant_service._cache.keys()),
        "ram_cache":      ram_cache,
        "disk_cache":     disk_keys,
        "state_dir":      str(state_store._STATE_DIR),
        "state_dir_exists": state_store._STATE_DIR.exists(),
        "compute_locks":  list(quant_service._cache_compute_locks.keys()),
    }


@router.get("/_debug/quant/test")
def debug_quant_test():
    """Wymuś nowy snapshot z timing per-module."""
    import time as _time
    from app.services import quant_service as q
    timings = {}
    results = {}
    for name, fn in [
        ("vol",   q._volatility_snapshot),
        ("stat",  q._statistical_snapshot),
        ("cross", q._crossmarket_snapshot),
    ]:
        t0 = _time.time()
        try:
            r = q._run_with_timeout(fn, timeout=10.0)
            timings[name] = round(_time.time() - t0, 2)
            results[name] = "OK" if r else "TIMEOUT"
        except Exception as e:
            timings[name] = round(_time.time() - t0, 2)
            results[name] = f"ERROR: {e}"

    t0 = _time.time()
    breadth_result = q._run_with_timeout(q._breadth_compute, timeout=15.0)
    timings["breadth"] = round(_time.time() - t0, 2)
    results["breadth"] = "OK" if breadth_result else "TIMEOUT"

    return {"timings_s": timings, "results": results}
