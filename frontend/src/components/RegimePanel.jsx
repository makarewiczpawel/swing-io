const REGIME_CONFIG = {
  UPTREND:      { label: "UPTREND",      color: "#10b981", bg: "rgba(16,185,129,0.08)" },
  DOWNTREND:    { label: "DOWNTREND",    color: "#ef4444", bg: "rgba(239,68,68,0.08)"  },
  SIDEWAYS:     { label: "SIDEWAYS",     color: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
  TRANSITIONING:{ label: "TRANSITIONING",color: "#6366f1", bg: "rgba(99,102,241,0.08)"},
  UNKNOWN:      { label: "UNKNOWN",      color: "#64748b", bg: "rgba(100,116,139,0.08)"},
};

const STAT_LABELS = [
  { key: "adx",       label: "ADX",  fmt: (v) => Number(v).toFixed(1) },
  { key: "rsi",       label: "RSI",  fmt: (v) => Number(v).toFixed(1) },
  { key: "dmi_plus",  label: "DMI+", fmt: (v) => Number(v).toFixed(1) },
  { key: "dmi_minus", label: "DMI−", fmt: (v) => Number(v).toFixed(1) },
];

export default function RegimePanel({ regime, loading }) {
  if (loading) {
    return (
      <div className="regime-panel">
        <div className="regime-header">
          <span className="regime-dot" style={{ background: "#334155" }} />
          <span className="regime-loading">Ładowanie reżimu...</span>
        </div>
      </div>
    );
  }

  if (!regime) return null;

  const cfg = REGIME_CONFIG[regime.regime] ?? REGIME_CONFIG.UNKNOWN;
  const conf = Math.min(100, Math.max(0, regime.confidence ?? 0));

  return (
    <div className="regime-panel" style={{ borderLeftColor: cfg.color, background: cfg.bg }}>
      <div className="regime-header">
        <span className="regime-dot" style={{ background: cfg.color, boxShadow: `0 0 6px ${cfg.color}` }} />
        <span className="regime-label" style={{ color: cfg.color }}>{cfg.label}</span>

        <div className="regime-conf-track">
          <div
            className="regime-conf-fill"
            style={{ width: `${conf}%`, background: cfg.color }}
          />
        </div>

        <span className="regime-confidence">{conf.toFixed(0)}%</span>
      </div>

      <div className="regime-stats">
        {STAT_LABELS.map(({ key, label, fmt }) =>
          regime[key] != null ? (
            <span key={key} className="regime-stat-chip">
              <span className="regime-stat-key">{label}</span>
              <strong>{fmt(regime[key])}</strong>
            </span>
          ) : null
        )}
        {regime.description && (
          <span className="regime-description-inline">{regime.description}</span>
        )}
      </div>
    </div>
  );
}
