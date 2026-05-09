import { useState, useEffect } from "react";
import { getStrategies, runBacktest, runWalkForward } from "../api/client";
import BacktestForm from "../components/backtest/BacktestForm";
import BacktestResults from "../components/backtest/BacktestResults";
import WalkForwardResults from "../components/backtest/WalkForwardResults";

export default function BacktestView() {
  const [strategies, setStrategies] = useState({});
  const [result, setResult] = useState(null);
  const [wfResult, setWfResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [wfLoading, setWfLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStrategies().then(setStrategies).catch(console.error);
  }, []);

  async function handleRun(formData) {
    setLoading(true);
    setError(null);
    setResult(null);
    setWfResult(null);
    try {
      const r = await runBacktest(formData);
      setResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleWalkForward(formData) {
    setWfLoading(true);
    setError(null);
    setWfResult(null);
    try {
      const r = await runWalkForward({
        strategy: formData.strategy,
        interval: formData.interval,
        params: formData.params,
        initial_capital: formData.initial_capital,
      });
      setWfResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setWfLoading(false);
    }
  }

  return (
    <div className="backtest-view">
      <div className="backtest-header">
        <h2 className="backtest-title">Backtesting</h2>
        <p className="backtest-subtitle">
          Weryfikacja strategii na danych historycznych S&P 500 (2010–2026).
          Podział train/test z detekcją overfittingu.
        </p>
      </div>

      <div className="backtest-layout">
        <aside className="backtest-sidebar">
          <BacktestForm
            strategies={strategies}
            onRun={handleRun}
            onWalkForward={handleWalkForward}
            loading={loading}
            wfLoading={wfLoading}
          />
        </aside>

        <main className="backtest-main">
          {error && (
            <div className="error-state" style={{ height: "auto", padding: "16px" }}>
              {error}
            </div>
          )}

          {(loading || wfLoading) && (
            <div className="loading-state" style={{ height: "200px" }}>
              <div className="spinner" />
              {loading ? "Uruchamiam backtest…" : "Walk-forward testing…"}
            </div>
          )}

          {result && !loading && <BacktestResults result={result} />}
          {wfResult && !wfLoading && <WalkForwardResults result={wfResult} />}

          {!result && !wfResult && !loading && !wfLoading && !error && (
            <div className="backtest-empty">
              <p>Wybierz strategię i kliknij <strong>Uruchom backtest</strong></p>
              <p className="text-muted">Przykładowe pytanie: czy RSI &lt; 30 daje zysk na S&amp;P 500?</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
