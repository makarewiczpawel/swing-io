function CorrBadge({ label, value }) {
  if (value === null || value === undefined) return (
    <div className="corr-item"><span className="qs-label">{label}</span><span className="qs-value text-muted">N/A</span></div>
  );
  const abs = Math.abs(value);
  const color = abs > 0.5 ? (value > 0 ? "#ef4444" : "#10b981") : "#94a3b8";
  return (
    <div className="corr-item">
      <span className="qs-label">{label}</span>
      <span className="qs-value" style={{ color }}>{value > 0 ? "+" : ""}{value.toFixed(3)}</span>
    </div>
  );
}

export default function CrossMarketPanel({ cross }) {
  if (!cross) return null;

  const csChange = cross.credit_spread_change;
  const csColor = csChange === null ? "#94a3b8" : csChange > 0.5 ? "#ef4444" : csChange < -0.5 ? "#10b981" : "#f59e0b";
  const dxyColor = cross.dxy_change_20d === null ? "#94a3b8" : cross.dxy_change_20d > 1 ? "#ef4444" : cross.dxy_change_20d < -1 ? "#10b981" : "#94a3b8";

  return (
    <div className="quant-cross-panel">
      <h3 className="quant-chart-title">Cross-Market</h3>
      <div className="quant-cross-grid">

        <div className="quant-card quant-card-sm">
          <div className="quant-card-label">Korelacje 30d (rolling)</div>
          <CorrBadge label="S&P 500 / TLT" value={cross.corr_sp500_tlt_30d} />
          <CorrBadge label="S&P 500 / GLD" value={cross.corr_sp500_gold_30d} />
          <p className="quant-hint" style={{ marginTop: "6px" }}>
            {cross.corr_sp500_tlt_30d > 0.3
              ? "⚠ Korelacja S&P/TLT dodatnia — stress systemowy."
              : "Korelacja S&P/TLT ujemna — normalny reżim."}
          </p>
        </div>

        <div className="quant-card quant-card-sm">
          <div className="quant-card-label">Credit Spread (HYG–LQD, 30d)</div>
          <div className="quant-big-value" style={{ color: csColor, fontSize: "20px" }}>
            {cross.credit_spread_30d !== null ? `${cross.credit_spread_30d > 0 ? "+" : ""}${cross.credit_spread_30d?.toFixed(2)}%` : "N/A"}
          </div>
          {csChange !== null && (
            <div className="quant-badge" style={{ color: csColor }}>
              zmiana: {csChange > 0 ? "+" : ""}{csChange?.toFixed(2)} pkt
            </div>
          )}
          <p className="quant-hint">Rozszerzający się spread = rosnące ryzyko systemowe.</p>
        </div>

        <div className="quant-card quant-card-sm">
          <div className="quant-card-label">US Dollar Index (DXY)</div>
          <div className="quant-big-value" style={{ color: dxyColor, fontSize: "20px" }}>
            {cross.dxy_price?.toFixed(2) ?? "N/A"}
          </div>
          {cross.dxy_change_20d !== null && (
            <div className="quant-badge" style={{ color: dxyColor }}>
              20d: {cross.dxy_change_20d > 0 ? "+" : ""}{cross.dxy_change_20d?.toFixed(2)}%
            </div>
          )}
          <p className="quant-hint">Silny dolar zazwyczaj negatywny dla S&P.</p>
        </div>

        <div className="quant-card quant-card-sm">
          <div className="quant-card-label">Ceny aktywów</div>
          <div className="quant-stats-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div><span className="qs-label">TLT</span><span className="qs-value">{cross.tlt_price?.toFixed(2) ?? "—"}</span></div>
            <div><span className="qs-label">GLD</span><span className="qs-value">{cross.gld_price?.toFixed(2) ?? "—"}</span></div>
            <div><span className="qs-label">HYG</span><span className="qs-value">{cross.hyg_price?.toFixed(2) ?? "—"}</span></div>
            <div><span className="qs-label">LQD</span><span className="qs-value">{cross.lqd_price?.toFixed(2) ?? "—"}</span></div>
          </div>
        </div>

      </div>
    </div>
  );
}
