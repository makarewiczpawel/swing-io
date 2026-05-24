"""swing.io — FastAPI Backend."""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings
from app.core import auth
from app.services import state_store, performance_service, agent_service, quant_service
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="swing.io API",
    description="Analiza techniczna S&P 500 z agentami AI wspomagającymi swing trading",
    version="0.1.0",
)

# Dozwolone originy — definiujemy przed middleware
_origins = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://swing-io.pages.dev",
]
if settings.frontend_urls:
    _origins += [u.strip() for u in settings.frontend_urls.split(",") if u.strip()]

# Auth middleware — dodajemy PRZED CORS, żeby CORS był zewnętrzny i dodawał
# nagłówki Access-Control-Allow-Origin nawet do odpowiedzi 401.
_PUBLIC_PATHS = {"/", "/api/health", "/api/auth/login", "/api/auth/status",
                 "/docs", "/openapi.json", "/redoc"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not auth.is_auth_enabled():
        return await call_next(request)
    # Public paths + CORS preflight
    if request.url.path in _PUBLIC_PATHS or request.method == "OPTIONS":
        return await call_next(request)
    # Wymagaj Bearer
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or not auth.verify_token(header[7:]):
        return JSONResponse(status_code=401, content={"detail": "Brak autoryzacji"})
    return await call_next(request)

# CORS — dodajemy PO auth_middleware; w Starlette ostatni add_middleware
# staje się najbardziej zewnętrzną warstwą, więc opakuje auth i doda
# nagłówki CORS do wszystkich odpowiedzi, łącznie z 401.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routy
app.include_router(router)

# ─── Startup: załaduj stan z dysku + zaaplikuj saved alerts config ─────────
@app.on_event("startup")
def _startup():
    log = logging.getLogger("startup")
    try:
        agent_service._load_state()
        performance_service._load_state()
        # Zastosuj zapisaną konfigurację alertów (przeżyła restart)
        cfg = state_store.load("alerts_config") or {}
        if "alerts_enabled" in cfg:
            os.environ["ALERTS_ENABLED"] = str(cfg["alerts_enabled"]).lower()
        if cfg.get("smtp_password"):
            os.environ["SMTP_PASSWORD"] = cfg["smtp_password"]
        get_settings.cache_clear()
        # Odpal quant warmup w tle (nie blokuje healthcheck-a)
        quant_service.warmup_async()
        log.info("State + alerts config loaded; quant warmup queued")
    except Exception as e:
        log.error(f"Startup state load failed: {e}")

# Scheduler — automatyczna analiza 3× dziennie w dni robocze
def _scheduled_analysis():
    log = logging.getLogger("scheduler")
    try:
        result = agent_service.run_analysis(interval="1D")
        log.info(f"Scheduled analysis done: {result.get('signal')} confidence={result.get('confidence')}")
    except Exception as e:
        log.error(f"Scheduled analysis failed: {e}", exc_info=True)

scheduler = BackgroundScheduler(timezone="America/New_York")
scheduler.add_job(
    _scheduled_analysis, "cron",
    day_of_week="mon-fri", hour="10,14,18", minute=5,
    coalesce=True, max_instances=1, misfire_grace_time=600,
)
scheduler.start()

@app.on_event("shutdown")
def _shutdown():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass


@app.get("/")
def root():
    return {
        "app": "swing.io",
        "version": "0.1.0",
        "docs": "/docs",
    }
