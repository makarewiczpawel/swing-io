# swing.io

Aplikacja webowa do analizy technicznej S&P 500 z agentami AI wspomagającymi swing trading.

## Architektura

```
sp500-analyzer/
├── backend/                  # FastAPI (Python)
│   ├── app/
│   │   ├── api/routes.py     # Endpointy REST API
│   │   ├── core/config.py    # Konfiguracja
│   │   ├── models/schemas.py # Pydantic modele
│   │   ├── services/         # Logika biznesowa
│   │   │   └── market_data.py # yfinance + Finnhub
│   │   └── main.py           # FastAPI app
│   ├── migrations/           # SQL schematy (v2.0)
│   └── requirements.txt
│
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── api/client.js     # Fetch z backendu
│   │   ├── components/       # React komponenty
│   │   ├── hooks/            # Custom hooks
│   │   └── App.jsx           # Główny komponent
│   └── package.json
│
└── README.md
```

## Quick Start

### 1. Backend

```bash
cd backend

# Utwórz virtual environment
python3 -m venv venv
source venv/bin/activate   # macOS/Linux

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj i uzupełnij .env
cp .env.example .env

# Uruchom serwer
uvicorn app.main:app --reload --port 8000
```

Backend dostępny: http://localhost:8000
Dokumentacja API: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend

# Zainstaluj zależności
npm install

# Uruchom dev server
npm run dev
```

Frontend dostępny: http://localhost:5173

### 3. API Endpoints (Faza 1)

| Endpoint | Opis |
|---|---|
| `GET /api/candles?interval=1D&days=365` | Świece S&P 500 |
| `GET /api/quote` | Aktualna cena |
| `GET /api/market-info` | Info (52w high/low, SMA) |
| `GET /api/health` | Health check |

Interwały: `1h`, `4h`, `1D`, `1W`

## Stack

- **Backend:** FastAPI, Python, yfinance, Finnhub
- **Frontend:** React, Vite, TradingView Lightweight Charts
- **Baza danych:** PostgreSQL (Railway) — Faza 2+
- **AI:** Claude API (Anthropic) — Faza 4
- **Deploy:** Railway (backend) + Cloudflare Pages (frontend)

## Fazy rozwoju (v2.0)

- [x] Faza 1 — Fundament (wykres, dane, API)
- [ ] Faza 2a — Wskaźniki techniczne + reżim rynkowy
- [ ] Faza 2b — Backtesting (weryfikacja wskaźników)
- [ ] Faza 3 — Formacje świecowe + filtr fałszywych breakoutów
- [ ] Faza 4 — Agent AI + model pozycji
- [ ] Faza 5 — Live Performance Tracker
- [ ] Faza 6 — Feedback loop + alerty email
- [ ] Faza 7 — Deploy
- [ ] Faza 8 — Trump Monitor (opcjonalny)
