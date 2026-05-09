const REGIME_CONFIG = {
  UPTREND: { label: "UPTREND", color: "#10b981", bg: "rgba(16,185,129,0.12)" },
  DOWNTREND: { label: "DOWNTREND", color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  SIDEWAYS: { label: "SIDEWAYS", color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  TRANSITIONING: { label: "TRANSITIONING", color: "#6366f1", bg: "rgba(99,102,241,0.12)" },
  UNKNOWN: { label: "UNKNOWN", color: "#64748b", bg: "rgba(100,116,139,0.12)" },
};

export default function RegimePanel({ regime, loading }) {
  if (loading) {
    return (
      <div className="regime-panel regime-loading">
        <span className="regime-dot" style={{ background: "#334155" }} />
        Ładowanie reżimu...
      </div>
    );
  }

  if (!regime) return null;

  const cfg = REGIME_CONFIG[regime.regime] ?? REGIME_CONFIG.UNKNOWN;

  return (
    <div className="regime-panel" style={{ borderColor: cfg.color, background: cfg.bg }}>
      <div className="regime-header">
        <span className="regime-dot" style={{ background: cfg.color }} />
        <span className="regime-label" style={{ color: cfg.color }}>{cfg.label}</span>
        <span className="regime-confidence">{regime.confidence?.toFixed(0)}% conf.</span>
      </div>
      <p className="regime-description">{regime.description}</p>
      <div className="regime-stats">
        <span>ADX <strong>{regime.adx}</strong></span>
        <span>RSI <strong>{regime.rsi?.toFixed(1)}</strong></span>
        <span>DMI+ <strong>{regime.dmi_plus}</strong></span>
        <span>DMI− <strong>{regime.dmi_minus}</strong></span>
      </div>
    </div>
  );
}
