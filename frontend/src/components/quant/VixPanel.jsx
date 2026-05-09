const VIX_ZONES = [
  { max: 15, label: "NISKI",     color: "#10b981" },
  { max: 25, label: "NORMALNY",  color: "#94a3b8" },
  { max: 35, label: "ELEVATED",  color: "#f59e0b" },
  { max: 999, label: "PANIKA",   color: "#ef4444" },
];

function vixColor(vix) {
  return (VIX_ZONES.find((z) => vix <= z.max) || VIX_ZONES.at(-1)).color;
}

export default function VixPanel({ vol }) {
  if (!vol) return null;
  const c = vixColor(vol.vix);
  const termColor = { CONTANGO: "#10b981", BACKWARDATION: "#ef4444", FLAT: "#94a3b8", UNKNOWN: "#64748b" }[vol.vix_term_structure] || "#94a3b8";

  return (
    <div className="quant-card">
      <div className="quant-card-label">Zmienność</div>
      <div className="quant-big-value" style={{ color: c }}>VIX {vol.vix}</div>
      <div className="quant-badge" style={{ color: c }}>
        {vol.vix_regime} · {vol.vix_percentile_252d?.toFixed(0)}. percentyl
      </div>

      <div className="quant-stats-grid">
        <div><span className="qs-label">HV 20d</span><span className="qs-value">{vol.historical_vol_20d}%</span></div>
        <div><span className="qs-label">IV-HV</span><span className="qs-value" style={{ color: vol.iv_hv_spread > 0 ? "#f59e0b" : "#10b981" }}>{vol.iv_hv_spread > 0 ? "+" : ""}{vol.iv_hv_spread}</span></div>
        <div><span className="qs-label">ATR %ile</span><span className="qs-value">{vol.atr_percentile_252d?.toFixed(0)}</span></div>
        <div>
          <span className="qs-label">Term Structure</span>
          <span className="qs-value" style={{ color: termColor }}>{vol.vix_term_structure}</span>
        </div>
      </div>
    </div>
  );
}
