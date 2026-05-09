# swing.io — Szczegółowy Plan Projektu

> **Wersja:** 2.0 | **Data:** 28 kwietnia 2026  
> **Cel:** Aplikacja webowa do analizy technicznej S&P 500 z agentami AI wspomagającymi decyzje swing tradingowe  
> **Styl tradingu:** Swing trading (interwały 1D + 4h)  
> **Poprzednia nazwa:** SP500 Analyzer  
> **Changelog v2.0:** Uwzględniono 8 poprawek z review — szczegóły w sekcji "Co zmieniono"

---

## Co zmieniono w v2.0 (vs v1.2)

| # | Uwaga z review | Jak uwzględniono |
|---|---|---|
| 1 | Brakuje Fazy 0 — edukacja | Dodano sekcję edukacyjną do każdej fazy (sekcja 13) |
| 2 | Harmonogram zbyt optymistyczny | Usunięto sztywne tygodnie, plan oparty na fazach (sekcja 10) |
| 3 | Trump Monitor ryzykowny | Przeniesiony na sam koniec jako opcjonalny bonus (Faza 8) |
| 4 | Brakuje zarządzania stanem portfela | Dodano model pozycji + tabela `positions` (sekcje 3, 4) |
| 5 | Feedback loop bez reguł oceny | Zdefiniowano jasne reguły oceny sygnałów (sekcja 8) |
| 6 | Brak filtrowania fałszywych breakoutów | Dodano regułę potwierdzenia breakoutu (sekcja 6) |
| 7 | Backtesting za późno | Przeniesiony do Fazy 2b — zaraz po wskaźnikach (sekcja 10) |
| 8 | Brak ochrony przed overfittingiem | Dodano train/test split + walk-forward testing (sekcja 7) |

---

## 1. Stack technologiczny

| Warstwa | Technologia | Uzasadnienie |
|---|---|---|
| Frontend | React + Vite | Sprawdzony stack (makro.io), szybki development |
| Backend | FastAPI (Python) | Ekosystem ML/AI, pandas, ta-lib, backtrader |
| Baza danych | PostgreSQL (Railway) | Dane historyczne, backtesting — wymaga relacyjnej bazy |
| Cache | Redis (Railway addon) | Cache cen, kolejki zadań agentów |
| AI | Claude API (Anthropic) | Orchestrator + Risk Manager + Chat |
| Hosting frontend | Cloudflare Pages | CDN, darmowy, sprawdzony |
| Hosting backend | Railway | Python, scheduler, baza — sprawdzony z makro.io |
| Powiadomienia | Email (SMTP / Resend) | Alerting przy sygnałach |

---

## 2. Źródła danych — strategia hybrydowa

### yfinance (główne źródło historyczne)
- **Rola:** Dane historyczne, backtesting, inicjalne wypełnienie bazy
- **Interwały:** 1D, 1W (lata wstecz), 4h/1h (ostatnie 60 dni)
- **Koszt:** Darmowe, bez klucza API
- **Limity:** Dane intraday max 60 dni wstecz; 1-min dane max 7 dni
- **Ticker S&P 500:** `^GSPC`

### Finnhub (dane bieżące + fundamentalne)
- **Rola:** Aktualna cena, news, sentiment, earnings calendar
- **Koszt:** Darmowy tier
- **Limity:** 60 req/min, ~20 min opóźnienie na free tier
- **Klucz API:** Wymagany (darmowa rejestracja)

### Strategia upgrade (przyszłość)
- **FMP** ($19/mies.) lub **Polygon.io** ($29/mies.) — prawdziwy real-time
- Architektura modułowa: zamiana źródła = zmiana jednego modułu

---

## 3. Baza danych — schemat

