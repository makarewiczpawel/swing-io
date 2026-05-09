import MetricsGrid from "./MetricsGrid";
import EquityChart from "./EquityChart";
import TradesTable from "./TradesTable";
import { useState } from "react";

export default function BacktestResults({ result }) {
  const [tab, setTab] = useState("overview");

  const { is_overfit, degradation_win_rate, degradation_sharpe } = result;

  return (
    <div className="bt-results">
      {/* Nagłówek */}
      <div className="bt-results-header">
        <div>
          <h3 className="bt-results-title">
            {result.strategy.replace(/_/g, " ")}
            <span className="bt-badge">{result.interval}</span>
          </h3>
          <p className="text-muted" style={{ fontSize: "12px", marginTop: "2px" }}>
            Train: {result.train_from} → {result.train_to} &nbsp;|&nbsp;
            Test: {result.test_from} → {result.test_to} &nbsp;|&nbsp;
            Kapitał: ${result.initial_capital?.toLocaleString()}
          </p>
        </div>

        {is_overfit ? (
          <div className="bt-overfit-badge">
            ⚠ OVERFIT — degradacja win rate: {degradation_win_rate}%
          </div>
        ) : (
          <div className="bt-ok-badge">
            ✓ Brak overfittingu ({degradation_win_rate ?? "—"}% degradacji)
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="bt-tabs">
        {["overview", "train_trades", "test_trades"].map((t) => (
          <button
            key={t}
            className={`bt-tab ${tab === t ? "active" : ""}`}
            onClick={() => setTab(t)}
          >
            {{ overview: "Wyniki", train_trades: "Transakcje TRAIN", test_trades: "Transakcje TEST" }[t]}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <div className="bt-metrics-row">
            <MetricsGrid metrics={result.train_metrics} title="TRAIN SET (2010–2021)" accent="#3b82f6" />
            <MetricsGrid metrics={result.test_metrics}  title="TEST SET (2022–2026)"  accent="#10b981" />
          </div>

          <div className="bt-chart-block">
            <h4 className="bt-section-label">Equity Curve (niebieski = TRAIN, zielony = TEST)</h4>
            <EquityChart
              trainEquity={result.train_equity}
              testEquity={result.test_equity}
              initialCapital={result.initial_capital}
            />
          </div>

          {(degradation_win_rate !== null || degradation_sharpe !== null) && (
            <div className={`bt-degradation ${is_overfit ? "overfit" : "ok"}`}>
              <strong>Degradacja:</strong>&nbsp;
              Win Rate: {degradation_win_rate ?? "—"}%&nbsp; | &nbsp;
              Sharpe: {degradation_sharpe ?? "—"}%
              {is_overfit
                ? " — strategia może być dopasowana do danych historycznych."
                : " — strategia jest odporna na nowe dane."}
            </div>
          )}
        </>
      )}

      {tab === "train_trades" && (
        <TradesTable trades={result.train_trades} title="TRAIN" />
      )}
      {tab === "test_trades" && (
        <TradesTable trades={result.test_trades} title="TEST" />
      )}
    </div>
  );
}
