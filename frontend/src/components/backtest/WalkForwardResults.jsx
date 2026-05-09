export default function WalkForwardResults({ result }) {
  const { summary, rounds, strategy } = result;

  return (
    <div className="bt-results">
      <div className="bt-results-header">
        <div>
          <h3 className="bt-results-title">
            Walk-Forward — {strategy.replace(/_/g, " ")}
          </h3>
          <p className="text-muted" style={{ fontSize: "12px", marginTop: "2px" }}>
            {summary.total_rounds} rund | okno testowe: 1 rok
          </p>
        </div>
        <div className={summary.robust ? "bt-ok-badge" : "bt-overfit-badge"}>
          {summary.robust
            ? `✓ Strategia odporna (${summary.overfit_rounds}/${summary.total_rounds} overfit)`
            : `⚠ ${summary.overfit_rounds}/${summary.total_rounds} rund z overfittingiem`}
        </div>
      </div>

      {/* Summary */}
      <div className="bt-wf-summary">
        <div className="bt-metric-card">
          <div className="bt-metric-label">Śr. Win Rate (test)</div>
          <div className={`bt-metric-value ${summary.avg_test_win_rate >= 50 ? "positive" : "negative"}`}>
            {summary.avg_test_win_rate}%
          </div>
        </div>
        <div className="bt-metric-card">
          <div className="bt-metric-label">Śr. Return (test)</div>
          <div className={`bt-metric-value ${summary.avg_test_return_pct >= 0 ? "positive" : "negative"}`}>
            {summary.avg_test_return_pct > 0 ? "+" : ""}{summary.avg_test_return_pct}%
          </div>
        </div>
        <div className="bt-metric-card">
          <div className="bt-metric-label">Śr. Sharpe (test)</div>
          <div className={`bt-metric-value ${summary.avg_test_sharpe >= 1 ? "positive" : "neutral"}`}>
            {summary.avg_test_sharpe}
          </div>
        </div>
        <div className="bt-metric-card">
          <div className="bt-metric-label">Rundy overfit</div>
          <div className={`bt-metric-value ${summary.overfit_rounds === 0 ? "positive" : "negative"}`}>
            {summary.overfit_rounds} / {summary.total_rounds}
          </div>
        </div>
      </div>

      {/* Tabela rund */}
      <table className="bt-table" style={{ marginTop: "16px" }}>
        <thead>
          <tr>
            <th>Runda</th><th>Train</th><th>Test</th>
            <th>Win Rate train</th><th>Win Rate test</th>
            <th>Return test</th><th>Sharpe test</th>
            <th>Max DD test</th><th>Transakcje</th><th>Degradacja</th>
          </tr>
        </thead>
        <tbody>
          {rounds.map((r) => (
            <tr key={r.round} className={r.is_overfit ? "row-overfit" : ""}>
              <td>#{r.round}</td>
              <td className="text-muted">{r.train_from?.slice(0, 4)}–{r.train_to?.slice(0, 4)}</td>
              <td className="text-muted">{r.test_from?.slice(0, 7)}</td>
              {r.error ? (
                <td colSpan={7} className="negative">{r.error}</td>
              ) : (
                <>
                  <td>{r.train_win_rate}%</td>
                  <td className={r.test_win_rate >= 50 ? "positive" : "negative"}>{r.test_win_rate}%</td>
                  <td className={r.test_return_pct >= 0 ? "positive" : "negative"}>
                    {r.test_return_pct > 0 ? "+" : ""}{r.test_return_pct}%
                  </td>
                  <td>{r.test_sharpe}</td>
                  <td className="negative">{r.test_max_drawdown?.toFixed(1)}%</td>
                  <td>{r.test_total_trades}</td>
                  <td className={r.is_overfit ? "negative" : "positive"}>
                    {r.degradation_win_rate !== null ? `${r.degradation_win_rate}%` : "—"}
                    {r.is_overfit ? " ⚠" : ""}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