```sql
-- ─── Świece cenowe S&P 500 ──────────────────────────────────────

candles (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT DEFAULT 0,
    interval VARCHAR(5) NOT NULL,      -- '1h', '4h', '1D', '1W'
    source VARCHAR(20) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, interval)
)

-- ─── Reżim rynkowy ─────────────────────────────────────────────

regime_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    interval VARCHAR(5) NOT NULL,
    regime VARCHAR(20) NOT NULL,       -- 'uptrend', 'downtrend', 'sideways', 'transitioning'
    adx_value DECIMAL(6,2),
    sma50 DECIMAL(10,2),
    sma200 DECIMAL(10,2),
    confidence DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── [NOWE v2.0] Model pozycji — agent wie w jakiej jesteś sytuacji ───

positions (
    id SERIAL PRIMARY KEY,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    signal_id INTEGER REFERENCES signals(id),
    direction VARCHAR(5) NOT NULL,     -- 'LONG', 'SHORT'
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    size_pct DECIMAL(5,2),             -- % kapitału zaangażowanego
    status VARCHAR(10) NOT NULL,       -- 'OPEN', 'CLOSED'
    close_reason VARCHAR(20),          -- 'SL_HIT', 'TP_HIT', 'OPPOSITE_SIGNAL', 'MANUAL', 'EXPIRED'
    pnl_amount DECIMAL(12,2),
    pnl_percent DECIMAL(6,2),
    max_favorable_excursion DECIMAL(10,2),  -- najlepsza cena w kierunku pozycji
    max_adverse_excursion DECIMAL(10,2),    -- najgorsza cena przeciw pozycji
    bars_held INTEGER                  -- ile świec trwała pozycja
)

-- ─── [NOWE v2.0] Stan portfela — aktualny kapitał i ekspozycja ────

portfolio_state (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    starting_capital DECIMAL(12,2) DEFAULT 100000,
    current_capital DECIMAL(12,2) NOT NULL,
    current_position VARCHAR(5),       -- 'LONG', 'SHORT', 'FLAT'
    position_id INTEGER REFERENCES positions(id),
    unrealized_pnl DECIMAL(12,2) DEFAULT 0,
    total_realized_pnl DECIMAL(12,2) DEFAULT 0,
    peak_equity DECIMAL(12,2),
    drawdown_pct DECIMAL(6,2),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0
)

-- ─── Sygnały agenta AI ──────────────────────────────────────────

signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    type VARCHAR(10) NOT NULL,         -- 'BUY', 'SELL', 'SHORT', 'HOLD'
    confidence INTEGER NOT NULL,       -- 0-100
    reasoning TEXT,
    entry_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    regime VARCHAR(20),
    interval VARCHAR(5),
    status VARCHAR(20) DEFAULT 'pending',
    -- [NOWE v2.0] kontekst pozycji w momencie generowania sygnału
    current_position VARCHAR(5),       -- 'LONG', 'SHORT', 'FLAT' w momencie sygnału
    position_entry_price DECIMAL(10,2),-- cena wejścia aktualnej pozycji (jeśli jest)
    position_pnl_pct DECIMAL(6,2),     -- P&L aktualnej pozycji (jeśli jest)
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── Wyniki sygnałów (feedback loop) ────────────────────────────

signal_results (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id) ON DELETE CASCADE,
    price_after_1h DECIMAL(10,2),
    price_after_4h DECIMAL(10,2),
    price_after_1d DECIMAL(10,2),
    price_after_5d DECIMAL(10,2),      -- [ZMIANA v2.0] 5d zamiast 1w (reguła oceny)
    max_favorable DECIMAL(10,2),
    max_adverse DECIMAL(10,2),
    -- [NOWE v2.0] jasne reguły oceny
    hit_tp BOOLEAN DEFAULT FALSE,      -- czy cena osiągnęła TP w oknie oceny?
    hit_sl BOOLEAN DEFAULT FALSE,      -- czy cena osiągnęła SL w oknie oceny?
    hit_tp_first BOOLEAN,              -- TRUE=TP hit przed SL, FALSE=SL hit przed TP
    outcome VARCHAR(10),               -- 'WIN', 'LOSS', 'BREAKEVEN', 'EXPIRED', 'PENDING'
    pnl_percent DECIMAL(6,2),
    pnl_amount DECIMAL(12,2),
    closed_at TIMESTAMPTZ
)

-- ─── Equity curve ────────────────────────────────────────────────

portfolio_equity (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    signal_id INTEGER REFERENCES signals(id),
    equity DECIMAL(12,2) NOT NULL,
    drawdown_pct DECIMAL(6,2),
    peak_equity DECIMAL(12,2),
    cumulative_pnl_pct DECIMAL(8,2),
    total_trades INTEGER,
    win_rate DECIMAL(5,2),
    profit_factor DECIMAL(6,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── Raporty agentów ─────────────────────────────────────────────

agent_reports (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── Backtesty ───────────────────────────────────────────────────

backtest_runs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    strategy_name VARCHAR(100) NOT NULL,
    params JSONB,
    -- [NOWE v2.0] podział danych train/test
    train_from DATE,
    train_to DATE,
    test_from DATE,
    test_to DATE,
    -- metryki na zbiorze treningowym
    train_total_trades INTEGER,
    train_win_rate DECIMAL(5,2),
    train_profit_factor DECIMAL(6,2),
    train_sharpe DECIMAL(6,2),
    train_max_drawdown DECIMAL(6,2),
    train_return DECIMAL(8,2),
    -- metryki na zbiorze testowym (weryfikacja)
    test_total_trades INTEGER,
    test_win_rate DECIMAL(5,2),
    test_profit_factor DECIMAL(6,2),
    test_sharpe DECIMAL(6,2),
    test_max_drawdown DECIMAL(6,2),
    test_return DECIMAL(8,2),
    -- degradacja (różnica train vs test — im mniejsza, tym lepiej)
    degradation_win_rate DECIMAL(5,2),
    degradation_sharpe DECIMAL(6,2),
    -- ogólne
    equity_curve JSONB,
    results_detail JSONB,
    is_overfit BOOLEAN DEFAULT FALSE   -- auto-flag: degradacja > 20% → prawdopodobny overfitting
)

-- ─── Historia chatów z agentem ───────────────────────────────────

chat_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    role VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    context_json JSONB
)

-- ─── [OPCJONALNIE — Faza 8] Posty Trumpa z Truth Social ─────────

trump_posts (
    id SERIAL PRIMARY KEY,
    truth_id VARCHAR(50) UNIQUE,
    timestamp TIMESTAMPTZ,
    content TEXT,
    relevance INTEGER,
    sentiment VARCHAR(10),
    impact INTEGER,
    urgency VARCHAR(20),
    keywords TEXT[],
    reasoning TEXT,
    sp500_price_at_post DECIMAL(10,2),
    sp500_price_after_1h DECIMAL(10,2),
    sp500_price_after_4h DECIMAL(10,2),
    sp500_price_after_1d DECIMAL(10,2),
    actual_impact_pct DECIMAL(6,2),
    alert_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
)
```

