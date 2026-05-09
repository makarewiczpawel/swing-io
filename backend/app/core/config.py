from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    frontend_url: str = "http://localhost:5173"
    # Comma-separated list of allowed origins (for production multi-domain)
    frontend_urls: str = ""

    # Finnhub
    finnhub_api_key: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # S&P 500 ticker
    sp500_ticker: str = "^GSPC"

    # Email alerts
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_recipient: str = ""
    alerts_enabled: bool = False

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
