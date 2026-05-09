-- swing.io — Database Schema v2.1
-- PostgreSQL (Railway)
-- Changelog: Removed trump_posts, added quant_snapshots, updated regime_log

CREATE TABLE IF NOT EXISTS candles (
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
);
CREATE INDEX idx_candles_interval_ts ON candles(interval, timestamp DESC);

CREATE TABLE IF NOT EXISTS regime_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    interval VARCHAR(5) NOT NULL,
    regime VARCHAR(20) NOT NULL,
    adx_value DECIMAL(6,2),
    sma50 DECIMAL(10,2),
    sma200 DECIMAL(10,2),
    vix_value DECIMAL(6,2),
    vix_regime VARCHAR(15),
    breadth_pct_above_sma50 DECIMAL(5,2),
    confidence DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_regime_ts ON regime_log(timestamp DESC);

CREATE TABLE IF NOT EXISTS signals (
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
);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_ts ON signals(timestamp DESC);

CREATE TABLE IF NOT EXISTS positions (
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
);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_ts ON positions(opened_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_state (
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
);

CREATE TABLE IF NOT EXISTS signal_results (
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
);

CREATE TABLE IF NOT EXISTS portfolio_equity (
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
);
CREATE INDEX idx_equity_ts ON portfolio_equity(timestamp DESC);

-- v2.1: Snapshoty wskaźników kwantowych
CREATE TABLE IF NOT EXISTS quant_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    interval VARCHAR(5) NOT NULL,
    -- Zmienność
    vix DECIMAL(6,2),
    vix_sma20 DECIMAL(6,2),
    vix_percentile_252d DECIMAL(5,2),
    vix_term_structure VARCHAR(15),
    historical_vol_20d DECIMAL(6,2),
    iv_hv_spread DECIMAL(6,2),
    atr_percentile_252d DECIMAL(5,2),
    -- Breadth
    pct_above_sma50 DECIMAL(5,2),
    pct_above_sma200 DECIMAL(5,2),
    advance_decline_ratio DECIMAL(6,2),
    new_highs_minus_lows INTEGER,
    -- Sentiment
    put_call_ratio DECIMAL(6,3),
    put_call_sma10 DECIMAL(6,3),
    -- Statystyczne
    z_score_50d DECIMAL(6,3),
    z_score_200d DECIMAL(6,3),
    hurst_exponent DECIMAL(5,3),
    -- Międzyrynkowe
    corr_sp500_tlt_30d DECIMAL(5,3),
    corr_sp500_gold_30d DECIMAL(5,3),
    credit_spread DECIMAL(6,3),
    dxy_change_pct_20d DECIMAL(6,2),
    -- Composite
    risk_score INTEGER,
    quant_signal VARCHAR(15),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, interval)
);
CREATE INDEX idx_quant_ts ON quant_snapshots(timestamp DESC);

CREATE TABLE IF NOT EXISTS agent_reports (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backtest_runs (
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
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    role VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    context_json JSONB
);