---

## 4. Architektura agentów AI

### Podział ról

#### Agenty algorytmiczne (Python — szybkie, deterministyczne)

**TREND ANALYST**
- Oblicza: SMA 9/21/50/200, EMA 9/21, MACD, ADX, RSI, Bollinger Bands
- Klasyfikuje reżim rynkowy (uptrend / downtrend / sideways)
- Output: JSON z wartościami wskaźników + ocena reżimu

**PATTERN ANALYST**
- Rozpoznaje formacje świecowe (candlestick patterns)
- Analizuje Price Action: swing highs/lows, Break of Structure, Change of Character
- Identyfikuje poziomy wsparcia/oporu
- Wykrywa dywergencje (cena vs RSI, cena vs MACD)
- **[NOWE v2.0] Filtrowanie fałszywych breakoutów** — breakout wymaga: zamknięcia świecy powyżej/poniżej poziomu + wolumen > 1.5x średniego 20-dniowego wolumenu. Bez tego = "pending breakout", nie sygnał.
- Output: JSON z listą wykrytych formacji + ich scoring

**VOLUME ANALYST**
- Oblicza: OBV, Volume Profile, wolumen relatywny
- Wykrywa: climax volume, dry-up volume, volume confirmation
- Output: JSON z oceną wolumenu

#### Agenty AI (Claude API — rozumują, decydują)

**ORCHESTRATOR**
- Otrzymuje raporty od trzech agentów algorytmicznych
- Otrzymuje kontekst: ostatnie N sygnałów i ich wyniki
- **[NOWE v2.0] Otrzymuje stan pozycji:** czy jest otwarta pozycja, w jakim kierunku, jaki P&L
- Waży sygnały w kontekście reżimu rynkowego
- Generuje: sygnał (BUY/SELL/SHORT/HOLD), confidence (0-100), uzasadnienie, SL/TP
- **[NOWE v2.0] Nie generuje BUY jeśli jest już LONG** (chyba że to doważenie z osobnym uzasadnieniem)
- Próg powiadomienia: confidence ≥ 75 (konfigurowalny)

**RISK MANAGER**
- Ocenia ryzyko przed zatwierdzeniem sygnału
- Sprawdza: ATR-based stop-loss, risk/reward ratio (min 1:2), max drawdown
- Może zablokować sygnał Orchestratora jeśli ryzyko zbyt wysokie
- **[NOWE v2.0] Sugeruje position sizing** na podstawie: aktualnego kapitału, ATR, max risk per trade (domyślnie 2% kapitału)

**CHAT AGENT**
- Interfejs konwersacyjny — odpowiada na pytania o rynek
- Ma dostęp do: aktualnych danych, raportów agentów, historii sygnałów, **stanu pozycji**
- Przykładowe pytania: "Jak oceniasz obecny trend?", "Dlaczego ostatni sygnał był błędny?", "Czy powinienem zamknąć pozycję?", "Jaki jest mój aktualny P&L?"

### Flow sygnału

