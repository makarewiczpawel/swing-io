const ZONES = [
  { max: 20,  label: "EXTREME GREED", color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  { max: 40,  label: "RISK ON",       color: "#10b981", bg: "rgba(16,185,129,0.12)" },
  { max: 60,  label: "NEUTRAL",       color: "#94a3b8", bg: "rgba(148,163,184,0.1)" },
  { max: 80,  label: "RISK OFF",      color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  { max: 100, label: "EXTREME FEAR",  color: "#ef4444", bg: "rgba(239,68,68,0.15)" },
];

function getZone(score) {
  return ZONES.find((z) => score <= z.max) || ZONES[ZONES.length - 1];
}

export default function RiskScoreMeter({ score, signal }) {
  const zone = getZone(score ?? 50);
  const pct = ((score ?? 50) / 100) * 100;

  return (
    <div className="quant-card quant-risk-card" style={{ borderColor: zone.color, background: zone.bg }}>
      <div className="quant-card-label">Risk Score</div>
      <div className="risk-score-number" style={{ color: zone.color }}>{score ?? "—"}</div>
      <div className="risk-score-signal" style={{ color: zone.color }}>{signal}</div>

      {/* Track */}
      <div className="risk-track">
        <div className="risk-track-fill" style={{ width: `${pct}%`, background: zone.color }} />
      </div>
      <div className="risk-track-labels">
        <span>0</span><span>RISK ON</span><span>NEUTRAL</span><span>RISK OFF</span><span>100</span>
      </div>

      {/* Zone explanation */}
      <p className="risk-zone-label" style={{ color: zone.color }}>{zone.label}</p>
    </div>
  );
}
