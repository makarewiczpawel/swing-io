# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**swing.io** — a full-stack S&P 500 swing trading analysis tool. Phase 1 (current) delivers live candlestick charting with market indicators. Future phases add AI-driven signals, backtesting, and portfolio tracking.

## Commands

### Backend

```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Swagger docs at `http://localhost:8000/docs`. No tests exist yet.

### Frontend

```bash
cd frontend
npm run dev        # dev server on :5173
npm run build      # output to dist/
npm run preview    # serve production build
```

Vite proxies `/api/*` → `http://localhost:8000` in dev.

## Architecture

### Backend (`backend/app/`)

- **`main.py`** — FastAPI app, CORS middleware, mounts router
- **`api/routes.py`** — four endpoints: `/api/health`, `/api/candles`, `/api/quote`, `/api/market-info`; holds a module-level `MarketDataService` singleton
- **`services/market_data.py`** — all data fetching logic; yfinance for historical candles, async httpx for Finnhub quotes; 4H candles are manually aggregated from 1H data via pandas (yfinance limitation)
- **`models/schemas.py`** — Pydantic request/response models
- **`core/config.py`** — pydantic-settings `Settings` class; reads `.env`

Data flow: routes → `MarketDataService` → yfinance (`^GSPC`) / Finnhub (SPY proxy for quotes) → pandas aggregation → Pydantic response.

### Frontend (`frontend/src/`)

- **`App.jsx`** — layout shell; owns interval/date-range state passed down to chart and panels
- **`components/CandlestickChart.jsx`** — TradingView Lightweight Charts (v4); ResizeObserver keeps canvas responsive
- **`components/Header.jsx`** — live price quote display
- **`components/InfoPanel.jsx`** — SMA 50/200, 52-week high/low, trend label
- **`api/client.js`** — thin fetch wrapper used by all hooks
- **`hooks/useMarketData.js`** — custom hooks (`useCandles`, `useQuote`, `useMarketInfo`) that fetch and memoize API data

### Database

`backend/migrations/001_initial_schema.sql` defines the full PostgreSQL schema (candles, signals, positions, portfolio_state, agent_reports, etc.) for future phases. **Not in use in Phase 1** — all data is fetched live.

## Environment Variables

Copy `backend/.env.example` to `backend/.env`. Required for Phase 1:

```
FINNHUB_API_KEY=    # free tier at finnhub.io
FRONTEND_URL=http://localhost:5173
```

`ANTHROPIC_API_KEY`, SMTP credentials, and `DATABASE_URL` are placeholders for later phases.

## Key Constraints

- yfinance does not natively support 4H intervals — `market_data.py` aggregates 1H OHLCV rows into 4H buckets.
- Finnhub is used only for real-time quotes (SPY ticker); yfinance is the fallback.
- The frontend dark theme, fonts (JetBrains Mono for charts, Outfit for UI), and colour palette (`#0a0e17` background) are intentional design choices — don't change them without reason.
