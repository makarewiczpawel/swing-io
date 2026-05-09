"""swing.io — FastAPI Backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings
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

# CORS — pozwól frontendowi na komunikację
_origins = [settings.frontend_url, "http://localhost:5173", "http://localhost:3000"]
if settings.frontend_urls:
    _origins += [u.strip() for u in settings.frontend_urls.split(",") if u.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routy
app.include_router(router)

# Scheduler — automatyczna analiza co 4h w dni robocze
def _scheduled_analysis():
    from app.services.agent_service import run_analysis
    logger = logging.getLogger("scheduler")
    try:
        result = run_analysis(interval="1D")
        logger.info(f"Scheduled analysis done: {result.get('signal')} confidence={result.get('confidence')}")
    except Exception as e:
        logger.error(f"Scheduled analysis failed: {e}")

scheduler = BackgroundScheduler(timezone="America/New_York")
scheduler.add_job(_scheduled_analysis, "cron", day_of_week="mon-fri", hour="10,14,18", minute=5)
scheduler.start()


@app.get("/")
def root():
    return {
        "app": "swing.io",
        "version": "0.1.0",
        "docs": "/docs",
    }
