"""
Market Data Service — pobieranie danych S&P 500 z yfinance i Finnhub.
Architektura modułowa: zamiana źródła = zmiana jednego modułu.
"""

import yfinance as yf
import httpx
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ─── Mapowanie interwałów yfinance ───────────────────────────────
# yfinance używa swoich oznaczeń interwałów
YFINANCE_INTERVAL_MAP = {
    "1h": "1h",
    "4h": "1h",   # yfinance nie ma 4h — pobieramy 1h i agregujemy
    "1D": "1d",
    "1W": "1wk",
}

# Maksymalny okres wstecz dla interwałów intraday
YFINANCE_MAX_PERIOD = {
    "1h": 729,   # ~2 lata (730 dni)
    "4h": 729,
    "1D": 10000, # praktycznie bez limitu
    "1W": 10000,
}


class MarketDataService:
    """Serwis pobierania danych rynkowych S&P 500."""

    def __init__(self, finnhub_api_key: str = ""):
        self.ticker_symbol = "^GSPC"
        self.finnhub_api_key = finnhub_api_key
        self.finnhub_base_url = "https://finnhub.io/api/v1"
        self._ticker = yf.Ticker(self.ticker_symbol)

    # ─── yfinance: dane historyczne ──────────────────────────────

    def get_candles(
        self,
        interval: str = "1D",
        days_back: int = 365,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """
        Pobierz świece S&P 500.

        Args:
            interval: "1h", "4h", "1D", "1W"
            days_back: ile dni wstecz (jeśli brak start/end)
            start_date: "YYYY-MM-DD" (opcjonalny)
            end_date: "YYYY-MM-DD" (opcjonalny)

        Returns:
            Lista dict z polami: timestamp, open, high, low, close, volume
        """
        try:
            # Oblicz daty
            max_days = YFINANCE_MAX_PERIOD.get(interval, 365)
            days_back = min(days_back, max_days)

            if start_date and end_date:
                start = start_date
                end = end_date
            else:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=days_back)
                start = start_dt.strftime("%Y-%m-%d")
                end = end_dt.strftime("%Y-%m-%d")

            # Dla 4h: pobierz 1h i agreguj
            yf_interval = YFINANCE_INTERVAL_MAP.get(interval, "1d")

            logger.info(
                f"Fetching {self.ticker_symbol} | interval={interval} "
                f"(yf={yf_interval}) | {start} → {end}"
            )

            df = self._ticker.history(
                start=start,
                end=end,
                interval=yf_interval,
                auto_adjust=True,
            )

            if df.empty:
                logger.warning(f"No data returned for {interval}")
                return []

            # Agreguj do 4h jeśli potrzeba
            if interval == "4h":
                df = self._aggregate_to_4h(df)

            # Konwertuj do listy słowników
            candles = self._dataframe_to_candles(df)
            logger.info(f"Fetched {len(candles)} candles for {interval}")
            return candles

        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            raise

    def _aggregate_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agreguj dane 1h do świec 4h."""
        df = df.copy()

        # Ustaw index jako datetime jeśli jeszcze nie jest
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Grupuj po 4-godzinnych blokach
        df["group"] = df.index.floor("4h")

        agg = df.groupby("group").agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        )

        # Usuń niekompletne świece (mniej niż 2 godziny danych)
        counts = df.groupby("group").size()
        valid_groups = counts[counts >= 2].index
        agg = agg.loc[agg.index.isin(valid_groups)]

        return agg

    def _dataframe_to_candles(self, df: pd.DataFrame) -> list[dict]:
        """Konwertuj DataFrame do listy słowników (format API)."""
        candles = []
        for idx, row in df.iterrows():
            ts = idx
            if hasattr(ts, "timestamp"):
                timestamp = int(ts.timestamp())
            else:
                timestamp = int(pd.Timestamp(ts).timestamp())

            candles.append(
                {
                    "timestamp": timestamp,
                    "datetime": str(ts),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                }
            )

        return candles

    # ─── Finnhub: bieżąca cena ──────────────────────────────────

    async def get_current_quote(self) -> dict:
        """Pobierz aktualną cenę S&P 500 z Finnhub."""
        if not self.finnhub_api_key:
            # Fallback: ostatnia cena z yfinance
            return self._get_yfinance_quote()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.finnhub_base_url}/quote",
                    params={
                        "symbol": "SPY",  # ETF trackujący S&P 500
                        "token": self.finnhub_api_key,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "price": data.get("c", 0),       # current price
                    "change": data.get("d", 0),       # change
                    "change_pct": data.get("dp", 0),   # change percent
                    "high": data.get("h", 0),          # day high
                    "low": data.get("l", 0),           # day low
                    "open": data.get("o", 0),          # day open
                    "prev_close": data.get("pc", 0),   # prev close
                    "timestamp": data.get("t", 0),
                    "source": "finnhub",
                }
        except Exception as e:
            logger.warning(f"Finnhub error, falling back to yfinance: {e}")
            return self._get_yfinance_quote()

    def _get_yfinance_quote(self) -> dict:
        """Fallback: aktualna cena z yfinance."""
        try:
            info = self._ticker.fast_info
            history = self._ticker.history(period="2d", interval="1d")

            if history.empty:
                return {"price": 0, "source": "yfinance", "error": "no data"}

            last_row = history.iloc[-1]
            prev_close = history.iloc[-2]["Close"] if len(history) > 1 else last_row["Open"]
            current = float(last_row["Close"])
            change = current - float(prev_close)
            change_pct = (change / float(prev_close)) * 100

            return {
                "price": round(current, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "high": round(float(last_row["High"]), 2),
                "low": round(float(last_row["Low"]), 2),
                "open": round(float(last_row["Open"]), 2),
                "prev_close": round(float(prev_close), 2),
                "timestamp": int(last_row.name.timestamp()),
                "source": "yfinance",
            }
        except Exception as e:
            logger.error(f"yfinance quote error: {e}")
            return {"price": 0, "source": "yfinance", "error": str(e)}

    # ─── Info o indeksie ─────────────────────────────────────────

    def get_market_info(self) -> dict:
        """Podstawowe info o S&P 500."""
        try:
            history = self._ticker.history(period="1y", interval="1d")
            if history.empty:
                return {}

            current = float(history.iloc[-1]["Close"])
            high_52w = float(history["High"].max())
            low_52w = float(history["Low"].min())
            sma_50 = float(history["Close"].tail(50).mean())
            sma_200 = float(history["Close"].tail(200).mean())

            return {
                "name": "S&P 500",
                "ticker": self.ticker_symbol,
                "current_price": round(current, 2),
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "sma_50": round(sma_50, 2),
                "sma_200": round(sma_200, 2),
                "above_sma_50": current > sma_50,
                "above_sma_200": current > sma_200,
                "distance_from_high_pct": round(
                    ((current - high_52w) / high_52w) * 100, 2
                ),
            }
        except Exception as e:
            logger.error(f"Market info error: {e}")
            return {"error": str(e)}