```
[Co 4h: nowa świeca]
      │
      ▼
[Pobierz dane z Finnhub/yfinance]
      │
      ▼
[Trend Analyst] ──► raport JSON
[Pattern Analyst] ──► raport JSON (z filtrem fałszywych breakoutów)
[Volume Analyst] ──► raport JSON
      │
      ▼
[ORCHESTRATOR (Claude API)]
  + raporty agentów
  + ostatnie 20 sygnałów i ich wyniki
  + aktualny reżim rynkowy
  + [NOWE] stan pozycji (LONG/SHORT/FLAT, entry price, P&L)
  + [NOWE] aktualny kapitał i ekspozycja
      │
      ▼
[Propozycja sygnału]
      │
      ▼
[RISK MANAGER (Claude API)]
  + ocena ryzyka
  + position sizing (max 2% risk per trade)
  + czy zatwierdzić?
      │
      ▼
[Sygnał zapisany w bazie]
[Pozycja otwarta/zamknięta w tabeli positions]
[Portfolio state zaktualizowany]
      │
      ▼
[confidence ≥ 75?] ──YES──► EMAIL ALERT 📊
      │
      NO
      ▼
[Zapisz w historii, brak powiadomienia]
```

---

## 5. Identyfikacja reżimu rynkowego

### Algorytm klasyfikacji

```
IF ADX > 25 AND cena > SMA50 > SMA200:
    reżim = "UPTREND"
    
IF ADX > 25 AND cena < SMA50 < SMA200:
    reżim = "DOWNTREND"
    
IF ADX < 20 OR (SMA50 ≈ SMA200 w zakresie 1%):
    reżim = "SIDEWAYS"
    
IF ADX 20-25:
    reżim = "TRANSITIONING" (ostrzeżenie — sygnały mniej wiarygodne)
```

### Strategia per reżim

| Reżim | Strategia | Wskaźniki priorytetowe | Sygnały |
|---|---|---|---|
| UPTREND | Trend-following | EMA 9/21, MACD, wolumen | BUY na pullbackach do EMA, breakouty |
| DOWNTREND | Trend-following (short) | EMA 9/21, MACD, wolumen | SHORT na pullbackach do EMA |
| SIDEWAYS | Mean-reversion | RSI, Bollinger Bands, S/R | BUY przy wsparciu, SELL przy oporze |
| TRANSITIONING | Ostrożność | ADX, Price Action, wolumen | Mniejsze pozycje, wyższy próg confidence |

---

## 6. Formacje świecowe — priorytetowe

### Formacje odwrócenia (najważniejsze dla swing tradingu)
- **Bullish Engulfing** — przy wsparciu, w downtrend → sygnał BUY
- **Bearish Engulfing** — przy oporze, w uptrend → sygnał SELL/SHORT
- **Hammer / Inverted Hammer** — przy wsparciu → potencjalne odwrócenie
- **Morning Star / Evening Star** — silne sygnały 3-świecowe
- **Doji** — niezdecydowanie, ważny w kontekście (przy ekstremalnych S/R)

### Formacje kontynuacji
- **Three White Soldiers / Three Black Crows**
- **Rising / Falling Three Methods**
- **Bullish / Bearish Flag** (Price Action)

### Price Action
- **Higher Highs + Higher Lows** → uptrend potwierdzona strukturą
- **Lower Highs + Lower Lows** → downtrend potwierdzona strukturą
- **Break of Structure (BOS)** → kontynuacja trendu
- **Change of Character (CHOCH)** → potencjalne odwrócenie trendu
- **Dywergencje** RSI/MACD vs cena → wczesne ostrzeżenie

### [NOWE v2.0] Filtrowanie fałszywych breakoutów

Breakout jest uznany za **potwierdzony** tylko jeśli spełnia OBA warunki:
1. **Zamknięcie świecy** powyżej oporu (lub poniżej wsparcia) — sam knot nie wystarczy
2. **Wolumen > 1.5x** średniego 20-dniowego wolumenu

Jeśli cena przebija poziom, ale nie spełnia obu warunków → status **"PENDING BREAKOUT"**:
- Agent nie generuje sygnału, ale monitoruje
- Jeśli następna świeca potwierdzi (zamknięcie + wolumen) → sygnał
- Jeśli cena wraca poniżej/powyżej poziomu → fałszywy breakout, ignoruj

Scoring breakoutów:
- Potwierdzone zamknięciem + wolumenem = +3 do score formacji
- Tylko zamknięcie, bez wolumenu = +1 (słaby)
- Tylko knot, bez zamknięcia = 0 (ignoruj)

---

## 7. Backtesting

### [ZMIANA v2.0] Przeniesiony do Fazy 2b — zaraz po wskaźnikach

Backtesting jest teraz fundamentem, nie dodatkiem. Każdy wskaźnik i formacja jest weryfikowana na danych historycznych ZANIM trafi do agenta.

### Silnik
- Własny lekki engine w Pythonie (lub `backtrader`)
- Dane: yfinance historyczne S&P 500 (min. 10 lat daily, 60 dni 4h)
- Symulacja uwzględnia: prowizje, spread, slippage

### [NOWE v2.0] Podział danych — ochrona przed overfittingiem

