function MetricCard({ label, value, sub, color }) {
  return (
    <div className="bt-metric-card">
      <div className="bt-metric-label">{label}</div>
      <div className={`bt-metric-value ${color || ""}`}>{value}</div>
      {sub && <div className="bt-metric-sub">{sub}</div>}
    </div>
  );
}

export default function MetricsGrid({ metrics, title, accent }) {
  if (!metrics) return null;

  const pf = metrics.profit_factor >= 999 ? "∞" : metrics.profit_factor?.toFixed(2);

  return (
    <div className="bt-metrics-block">
      <h4 className="bt-metrics-title" style={{ color: accent }}>{title}</h4>
      <div className="bt-metrics-grid">
        <MetricCard label="Transakcje" value={metrics.total_trades} />
        <MetricCard
          label="Win Rate"
          value={`${metrics.win_rate}%`}
          sub={`${metrics.winning_trades} / ${metrics.total_trades}`}
          color={metrics.win_rate >= 50 ? "positive" : "negative"}
        />
        <MetricCard
          label="Return"
          value={`${metrics.total_return_pct > 0 ? "+" : ""}${metrics.total_return_pct}%`}
          color={metrics.total_return_pct >= 0 ? "positive" : "negative"}
        />
        <MetricCard
          label="Profit Factor"
          value={pf}
          color={metrics.profit_factor >= 1.5 ? "positive" : metrics.profit_factor >= 1 ? "neutral" : "negative"}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={metrics.sharpe_ratio?.toFixed(2)}
          color={metrics.sharpe_ratio >= 1 ? "positive" : metrics.sharpe_ratio >= 0 ? "neutral" : "negative"}
        />
        <MetricCard
          label="Max Drawdown"
          value={`${metrics.max_drawdown_pct?.toFixed(1)}%`}
          color={metrics.max_drawdown_pct >= -10 ? "neutral" : "negative"}
        />
        <MetricCard label="Śr. czas pozycji" value={`${metrics.avg_trade_duration_bars} dni`} />
        <MetricCard
          label="Śr. zysk / strata"
          value={`+${metrics.avg_win_pct?.toFixed(1)}% / ${metrics.avg_loss_pct?.toFixed(1)}%`}
        />
      </div>
    </div>
  );
}
