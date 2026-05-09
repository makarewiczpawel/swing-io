# swing.io — Szczegółowy Plan Projektu

> **Wersja:** 2.1 | **Data:** 28 kwietnia 2026  
> **Cel:** Aplikacja webowa do analizy technicznej S&P 500 z agentami AI wspomagającymi decyzje swing tradingowe  
> **Styl tradingu:** Swing trading (interwały 1D + 4h)  
> **Changelog v2.1:** Usunięto Trump Monitor, dodano wskaźniki kwantowe (sekcja 4b, Faza 2c)

---

## Co zmieniono w v2.1 (vs v2.0)

| # | Zmiana | Szczegóły |
|---|---|---|
| 1 | Usunięto Trump Monitor | Usunięto Fazę 8, tabelę trump_posts, endpointy /api/trump, osobne alerty email |
| 2 | Dodano wskaźniki kwantowe | Nowy agent QUANT ANALYST, tabela quant_snapshots, Faza 2c |
| 3 | Rozszerzono źródła danych | Dodano tickery: ^VIX, TLT, GLD, DX-Y.NYB, HYG, LQD (yfinance, darmowe) |
| 4 | Wzbogacono identyfikację reżimu | Reżim uwzględnia teraz VIX, breadth i korelacje międzyrynkowe |
| 5 | Zaktualizowano edukację | Faza 2c — edukacja o wskaźnikach kwantowych |

---

## Poprzednie zmiany (v2.0 vs v1.2)

| # | Uwaga z review | Jak uwzględniono |
|---|---|---|
| 1 | Brakuje Fazy 0 — edukacja | Dodano sekcję edukacyjną do każdej fazy (sekcja 14) |
| 2 | Harmonogram zbyt optymistyczny | Usunięto sztywne tygodnie, plan oparty na fazach (sekcja 11) |
| 3 | ~~Trump Monitor ryzykowny~~ | ~~v2.0: Przeniesiony na koniec~~ → v2.1: Usunięty, zastąpiony wskaźnikami kwantowymi |
| 4 | Brakuje zarządzania stanem portfela | Dodano model pozycji + tabela `positions` (sekcje 3, 4) |
| 5 | Feedback loop bez reguł oceny | Zdefiniowano jasne reguły oceny sygnałów (sekcja 8) |
| 6 | Brak filtrowania fałszywych breakoutów | Dodano regułę potwierdzenia breakoutu (sekcja 7) |
| 7 | Backtesting za późno | Przeniesiony do Fazy 2b — zaraz po wskaźnikach (sekcja 11) |
| 8 | Brak ochrony przed overfittingiem | Dodano train/test split + walk-forward testing (sekcja 6) |

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

### yfinance (główne źródło)
- **Rola:** Dane historyczne + bieżące, backtesting, wskaźniki kwantowe
- **Interwały:** 1D, 1W (lata wstecz), 4h/1h (ostatnie 60 dni)
- **Koszt:** Darmowe, bez klucza API
- **Tickery:**

| Ticker | Co reprezentuje | Rola |
|---|---|---|
| `^GSPC` | S&P 500 | Główny instrument |
| `^VIX` | CBOE Volatility Index | Zmienność, strach rynkowy |
| `TLT` | 20+ Year Treasury Bond ETF | Korelacja z obligacjami |
| `GLD` | Gold ETF | Risk-off indicator |
| `DX-Y.NYB` | US Dollar Index | Siła dolara |
| `HYG` | High Yield Corporate Bond ETF | Spread kredytowy (risk-on) |
| `LQD` | Investment Grade Corporate Bond ETF | Spread kredytowy (baseline) |
| `SPY` | S&P 500 ETF | Wolumen, put/call proxy |

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
    interval VARCHAR(5) NOT NULL,
    source VARCHAR(20) DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, interval)
)

-- ─── Reżim rynkowy ─────────────────────────────────────────────

regime_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    interval VARCHAR(5) NOT NULL,
    regime VARCHAR(20) NOT NULL,
    adx_value DECIMAL(6,2),
    sma50 DECIMAL(10,2),
    sma200 DECIMAL(10,2),
    -- v2.1: rozszerzone o dane kwantowe
    vix_value DECIMAL(6,2),
    vix_regime VARCHAR(15),            -- 'LOW', 'NORMAL', 'ELEVATED', 'PANIC'
    breadth_pct_above_sma50 DECIMAL(5,2),
    confidence DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── [NOWE v2.0] Model pozycji ─────────────────────────────────