```
Dane historyczne S&P 500 (2010–2026):

┌──────────────────────────────────┬─────────────────┐
│       TRAIN SET (70%)            │   TEST SET (30%) │
│       2010 — 2021                │   2022 — 2026    │
│                                  │                  │
│   Optymalizuj parametry          │   NIGDY nie      │
│   Testuj hipotezy                │   optymalizuj    │
│   Szukaj patterns                │   tutaj!         │
│                                  │                  │
│   Wyniki: train_win_rate,        │   Wyniki:        │
│   train_sharpe, etc.             │   test_win_rate  │
└──────────────────────────────────┴─────────────────┘

Reguła: jeśli test_win_rate < 0.8 × train_win_rate → OVERFIT
        jeśli test_sharpe < 0.7 × train_sharpe → OVERFIT
        
Overfit = strategia działa na przeszłości, ale nie na nowych danych.
Nie używaj jej!
```

### Walk-forward testing (zaawansowane)
Zamiast jednego podziału train/test, robimy przesuwane okno:

```
Runda 1: Train 2010-2018 → Test 2019
Runda 2: Train 2011-2019 → Test 2020
Runda 3: Train 2012-2020 → Test 2021
Runda 4: Train 2013-2021 → Test 2022
Runda 5: Train 2014-2022 → Test 2023
Runda 6: Train 2015-2023 → Test 2024
Runda 7: Train 2016-2024 → Test 2025

Strategia jest dobra, jeśli wyniki na KAŻDYM zbiorze testowym
są akceptowalne (nie tylko na jednym wybranym okresie).
```

### Metryki
| Metryka | Opis | Cel minimum |
|---|---|---|
| Win Rate | % zyskownych transakcji | > 50% |
| Profit Factor | suma zysków / suma strat | > 1.5 |
| Sharpe Ratio | zysk skorygowany o ryzyko | > 1.0 |
| Max Drawdown | największy spadek equity | < 15% |
| Avg Trade Duration | średni czas trwania pozycji | 2-10 dni (swing) |
| **[NOWE] Degradation** | różnica train vs test win rate | < 20% |

### Workflow
1. Zdefiniuj strategię z parametrami
2. Backend testuje na TRAIN set
3. Jeśli wyniki obiecujące → test na TEST set
4. Porównanie train vs test → flaga overfitting jeśli degradacja > 20%
5. Tylko strategie, które przejdą test → trafiają do agenta
6. Walk-forward testing dla najlepszych strategii

---

## 8. System uczenia się (Feedback Loop)

### [NOWE v2.0] Jasne reguły oceny sygnałów

**Kiedy sygnał BUY/LONG jest "trafiony" (WIN)?**
Gdy w ciągu **5 dni handlowych** od sygnału spełniony jest KTÓRYKOLWIEK warunek:
1. Cena osiągnęła Take Profit (TP) PRZED osiągnięciem Stop Loss (SL)
2. Cena wzrosła o ≥2% przed dotknięciem SL

**Kiedy sygnał BUY/LONG jest "nietrafiony" (LOSS)?**
1. Cena osiągnęła Stop Loss (SL) PRZED osiągnięciem TP
2. Cena spadła o ≥1.5% (domyślny max loss) przed osiągnięciem TP

**Kiedy sygnał wygasa (EXPIRED)?**
1. Po 5 dniach handlowych nie osiągnięto ani TP, ani SL
2. Wynik = P&L na zamknięciu 5. dnia

**Analogiczne reguły dla SHORT** (odwrócone kierunki).

**Kiedy sygnał jest BREAKEVEN?**
1. P&L w momencie zamknięcia mieści się w zakresie -0.3% do +0.3%

### Mechanizm
1. **Logging:** Każdy sygnał zapisywany z pełnym kontekstem + stanem pozycji
2. **Tracking:** Cron job śledzi cenę po 1h, 4h, 1D, 5D od sygnału
3. **Evaluation:** Automatyczna ocena wg reguł powyżej
4. **Review:** Co tydzień generowany raport skuteczności
5. **Context injection:** Przy każdym nowym sygnale agent dostaje ostatnie 20 sygnałów + wyniki + reguły oceny
6. **Auto-adjustment:** Jeśli win rate < 45% przez 30 dni → agent podnosi próg confidence o 5 punktów

