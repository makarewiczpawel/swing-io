import { useState, useEffect } from "react";

const DEFAULT_DATES = {
  train_from: "2010-01-01",
  train_to: "2021-12-31",
  test_from: "2022-01-01",
  test_to: "2026-05-01",
};

export default function BacktestForm({ strategies, onRun, onWalkForward, loading, wfLoading }) {
  const strategyNames = Object.keys(strategies);
  const [strategy, setStrategy] = useState("");
  const [params, setParams] = useState({});
  const [dates, setDates] = useState(DEFAULT_DATES);
  const [capital, setCapital] = useState(100000);

  // Ustaw domyślne params gdy zmienia się strategia
  useEffect(() => {
    if (strategy && strategies[strategy]) {
      setParams({ ...strategies[strategy].default_params });
    }
  }, [strategy, strategies]);

  // Ustaw pierwszą strategię gdy załadują się dane
  useEffect(() => {
    if (strategyNames.length > 0 && !strategy) {
      setStrategy(strategyNames[0]);
    }
  }, [strategyNames]);

  function buildPayload() {
    return {
      strategy,
      interval: "1D",
      ...dates,
      params,
      initial_capital: capital,
      commission_pct: 0.1,
      slippage_pct: 0.05,
    };
  }

  const paramLabels = strategies[strategy]?.param_labels || {};
  const isAnyLoading = loading || wfLoading;

  return (
    <div className="bt-form">
      <section className="bt-form-section">
        <label className="bt-label">Strategia</label>
        <select
          className="bt-select"
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
        >
          {strategyNames.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
          ))}
        </select>
        {strategy && strategies[strategy] && (
          <p className="bt-description">{strategies[strategy].description}</p>
        )}
      </section>

      {Object.keys(paramLabels).length > 0 && (
        <section className="bt-form-section">
          <label className="bt-label">Parametry</label>
          {Object.entries(paramLabels).map(([key, meta]) => (
            <div className="bt-param-row" key={key}>
              <label className="bt-param-label">{meta.label}</label>
              <input
                type="number"
                className="bt-input"
                value={params[key] ?? ""}
                min={meta.min}
                max={meta.max}
                step={meta.step}
                onChange={(e) =>
                  setParams((p) => ({ ...p, [key]: parseFloat(e.target.value) }))
                }
              />
            </div>
          ))}
        </section>
      )}

      <section className="bt-form-section">
        <label className="bt-label">Podział danych</label>
        <div className="bt-date-grid">
          <div>
            <span className="bt-sublabel">Train od</span>
            <input type="date" className="bt-input" value={dates.train_from}
              onChange={(e) => setDates((d) => ({ ...d, train_from: e.target.value }))} />
          </div>
          <div>
            <span className="bt-sublabel">Train do</span>
            <input type="date" className="bt-input" value={dates.train_to}
              onChange={(e) => setDates((d) => ({ ...d, train_to: e.target.value }))} />
          </div>
          <div>
            <span className="bt-sublabel">Test od</span>
            <input type="date" className="bt-input" value={dates.test_from}
              onChange={(e) => setDates((d) => ({ ...d, test_from: e.target.value }))} />
          </div>
          <div>
            <span className="bt-sublabel">Test do</span>
            <input type="date" className="bt-input" value={dates.test_to}
              onChange={(e) => setDates((d) => ({ ...d, test_to: e.target.value }))} />
          </div>
        </div>
      </section>

      <section className="bt-form-section">
        <label className="bt-label">Kapitał startowy ($)</label>
        <input
          type="number"
          className="bt-input"
          value={capital}
          min={1000}
          step={1000}
          onChange={(e) => setCapital(parseFloat(e.target.value))}
        />
      </section>

      <div className="bt-actions">
        <button
          className="bt-btn-primary"
          onClick={() => onRun(buildPayload())}
          disabled={!strategy || isAnyLoading}
        >
          {loading ? <><span className="spinner-sm" /> Trwa…</> : "Uruchom backtest"}
        </button>
        <button
          className="bt-btn-secondary"
          onClick={() => onWalkForward(buildPayload())}
          disabled={!strategy || isAnyLoading}
        >
          {wfLoading ? <><span className="spinner-sm" /> Trwa…</> : "Walk-forward (7 rund)"}
        </button>
      </div>
    </div>
  );
}
