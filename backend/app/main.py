"""swing.io — FastAPI Backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings
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


@app.get("/")
def root():
    return {
        "app": "swing.io",
        "version": "0.1.0",
        "docs": "/docs",
    }