### Dane dostarczane agentowi przy każdej analizie
```json
{
  "current_position": {
    "direction": "LONG",
    "entry_price": 5450.20,
    "current_pnl_pct": 1.2,
    "bars_held": 3,
    "stop_loss": 5380.00,
    "take_profit": 5550.00
  },
  "portfolio": {
    "current_capital": 103200,
    "starting_capital": 100000,
    "available_to_risk": 2064,
    "total_realized_pnl_pct": 3.2
  },
  "recent_signals": [
    {
      "date": "2026-04-25",
      "type": "BUY",
      "confidence": 82,
      "entry": 5450.20,
      "outcome": "WIN",
      "evaluation_rule": "TP hit on day 3 before SL",
      "pnl_percent": 1.8
    }
  ],
  "performance_summary": {
    "last_30_days": { "win_rate": 65, "profit_factor": 1.8, "total_signals": 12 },
    "last_90_days": { "win_rate": 58, "profit_factor": 1.5, "total_signals": 34 }
  },
  "regime_accuracy": {
    "uptrend_signals_win_rate": 72,
    "downtrend_signals_win_rate": 61,
    "sideways_signals_win_rate": 48
  },
  "evaluation_rules": {
    "window_days": 5,
    "win_condition": "TP hit before SL, OR +2% before SL hit",
    "loss_condition": "SL hit before TP, OR -1.5% before TP hit",
    "expired_condition": "5 days passed, no TP or SL hit"
  }
}
```

---

## 8b. Live Performance Tracker (Equity Curve z sygnałów)

### Czym różni się od backtestingu
- **Backtesting** = testowanie strategii na danych historycznych (symulacja)
- **Live Performance** = śledzenie wyników rzeczywistych sygnałów agenta w czasie rzeczywistym

### Jak działa
1. Użytkownik ustawia **wirtualny kapitał startowy** (np. $100,000)
2. Każdy sygnał agenta ze statusem `active` otwiera wirtualną pozycję w tabeli `positions`
3. **[NOWE v2.0] Portfolio state** jest aktualizowany w czasie rzeczywistym — agent zawsze wie ile masz kapitału
4. Gdy pozycja zostaje zamknięta:
   - Obliczany jest P&L (w $ i %)
   - Equity zostaje zaktualizowane
   - Nowy punkt dodany do equity curve

### Wykresy na stronie Performance
- **Equity Curve** (liniowy) — kapitał w czasie, z linią benchmarku (buy & hold S&P 500) dla porównania
- **Drawdown Chart** (liniowy, odwrócony) — % spadek od szczytu equity
- **P&L per sygnał** (słupkowy) — każdy zamknięty sygnał jako zielony lub czerwony słupek
- **Rozkład zysków** (histogram) — jak często agent generuje zyski/straty o danej wielkości
- **Performance by regime** (słupkowy grupowany) — win rate i avg P&L w podziale na reżim rynkowy

### Metryki wyświetlane w panelu
```
Kapitał startowy:    $100,000
Aktualny kapitał:    $108,450  (+8.45%)
Otwarta pozycja:     LONG @ 5,450.20 (+1.2%)
Peak equity:         $110,200
Max drawdown:        -4.2%
Win rate:            62%  (31/50 trades)
Profit factor:       1.85
Sharpe ratio:        1.42
Avg win:             +2.1%
Avg loss:            -1.1%
Avg trade duration:  4.2 dni
Best trade:          +5.8%
Worst trade:         -3.2%
vs Buy & Hold:       +3.2% (agent lepszy o 3.2pp)
```

### Zasady zamykania pozycji
- **Stop-loss hit** → pozycja zamknięta automatycznie po cenie SL
- **Take-profit hit** → pozycja zamknięta automatycznie po cenie TP
- **Przeciwny sygnał** → BUY zamyka SHORT i odwrotnie
- **Expiration** → jeśli pozycja nie trafi SL/TP w ciągu 10 dni (konfig.), zamykana po aktualnej cenie
- **[NOWE v2.0] Ręczne zamknięcie** przez użytkownika z interfejsu lub chatu z agentem

---

## 9. Frontend — widoki

### Dashboard (strona główna)
- Wykres świecowy S&P 500 (TradingView Lightweight Charts)
- Przełączanie interwałów: 4h / 1D / 1W
- Wskaźniki nakładane na wykres (toggle on/off)
- Panel boczny: aktualny reżim rynkowy, ostatni sygnał, confidence
- **[NOWE v2.0]** Status pozycji: LONG/SHORT/FLAT + aktualny P&L

### Sygnały
- Lista sygnałów (aktywne, historyczne)
- Filtrowanie po typie, confidence, wyniku
- Szczegóły sygnału: uzasadnienie agenta, wykres z zaznaczeniem entry/SL/TP
- **[NOWE v2.0]** Kolumna "Ocena" z wyjaśnieniem (np. "WIN: TP hit day 3")

### Performance (Zyski/Straty)
- **Equity Curve** — wykres liniowy kapitału w czasie (startowy kapitał → aktualny stan)
- **Drawdown Chart** — wykres spadków od szczytu equity
- **P&L per sygnał** — wykres słupkowy: zielony = zysk, czerwony = strata
- **Metryki zbiorcze:** łączny P&L (%), win rate, profit factor, Sharpe, max drawdown
- **Filtry:** okres (1M, 3M, 6M, 1Y, ALL), typ sygnału (BUY/SHORT), reżim rynkowy
- **Porównanie z benchmarkiem:** equity curve agenta vs buy & hold S&P 500
- **Tabela transakcji:** lista zamkniętych pozycji z entry, exit, P&L, czas trwania