positions (
    id SERIAL PRIMARY KEY,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    signal_id INTEGER REFERENCES signals(id),
    direction VARCHAR(5) NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    size_pct DECIMAL(5,2),
    status VARCHAR(10) NOT NULL DEFAULT 'OPEN',
    close_reason VARCHAR(20),
    pnl_amount DECIMAL(12,2),
    pnl_percent DECIMAL(6,2),
    max_favorable_excursion DECIMAL(10,2),
    max_adverse_excursion DECIMAL(10,2),
    bars_held INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── [NOWE v2.0] Stan portfela ─────────────────────────────────

portfolio_state (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    starting_capital DECIMAL(12,2) DEFAULT 100000,
    current_capital DECIMAL(12,2) NOT NULL,
    current_position VARCHAR(5) DEFAULT 'FLAT',
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
    type VARCHAR(10) NOT NULL,
    confidence INTEGER NOT NULL,
    reasoning TEXT,
    entry_price DECIMAL(10,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    regime VARCHAR(20),
    interval VARCHAR(5),
    status VARCHAR(20) DEFAULT 'pending',
    current_position VARCHAR(5),
    position_entry_price DECIMAL(10,2),
    position_pnl_pct DECIMAL(6,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- ─── Wyniki sygnałów (feedback loop) ────────────────────────────

signal_results (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id) ON DELETE CASCADE,
    price_after_1h DECIMAL(10,2),
    price_after_4h DECIMAL(10,2),
    price_after_1d DECIMAL(10,2),
    price_after_5d DECIMAL(10,2),
    max_favorable DECIMAL(10,2),
    max_adverse DECIMAL(10,2),
    hit_tp BOOLEAN DEFAULT FALSE,
    hit_sl BOOLEAN DEFAULT FALSE,
    hit_tp_first BOOLEAN,
    outcome VARCHAR(10),
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

-- ─── [NOWE v2.1] Snapshot wskaźników kwantowych ─────────────────

quant_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    interval VARCHAR(5) NOT NULL,

    -- Zmienność
    vix DECIMAL(6,2),
    vix_sma20 DECIMAL(6,2),
    vix_percentile_252d DECIMAL(5,2),  -- percentyl VIX vs ostatnie 252 dni
    vix_term_structure VARCHAR(15),     -- 'CONTANGO', 'BACKWARDATION', 'FLAT'
    historical_vol_20d DECIMAL(6,2),    -- HV 20-dniowa
    iv_hv_spread DECIMAL(6,2),         -- VIX minus HV (implied vs realized)
    atr_percentile_252d DECIMAL(5,2),  -- percentyl ATR

    -- Szerokość rynku (Market Breadth)
    pct_above_sma50 DECIMAL(5,2),      -- % spółek S&P 500 > SMA 50
    pct_above_sma200 DECIMAL(5,2),     -- % spółek S&P 500 > SMA 200
    advance_decline_ratio DECIMAL(6,2),
    new_highs_minus_lows INTEGER,

    -- Sentiment
    put_call_ratio DECIMAL(6,3),
    put_call_sma10 DECIMAL(6,3),       -- wygładzone, mniej szumu

    -- Statystyczne
    z_score_50d DECIMAL(6,3),          -- Z-Score ceny vs SMA 50
    z_score_200d DECIMAL(6,3),         -- Z-Score ceny vs SMA 200
    hurst_exponent DECIMAL(5,3),       -- 0-1: <0.5 mean-revert, >0.5 trending

    -- Międzyrynkowe (Cross-Market)
    corr_sp500_tlt_30d DECIMAL(5,3),   -- korelacja S&P vs obligacje (30 dni)
    corr_sp500_gold_30d DECIMAL(5,3),  -- korelacja S&P vs złoto
    credit_spread DECIMAL(6,3),        -- HYG yield - LQD yield (proxy)
    dxy_change_pct_20d DECIMAL(6,2),   -- zmiana dolara za 20 dni

    -- Composite score
    risk_score INTEGER,                 -- 0-100: 0=risk-on, 100=max risk-off
    quant_signal VARCHAR(15),           -- 'RISK_ON', 'RISK_OFF', 'NEUTRAL', 'EXTREME_FEAR', 'EXTREME_GREED'

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, interval)
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
    train_from DATE,
    train_to DATE,
    test_from DATE,
    test_to DATE,
    train_total_trades INTEGER,
    train_win_rate DECIMAL(5,2),
    train_profit_factor DECIMAL(6,2),
    train_sharpe DECIMAL(6,2),
    train_max_drawdown DECIMAL(6,2),
    train_return DECIMAL(8,2),
    test_total_trades INTEGER,
    test_win_rate DECIMAL(5,2),
    test_profit_factor DECIMAL(6,2),
    test_sharpe DECIMAL(6,2),
    test_max_drawdown DECIMAL(6,2),
    test_return DECIMAL(8,2),
    degradation_win_rate DECIMAL(5,2),
    degradation_sharpe DECIMAL(6,2),
    is_overfit BOOLEAN DEFAULT FALSE,
    equity_curve JSONB,
    results_detail JSONB
)

-- ─── Historia chatów z agentem ───────────────────────────────────

chat_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    role VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    context_json JSONB
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
- **[v2.0] Filtrowanie fałszywych breakoutów** — breakout wymaga: zamknięcia świecy powyżej/poniżej poziomu + wolumen > 1.5x średniego 20-dniowego wolumenu
- Output: JSON z listą wykrytych formacji + ich scoring

**VOLUME ANALYST**
- Oblicza: OBV, Volume Profile, wolumen relatywny
- Wykrywa: climax volume, dry-up volume, volume confirmation
- Output: JSON z oceną wolumenu

**[NOWE v2.1] QUANT ANALYST**
- Pobiera dane z dodatkowych tickerów (VIX, TLT, GLD, DXY, HYG, LQD)
- Oblicza wskaźniki kwantowe w 5 kategoriach:
  1. **Zmienność:** VIX, VIX percentyl, IV-HV spread, ATR percentyl, VIX term structure
  2. **Szerokość rynku:** % spółek > SMA 50/200, A/D ratio, NH-NL
  3. **Sentiment:** Put/Call ratio (wygładzone SMA 10)
  4. **Statystyczne:** Z-Score (50d, 200d), Hurst Exponent
  5. **Międzyrynkowe:** korelacja S&P vs TLT/Gold, credit spread (HYG-LQD), zmiana DXY
- Oblicza composite **Risk Score (0-100)** i **Quant Signal** (RISK_ON / RISK_OFF / NEUTRAL / EXTREME_FEAR / EXTREME_GREED)
- Zapisuje snapshot w tabeli `quant_snapshots`
- Output: JSON z pełnym zestawem wskaźników kwantowych

#### Agenty AI (Claude API — rozumują, decydują)

**ORCHESTRATOR**
- Otrzymuje raporty od **czterech** agentów algorytmicznych (Trend + Pattern + Volume + **Quant**)
- Otrzymuje kontekst: ostatnie N sygnałów i ich wyniki
- **[v2.0] Otrzymuje stan pozycji:** czy jest otwarta pozycja, w jakim kierunku, jaki P&L
- **[v2.1] Otrzymuje Risk Score i Quant Signal** — modyfikuje confidence:
  - EXTREME_FEAR + sygnał BUY → confidence boost +10 (contrarian)
  - EXTREME_GREED + sygnał BUY → confidence penalty -15 (ostrzeżenie)
  - RISK_OFF + sygnał BUY → confidence penalty -10
  - Breadth divergence (indeks rośnie, breadth spada) → blokada sygnałów BUY
- Generuje: sygnał (BUY/SELL/SHORT/HOLD), confidence (0-100), uzasadnienie, SL/TP
- **[v2.0] Nie generuje BUY jeśli jest już LONG** (chyba że doważenie z uzasadnieniem)
- Próg powiadomienia: confidence ≥ 75 (konfigurowalny)

**RISK MANAGER**
- Ocenia ryzyko przed zatwierdzeniem sygnału
- Sprawdza: ATR-based stop-loss, risk/reward ratio (min 1:2), max drawdown
- Może zablokować sygnał Orchestratora jeśli ryzyko zbyt wysokie
- **[v2.1] Uwzględnia VIX:** gdy VIX > 30, automatycznie zmniejsza position size o 50%
- **[v2.0] Sugeruje position sizing** na podstawie: aktualnego kapitału, ATR, max risk per trade (domyślnie 2% kapitału)

**CHAT AGENT**
- Interfejs konwersacyjny — odpowiada na pytania o rynek
- Ma dostęp do: aktualnych danych, raportów agentów, historii sygnałów, stanu pozycji, **wskaźników kwantowych**
- Przykładowe pytania: "Jaki jest aktualny VIX?", "Czy breadth potwierdza trend?", "Jak wygląda korelacja z obligacjami?", "Jaki jest Risk Score?"

### Flow sygnału

```
[Co 4h: nowa świeca]
      │
      ▼
[Pobierz dane z Finnhub/yfinance]
[Pobierz dane: VIX, TLT, GLD, DXY, HYG, LQD]
      │
      ▼
[Trend Analyst] ──► raport JSON
[Pattern Analyst] ──► raport JSON (z filtrem fałszywych breakoutów)
[Volume Analyst] ──► raport JSON
[Quant Analyst] ──► raport JSON (Risk Score, breadth, VIX, korelacje)
      │
      ▼
[ORCHESTRATOR (Claude API)]
  + raporty 4 agentów
  + ostatnie 20 sygnałów i ich wyniki
  + aktualny reżim rynkowy (wzbogacony o dane kwantowe)
  + stan pozycji (LONG/SHORT/FLAT, entry price, P&L)
  + aktualny kapitał i ekspozycja
  + Risk Score i Quant Signal
      │
      ▼
[Propozycja sygnału]
      │
      ▼
[RISK MANAGER (Claude API)]
  + ocena ryzyka
  + position sizing (max 2% risk, 50% redukcja gdy VIX > 30)
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

## 4b. [NOWE v2.1] Wskaźniki kwantowe — szczegóły

### Kategoria 1: Zmienność (Volatility)

| Wskaźnik | Źródło | Obliczenie | Interpretacja |
|---|---|---|---|
| VIX | `^VIX` yfinance | Bezpośredni odczyt | < 15: niski strach; 15-25: norma; 25-35: elevated; > 35: panika |
| VIX Percentyl (252d) | `^VIX` historia | Percentyl bieżącego VIX vs 252 dni | > 90: ekstremalnie wysoki; < 10: ekstremalnie niski |
| VIX Term Structure | VIX vs VIX3M | VIX / VIX3M ratio | < 1: contango (spokój); > 1: backwardation (stress) |
| Historical Volatility | `^GSPC` | Std dev % zmian × √252, okno 20d | Rzeczywista zmienność, porównaj z VIX |
| IV-HV Spread | VIX - HV | VIX minus HV 20d | > 0: rynek przeszacowuje ryzyko; < 0: niedoszacowuje |
| ATR Percentyl (252d) | `^GSPC` ATR | Percentyl ATR(14) vs 252 dni | > 90: ekstremalnie wysoka zmienność |

### Kategoria 2: Szerokość rynku (Market Breadth)

| Wskaźnik | Źródło | Obliczenie | Interpretacja |
|---|---|---|---|
| % > SMA 50 | Komponenty S&P 500 | Ile spółek > swojego SMA 50 | > 70%: silny uptrend; < 30%: słaby rynek |
| % > SMA 200 | Komponenty S&P 500 | Ile spółek > swojego SMA 200 | > 60%: zdrowy rynek; < 40%: bear territory |
| A/D Ratio | yfinance volume data | Advancing / Declining stocks | Dywergencja z indeksem = ostrzeżenie |
| NH-NL | New Highs minus New Lows | 52-week highs minus lows | Rosnący = zdrowy trend; malejący = kruchy |

**Uwaga implementacyjna:** Obliczenie breadth wymaga danych wszystkich ~500 komponentów S&P 500. Podejście: pobranie listy komponentów z Wikipedii/yfinance, obliczanie raz dziennie (nie co 4h) ze względu na liczbę requestów.

### Kategoria 3: Sentiment

| Wskaźnik | Źródło | Obliczenie | Interpretacja |
|---|---|---|---|
| Put/Call Ratio | CBOE via Finnhub | Wolumen puts / calls | > 1.2: extreme fear (contrarian BUY); < 0.6: extreme greed (ostrzeżenie) |
| Put/Call SMA 10 | j.w. | Wygładzone SMA(10) | Redukuje szum dzienny |

### Kategoria 4: Statystyczne

| Wskaźnik | Źródło | Obliczenie | Interpretacja |
|---|---|---|---|
| Z-Score (50d) | `^GSPC` | (Cena - SMA50) / StdDev(50) | > 2: ekstremalnie wysoko; < -2: ekstremalnie nisko |
| Z-Score (200d) | `^GSPC` | (Cena - SMA200) / StdDev(200) | Jak wyżej, dłuższa perspektywa |
| Hurst Exponent | `^GSPC` | R/S analysis, okno 100d | > 0.5: trending; ≈ 0.5: random; < 0.5: mean-reverting |

### Kategoria 5: Międzyrynkowe (Cross-Market)

| Wskaźnik | Źródło | Obliczenie | Interpretacja |
|---|---|---|---|
| Korelacja S&P/TLT | `^GSPC` + `TLT` | Pearson 30-dniowy | Normalnie < 0 (ujemna). Gdy > 0 = oba spadają = stress |
| Korelacja S&P/Gold | `^GSPC` + `GLD` | Pearson 30-dniowy | Normalnie niska. Rosnąca = niepewność |
| Credit Spread | `HYG` + `LQD` | Return spread (proxy) | Rosnący spread = rosnące ryzyko systemowe |
| DXY Change 20d | `DX-Y.NYB` | % zmiana za 20 dni | Silny dolar zazwyczaj negatywny dla S&P |
| Copper/Gold Ratio | `HG=F` + `GLD` | Copper price / Gold price | Rosnący = optymizm; spadający = risk-off |

### Composite Risk Score (0-100)

Algorytm obliczający zagregowany Risk Score:

```python
def calculate_risk_score(quant_data):
    score = 50  # bazowy, neutralny
    
    # Zmienność (+/- 15 pkt)
    if vix > 30: score += 15
    elif vix > 25: score += 10
    elif vix < 15: score -= 10
    
    # VIX term structure (+/- 10 pkt)
    if vix_term == 'BACKWARDATION': score += 10
    elif vix_term == 'CONTANGO': score -= 5
    
    # Breadth (+/- 15 pkt)
    if pct_above_sma50 < 30: score += 15
    elif pct_above_sma50 > 70: score -= 10
    
    # Sentiment (+/- 10 pkt)
    if put_call_ratio > 1.2: score += 10   # extreme fear
    elif put_call_ratio < 0.6: score -= 10  # extreme greed (risk!)
    # Uwaga: high score = high RISK, ale extreme fear = contrarian opportunity
    
    # Cross-market (+/- 10 pkt)
    if corr_sp500_tlt > 0.3: score += 10   # oba spadają = stress
    if credit_spread_widening: score += 10
    
    # Z-Score (+/- 5 pkt)
    if z_score_50d > 2: score += 5         # overbought
    elif z_score_50d < -2: score -= 5      # oversold
    
    return clamp(score, 0, 100)
```

Mapowanie Risk Score → Quant Signal:

| Risk Score | Quant Signal | Znaczenie |
|---|---|---|
| 0-20 | EXTREME_GREED | Rynek ekstremalnie optymistyczny — ostrzeżenie |
| 20-40 | RISK_ON | Niskie ryzyko, sprzyjające warunki |
| 40-60 | NEUTRAL | Brak wyraźnego sygnału |
| 60-80 | RISK_OFF | Podwyższone ryzyko, ostrożność |
| 80-100 | EXTREME_FEAR | Panika — contrarian opportunity |

---

## 5. Identyfikacja reżimu rynkowego

### [ROZSZERZONE v2.1] Algorytm klasyfikacji

```
# Krok 1: Klasyczny reżim (cena + wskaźniki techniczne)
IF ADX > 25 AND cena > SMA50 > SMA200:
    technical_regime = "UPTREND"
IF ADX > 25 AND cena < SMA50 < SMA200:
    technical_regime = "DOWNTREND"
IF ADX < 20 OR (SMA50 ≈ SMA200 w zakresie 1%):
    technical_regime = "SIDEWAYS"
IF ADX 20-25:
    technical_regime = "TRANSITIONING"

# Krok 2: Walidacja kwantowa
IF technical_regime == "UPTREND":
    IF pct_above_sma50 < 40%:
        regime = "UPTREND_WEAK"        # indeks rośnie, ale breadth nie potwierdza
        confidence_penalty = -15
    ELIF quant_signal == "RISK_OFF":
        regime = "UPTREND_CAUTION"     # trend OK, ale ryzyko rośnie
        confidence_penalty = -10
    ELSE:
        regime = "UPTREND_STRONG"
        confidence_penalty = 0

IF technical_regime == "DOWNTREND":
    IF quant_signal == "EXTREME_FEAR":
        regime = "DOWNTREND_CAPITULATION"  # potencjalne dno (contrarian)
        confidence_bonus = +10 for BUY signals
    ELSE:
        regime = "DOWNTREND"
```

### Strategia per reżim (rozszerzona)

| Reżim | Strategia | Kluczowe wskaźniki | Uwagi |
|---|---|---|---|
| UPTREND_STRONG | Trend-following | EMA, MACD, breadth > 70% | Pełne pozycje, standardowy confidence |
| UPTREND_WEAK | Ostrożność | Breadth dywergencja | Mniejsze pozycje, wyższy próg confidence |
| UPTREND_CAUTION | Zmniejsz ekspozycję | VIX rośnie, credit spread rośnie | Trailing stop ciasno, gotowość na odwrót |
| DOWNTREND | Short / cash | EMA, MACD, VIX | SHORT na pullbackach |
| DOWNTREND_CAPITULATION | Contrarian BUY | VIX > 35, P/C > 1.2, Z-Score < -2 | Historycznie najlepsze punkty wejścia |
| SIDEWAYS | Mean-reversion | RSI, BB, S/R | Range trading |
| TRANSITIONING | Wait | ADX 20-25 | Minimalna aktywność |

---

## 6. Backtesting

### [ZMIANA v2.0] Przeniesiony do Fazy 2b — zaraz po wskaźnikach

Backtesting jest fundamentem, nie dodatkiem. Każdy wskaźnik i formacja jest weryfikowana na danych historycznych ZANIM trafi do agenta.

### Silnik
- Własny lekki engine w Pythonie (lub `backtrader`)
- Dane: yfinance historyczne S&P 500 (min. 10 lat daily, 60 dni 4h)
- Symulacja uwzględnia: prowizje, spread, slippage

### Podział danych — ochrona przed overfittingiem

```
Dane historyczne S&P 500 (2010–2026):

┌──────────────────────────────────┬─────────────────┐
│       TRAIN SET (70%)            │   TEST SET (30%) │
│       2010 — 2021                │   2022 — 2026    │
└──────────────────────────────────┴─────────────────┘

Reguła: jeśli test_win_rate < 0.8 × train_win_rate → OVERFIT
        jeśli test_sharpe < 0.7 × train_sharpe → OVERFIT
```

### Walk-forward testing

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
| Degradation | różnica train vs test win rate | < 20% |

---

## 7. Formacje świecowe — priorytetowe

### Formacje odwrócenia
- **Bullish Engulfing** — przy wsparciu, w downtrend → sygnał BUY
- **Bearish Engulfing** — przy oporze, w uptrend → sygnał SELL/SHORT
- **Hammer / Inverted Hammer** — przy wsparciu → potencjalne odwrócenie
- **Morning Star / Evening Star** — silne sygnały 3-świecowe
- **Doji** — niezdecydowanie, ważny przy ekstremalnych S/R

### Formacje kontynuacji
- **Three White Soldiers / Three Black Crows**
- **Rising / Falling Three Methods**
- **Bullish / Bearish Flag** (Price Action)

### Price Action
- **Higher Highs + Higher Lows** → uptrend
- **Lower Highs + Lower Lows** → downtrend
- **Break of Structure (BOS)** → kontynuacja
- **Change of Character (CHOCH)** → odwrócenie
- **Dywergencje** RSI/MACD vs cena → ostrzeżenie

### Filtrowanie fałszywych breakoutów

Breakout **potwierdzony** = zamknięcie świecy za poziomem + wolumen > 1.5x SMA(20).
Bez tego = "PENDING BREAKOUT" — monitoruj, nie sygnalizuj.

---

## 8. System uczenia się (Feedback Loop)

### Jasne reguły oceny sygnałów

**WIN:** W ciągu 5 dni: TP hit przed SL, LUB +2% przed SL hit.
**LOSS:** W ciągu 5 dni: SL hit przed TP, LUB -1.5% przed TP hit.
**EXPIRED:** Po 5 dniach brak TP/SL → P&L na zamknięciu 5. dnia.
**BREAKEVEN:** P&L w zakresie -0.3% do +0.3%.

### Mechanizm
1. **Logging:** Każdy sygnał z pełnym kontekstem + stanem pozycji + snapshot kwantowy
2. **Tracking:** Cron job śledzi cenę po 1h, 4h, 1D, 5D
3. **Evaluation:** Automatyczna ocena wg reguł
4. **Review:** Cotygodniowy raport skuteczności
5. **Context injection:** Przy analizie: ostatnie 20 sygnałów + wyniki + reguły + **quant context**
6. **Auto-adjustment:** Win rate < 45% przez 30 dni → próg confidence +5

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
  "quant_snapshot": {
    "vix": 18.5,
    "vix_percentile": 42,
    "vix_term_structure": "CONTANGO",
    "pct_above_sma50": 68,
    "pct_above_sma200": 72,
    "put_call_ratio": 0.85,
    "z_score_50d": 0.8,
    "hurst_exponent": 0.58,
    "corr_sp500_tlt_30d": -0.35,
    "credit_spread": "STABLE",
    "dxy_change_20d": -1.2,
    "risk_score": 35,
    "quant_signal": "RISK_ON"
  },
  "recent_signals": [ ... ],
  "performance_summary": { ... },
  "regime_accuracy": { ... },
  "evaluation_rules": { ... }
}
```

---

## 9. Live Performance Tracker (Equity Curve)

### Jak działa
1. Użytkownik ustawia wirtualny kapitał startowy (np. $100,000)
2. Każdy sygnał otwiera wirtualną pozycję w tabeli `positions`
3. Portfolio state aktualizowany w czasie rzeczywistym
4. Zamknięcie pozycji → P&L obliczony, equity curve zaktualizowana

### Wykresy
- **Equity Curve** — kapitał w czasie + benchmark (buy & hold S&P 500)
- **Drawdown Chart** — % spadek od szczytu equity
- **P&L per sygnał** — słupkowy (zielony/czerwony)
- **Rozkład zysków** — histogram
- **Performance by regime** — win rate w podziale na reżim

### Zasady zamykania pozycji
- Stop-loss hit → automatyczne zamknięcie
- Take-profit hit → automatyczne zamknięcie
- Przeciwny sygnał → BUY zamyka SHORT i odwrotnie
- Expiration → po 10 dniach (konfig.) zamknięcie po aktualnej cenie
- Ręczne zamknięcie → z interfejsu lub chatu z agentem

---

## 10. Frontend — widoki

### Dashboard (strona główna)
- Wykres świecowy S&P 500 (TradingView Lightweight Charts)
- Przełączanie interwałów: 4h / 1D / 1W
- Wskaźniki nakładane na wykres (toggle on/off)
- Panel boczny: reżim rynkowy, ostatni sygnał, confidence
- Status pozycji: LONG/SHORT/FLAT + aktualny P&L
- **[v2.1]** Mini-panel kwantowy: VIX, Risk Score, Quant Signal (kolorowy badge)

### Sygnały
- Lista sygnałów (aktywne, historyczne)
- Filtrowanie po typie, confidence, wyniku
- Szczegóły sygnału: uzasadnienie agenta + wykres + entry/SL/TP
- Kolumna "Ocena" (np. "WIN: TP hit day 3")

### [NOWE v2.1] Quant Dashboard
- **VIX Gauge** — wskazówka z kolorowym tłem (zielony/żółty/czerwony)
- **Risk Score Meter** — 0-100 z podziałem na strefy
- **Breadth Chart** — % spółek > SMA 50 i SMA 200 (liniowy, historyczny)
- **Put/Call Ratio Chart** — z zaznaczonymi strefami extreme fear/greed
- **Cross-Market Correlations** — heatmapa: S&P vs TLT, Gold, DXY
- **Z-Score Chart** — liniowy z bandami na +2/-2
- **Credit Spread Chart** — HYG-LQD spread w czasie
- **Quant Signal History** — timeline: kiedy był RISK_ON, RISK_OFF, EXTREME_FEAR itp.

### Performance (Zyski/Straty)
- Equity Curve + benchmark
- Drawdown Chart
- P&L per sygnał
- Metryki zbiorcze
- Porównanie z benchmarkiem
- Tabela transakcji

### Backtesting
- Formularz: strategia, okres, parametry
- Automatyczny train/test split
- Alert overfitting (degradacja > 20%)
- Walk-forward testing
- Porównanie strategii

### Chat z Agentem
- Interfejs czatowy z kontekstem: dane, wskaźniki, reżim, pozycja, kapitał, **wskaźniki kwantowe**

### Ustawienia
- Próg confidence dla powiadomień
- Konfiguracja email
- Kapitał startowy (wirtualny)
- Max risk per trade (domyślnie 2%)
- Okno oceny sygnału (domyślnie 5 dni)
- Wybór wskaźników do wyświetlania

---

## 11. Harmonogram realizacji

> Bez sztywnych tygodni. Każda faza trwa tyle, ile potrzeba.

| Faza | Zakres | Deliverable | Edukacja |
|---|---|---|---|
| **1. Fundament** | Setup projektu, baza, API dane, wykres świecowy | Działający dashboard z wykresem | Python, FastAPI, React basics |
| **2a. Wskaźniki tech.** | RSI, MACD, ADX, BB, reżim rynkowy | Wskaźniki na wykresie + panel reżimu | Co mówi RSI, MACD, ADX |
| **2b. Backtesting** | Silnik backtestingowy, train/test split | "Czy RSI < 30 daje zysk na S&P?" | Overfitting, statystyka |
| **2c. Wskaźniki kwant.** | VIX, breadth, sentiment, cross-market, Risk Score | Quant Dashboard + Risk Score | Zmienność, breadth, sentiment |
| **3. Formacje** | Pattern recognition, Price Action, S/R, filtr breakoutów | Formacje na wykresie + scoring | Formacje, Price Action |
| **4. Agent AI** | Multi-agent (4 analityków), Claude API, model pozycji, chat | Agent z kontekstem kwantowym | Prompt engineering, LLM |
| **5. Performance** | Equity curve, P&L tracking, benchmark | Dashboard performance | Metryki tradingowe |
| **6. Uczenie** | Feedback loop, kalibracja, alerty email | Agent śledzi wyniki, wysyła alerty | Statystyczna ocena strategii |
| **7. Deploy** | Railway + Cloudflare Pages, monitoring | Aplikacja live | DevOps, CI/CD |

### Dlaczego ta kolejność?

```
Faza 1  → Masz dane i wykres
Faza 2a → Masz wskaźniki techniczne
Faza 2b → WERYFIKUJESZ czy wskaźniki działają (zanim zbudujesz agenta!)
Faza 2c → Dodajesz "rentgen rynku" — widzisz głębiej niż klasyczna TA
Faza 3  → Dodajesz formacje (przetestowane w backtestingu)
Faza 4  → Agent ma SPRAWDZONE narzędzia + kwanty + wie o Twojej pozycji
Faza 5  → Śledzisz wyniki live
Faza 6  → Agent się uczy na jasnych regułach
Faza 7  → Deploy
```

---

## 12. API Endpoints (planowane)

```
# ─── Dane rynkowe ───────────────────────────
GET  /api/candles?interval=1D&from=...&to=...
GET  /api/quote
GET  /api/market-info
GET  /api/indicators?type=RSI&interval=1D&period=14
GET  /api/regime/current

# ─── Pozycje i portfel ──────────────────────
GET  /api/position/current
GET  /api/position/history
GET  /api/portfolio/state
POST /api/position/close

# ─── [NOWE v2.1] Wskaźniki kwantowe ─────────
GET  /api/quant/current                ← aktualny snapshot
GET  /api/quant/history?from=...&to=...← historia snapshotów
GET  /api/quant/risk-score             ← aktualny Risk Score + Quant Signal
GET  /api/quant/breadth                ← dane breadth (% > SMA)
GET  /api/quant/vix                    ← VIX + term structure
GET  /api/quant/correlations           ← cross-market korelacje
GET  /api/quant/sentiment              ← put/call + inne

# ─── Sygnały ────────────────────────────────
GET  /api/signals?status=active
GET  /api/signals/{id}
POST /api/signals/analyze

# ─── Backtesting ────────────────────────────
POST /api/backtest/run
GET  /api/backtest/results/{id}
GET  /api/backtest/results/{id}/overfit

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

# ─── System ─────────────────────────────────
GET  /api/health
```

---

## 13. Uwagi i ryzyka

- **yfinance** jest nieoficjalnym API — architektura modułowa minimalizuje ryzyko.
- **Claude API** — szacunkowo $5-10/mies. przy analizie co 4h.
- **Opóźnienie 20 min** na Finnhub free tier — nieistotne dla swing tradingu.
- **Breadth calculation** — wymaga pobrania danych ~500 spółek. Raz dziennie, nie co 4h. Przy 60 req/min na Finnhub = ~8 min. Alternatywnie: yfinance batch.
- **Backtesting ≠ przyszłe wyniki** — agent informuje o tym w każdym sygnale.
- **Nie jest to doradztwo inwestycyjne** — narzędzie wspomagające, decyzja należy do użytkownika.
- **Overfitting** — train/test split i walk-forward minimalizują ryzyko.
- **Model pozycji jest wirtualny** — brak połączenia z brokerem.
- **Hurst Exponent** — obliczenie wymaga minimum ~100 punktów danych i jest wrażliwe na parametry. Traktować jako wskaźnik pomocniczy, nie decyzyjny.
- **Korelacje się zmieniają** — korelacja S&P/TLT może zmieniać znak w różnych reżimach. Agent musi to rozumieć.

---

## 14. Komponent edukacyjny — co rozumieć przy każdej fazie

> Nie chodzi o kopiowanie kodu, ale o rozumienie DLACZEGO.

### Faza 1 — Fundament
- Jak działa REST API (request → response)
- Co to FastAPI i dlaczego Python jest dobry do analizy danych
- Jak React renderuje UI i co to state/props
- Co to świeca OHLCV (Open, High, Low, Close, Volume)

### Faza 2a — Wskaźniki techniczne
- **RSI** — mierzy siłę ruchów cenowych. ALE: w silnym trendzie RSI może siedzieć na 70+ tygodniami.
- **MACD** — momentum. Dywergencja = cena nowe szczyty, MACD nie → słabnący trend.
- **ADX** — siła trendu, NIE kierunek. > 25 = silny trend, < 20 = brak trendu.
- **Bollinger Bands** — kanał zmienności. Przydatne w konsolidacji, mylące w trendzie.
- Dlaczego reżim rynkowy jest ważny.

### Faza 2b — Backtesting
- Co to overfitting i dlaczego optymalizacja na przeszłości jest niebezpieczna
- Dlaczego dzielimy dane na train/test
- Co mówią metryki: Sharpe, profit factor, max drawdown
- Walk-forward testing — dlaczego jedno okno nie wystarczy

### Faza 2c — Wskaźniki kwantowe
- **VIX** — nie mierzy "strachu" wprost, lecz oczekiwaną zmienność implikowaną z cen opcji. VIX 20 nie znaczy "bój się" — to informacja, że rynek spodziewa się ~20% rocznej zmienności.
- **Breadth** — indeks może rosnąć ciągnięty przez 10 mega-capów, podczas gdy 400 spółek spada. Breadth to "rentgen" — pokazuje co dzieje się pod powierzchnią.
- **Z-Score** — ile odchyleń standardowych cena jest od średniej. Z-Score > 2 statystycznie zdarza się w ~2.5% przypadków — to informacja, NIE sygnał automatyczny.
- **Korelacje** — zmieniają się w czasie. Korelacja S&P/TLT -0.4 w spokojnym rynku może skoczyć do +0.5 w kryzysie (oba spadają). Zmiana korelacji to sygnał zmiany reżimu.
- **Contrarian thinking** — dlaczego EXTREME_FEAR może być okazją do kupna (wszyscy sprzedali, kto zostaje? kupujący). Ale nie zawsze — potrzebne potwierdzenie techniczne.
- **Risk Score** — to zagregowana miara, nie wyrocznia. Niska wartość (RISK_ON) nie znaczy "kupuj wszystko", wysoka (RISK_OFF) nie znaczy "sprzedaj wszystko". To jeden z wielu inputów do decyzji.

### Faza 3 — Formacje
- Dlaczego formacja BEZ kontekstu (reżim, S/R, wolumen) jest bezwartościowa
- Co to false breakout i jak się przed nim bronić
- Price Action — struktura rynku (HH/HL/LH/LL) ważniejsza niż pojedyncza formacja

### Faza 4 — Agent AI
- Jak działa Claude API (prompt → response)
- Prompt engineering — jak pisać instrukcje
- Dlaczego agent musi znać stan pozycji i dane kwantowe
- Ograniczenia LLM — halucynacje, brak prawdziwego "rozumienia" rynku

### Faza 5-6 — Performance i uczenie
- Equity curve > win rate (40% win rate może być zyskowne!)
- Profit factor > 1.5 to minimum
- Max drawdown 15% to dużo
- Jasne reguły oceny (WIN/LOSS/EXPIRED) konieczne do uczenia