### Backtesting
- Formularz: wybierz strategię, okres, parametry
- **[NOWE v2.0]** Automatyczny podział na train/test z wizualizacją obu zestawów
- **[NOWE v2.0]** Alert overfitting gdy degradacja > 20%
- Wyniki: metryki + equity curve + lista transakcji
- Walk-forward testing z wynikami per runda
- Porównanie strategii

### Chat z Agentem
- Interfejs czatowy
- Agent ma kontekst rynkowy (aktualne dane, wskaźniki, reżim, **pozycja, kapitał**)
- Historia rozmów zapisywana w bazie

### Ustawienia
- Próg confidence dla powiadomień
- Konfiguracja email
- Kapitał startowy (wirtualny)
- Max risk per trade (domyślnie 2%)
- Okno oceny sygnału (domyślnie 5 dni)
- Wybór wskaźników do wyświetlania

---

## 10. Harmonogram realizacji

> **[ZMIANA v2.0]** Usunięto sztywne tygodnie. Każda faza trwa tyle, ile potrzeba.
> Kolejność jest ważniejsza niż tempo. Każda faza zawiera komponent edukacyjny (sekcja 13).

| Faza | Zakres | Deliverable | Edukacja |
|---|---|---|---|
| **1. Fundament** | Setup projektu, baza, API dane, wykres świecowy | Działający dashboard z wykresem | Python, FastAPI, React basics |
| **2a. Wskaźniki** | Wskaźniki techniczne, reżim rynkowy, overlay na wykresie | Wskaźniki na wykresie + panel reżimu | Co mówi RSI, MACD, ADX |
| **2b. Backtesting** | Prosty silnik backtestingowy, train/test split | "Czy RSI < 30 daje zysk na S&P?" | Overfitting, statystyka |
| **3. Formacje** | Pattern recognition, Price Action, S/R, filtr breakoutów | Formacje na wykresie + scoring | Formacje świecowe, Price Action |
| **4. Agent AI** | Multi-agent, Claude API, model pozycji, sygnały, chat | Agent generuje sygnały z kontekstem pozycji | Prompt engineering, LLM |
| **5. Performance** | Equity curve, P&L tracking, porównanie z benchmark | Dashboard performance | Metryki tradingowe |
| **6. Uczenie** | Feedback loop z jasnymi regułami, kalibracja, alerty email | Agent śledzi wyniki, wysyła alerty | Statystyczna ocena strategii |
| **7. Deploy** | Railway + Cloudflare Pages, monitoring | Aplikacja live | DevOps, CI/CD |
| **8. Trump Monitor** *(opcjonalny)* | Truthbrush, sentiment analysis, osobne alerty | Trump feed + alerty email | NLP, sentiment analysis |

### Dlaczego ta kolejność?

```
Faza 1 → Masz dane i wykres
Faza 2a → Masz wskaźniki do analizy
Faza 2b → WERYFIKUJESZ czy wskaźniki działają na S&P 500 (zanim zbudujesz na nich agenta!)
Faza 3 → Dodajesz formacje (przetestowane w backtestingu)
Faza 4 → Agent ma SPRAWDZONE narzędzia + wie o Twojej pozycji
Faza 5 → Śledzisz wyniki live
Faza 6 → Agent się uczy na jasnych regułach
Faza 7 → Deploy
Faza 8 → Bonus: Trump Monitor (jeśli chcesz)
```

---

## 11. API Endpoints (planowane)

```
# ─── Dane rynkowe ───────────────────────────
GET  /api/candles?interval=1D&from=...&to=...
GET  /api/quote
GET  /api/market-info
GET  /api/indicators?type=RSI&interval=1D&period=14
GET  /api/regime/current

# ─── [NOWE v2.0] Pozycje i portfel ──────────
GET  /api/position/current             ← aktualna pozycja (LONG/SHORT/FLAT)
GET  /api/position/history             ← historia zamkniętych pozycji
GET  /api/portfolio/state              ← kapitał, P&L, ekspozycja
POST /api/position/close               ← ręczne zamknięcie pozycji

# ─── Sygnały ────────────────────────────────
GET  /api/signals?status=active
GET  /api/signals/{id}
POST /api/signals/analyze              ← trigger ręcznej analizy

# ─── Backtesting ────────────────────────────
POST /api/backtest/run                 ← uruchom backtest
GET  /api/backtest/results/{id}
GET  /api/backtest/results/{id}/overfit ← [NOWE] sprawdzenie overfitting

# ─── Chat ───────────────────────────────────
POST /api/chat
GET  /api/chat/history

# ─── Performance ────────────────────────────
GET  /api/performance/summary
GET  /api/performance/equity?from=...&to=...
GET  /api/performance/drawdown
GET  /api/performance/pnl-per-signal
GET  /api/performance/vs-benchmark
GET  /api/performance/trades

# ─── [OPCJA] Trump Monitor ──────────────────
GET  /api/trump/posts?impact_min=0&limit=50
GET  /api/trump/posts/{id}
GET  /api/trump/stats
POST /api/trump/check

# ─── System ─────────────────────────────────
GET  /api/health
```

---

## 12. Uwagi i ryzyka

- **yfinance** jest nieoficjalnym API — może się zmienić/przestać działać. Architektura modułowa minimalizuje ryzyko.
- **Claude API** — koszty zależą od ilości tokenów. Szacunkowo $5-10/mies. (bez Trump Monitor).
- **Opóźnienie 20 min** na Finnhub free tier — nieistotne dla swing tradingu na 1D/4h.
- **Backtesting ≠ przyszłe wyniki** — agent powinien informować o tym w każdym sygnale.
- **Nie jest to doradztwo inwestycyjne** — aplikacja to narzędzie wspomagające, decyzja zawsze należy do użytkownika.
- **[NOWE v2.0] Overfitting** — największe ryzyko w backtestingu. Train/test split i walk-forward testing minimalizują, ale nie eliminują tego ryzyka. Agent powinien być świadomy ograniczeń backtestingu.
- **[NOWE v2.0] Model pozycji jest wirtualny** — aplikacja nie łączy się z żadnym brokerem. Pozycje są symulowane. Użytkownik samodzielnie realizuje transakcje u swojego brokera.
- **Trump Monitor (opcjonalny)** — Truthbrush/Truth Social mogą przestać działać bez ostrzeżenia. Dlatego przeniesiony na koniec i oznaczony jako opcjonalny.

---

## 13. [NOWE v2.0] Komponent edukacyjny — co rozumieć przy każdej fazie

> Nie chodzi o kopiejowanie kodu, ale o rozumienie DLACZEGO.

### Faza 1 — Fundament
- Jak działa REST API (request → response)
- Co to FastAPI i dlaczego Python jest dobry do analizy danych
- Jak React renderuje UI i co to state/props
- Co to świeca OHLCV (Open, High, Low, Close, Volume)

### Faza 2a — Wskaźniki
- **RSI** — mierzy siłę ruchów cenowych. < 30 = wyprzedanie, > 70 = wykupienie. ALE: w silnym trendzie RSI może siedzieć na 70+ tygodniami — to nie znaczy "sprzedawaj"!
- **MACD** — pokazuje momentum. Crossover linii MACD i Signal = potencjalny sygnał. Dywergencja = cena robi nowe szczyty, ale MACD nie → słabnący trend.
- **ADX** — mierzy SIŁĘ trendu (nie kierunek!). > 25 = silny trend, < 20 = brak trendu.
- **Bollinger Bands** — kanał zmienności. Przydatne w konsolidacji, mylące w trendzie.
- **Dlaczego reżim rynkowy jest ważny** — RSI < 30 w uptrend = świetna okazja do kupna. RSI < 30 w downtrend = łapanie spadającego noża.

### Faza 2b — Backtesting
- Co to overfitting i dlaczego optymalizacja parametrów na przeszłości jest niebezpieczna
- Dlaczego dzielimy dane na train/test
- Co mówią metryki: Sharpe, profit factor, max drawdown
- Walk-forward testing — dlaczego jedno okno nie wystarczy

### Faza 3 — Formacje
- Dlaczego formacja świecowa BEZ kontekstu (reżim, S/R, wolumen) jest bezwartościowa
- Co to false breakout i jak się przed nim bronić
- Price Action — dlaczego struktura rynku (HH/HL/LH/LL) jest ważniejsza niż pojedyncza formacja

### Faza 4 — Agent AI
- Jak działa Claude API (prompt → response)
- Prompt engineering — jak pisać instrukcje, żeby agent dawał dobre wyniki
- Dlaczego agent musi znać stan pozycji (żeby nie mówił "kupuj" gdy już kupiony)
- Ograniczenia LLM — halucynacje, brak prawdziwego "rozumienia" rynku

### Faza 5-6 — Performance i uczenie
- Dlaczego equity curve > win rate (możesz mieć 40% win rate i zarabiać)
- Co to profit factor i dlaczego > 1.5 to minimum
- Jak interpretować drawdown i dlaczego max drawdown 15% to dużo
- Dlaczego jasne reguły oceny (WIN/LOSS/EXPIRED) są konieczne do uczenia
