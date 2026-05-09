function BreadthBar({ label, value }) {
  const color = value > 60 ? "#10b981" : value > 40 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginBottom: "8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "3px" }}>
        <span style={{ color: "var(--text-muted)" }}>{label}</span>
        <span style={{ color, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{value?.toFixed(1)}%</span>
      </div>
      <div style={{ height: "4px", background: "var(--border)", borderRadius: "2px" }}>
        <div style={{ width: `${value}%`, height: "100%", background: color, borderRadius: "2px", transition: "width 0.5s ease" }} />
      </div>
    </div>
  );
}

export default function BreadthPanel({ breadth }) {
  if (!breadth) return null;
  const overall = breadth.pct_above_sma50 > 60 && breadth.pct_above_sma200 > 50 ? "BULLISH" :
                  breadth.pct_above_sma50 < 40 ? "BEARISH" : "MIXED";
  const c = { BULLISH: "#10b981", BEARISH: "#ef4444", MIXED: "#f59e0b" }[overall];

  return (
    <div className="quant-card">
      <div className="quant-card-label">Breadth ({breadth.sample_size} spółek)</div>
      <div className="quant-big-value" style={{ color: c, fontSize: "20px" }}>{overall}</div>
      <div style={{ marginTop: "12px" }}>
        <BreadthBar label="Powyżej SMA 50" value={breadth.pct_above_sma50} />
        <BreadthBar label="Powyżej SMA 200" value={breadth.pct_above_sma200} />
      </div>
      <p className="quant-hint">
        {breadth.pct_above_sma50 < 40
          ? "Słaba szerokość rynku — uwaga na dywergencje."
          : breadth.pct_above_sma50 > 70
          ? "Silna szerokość rynku — broad-based rally."
          : "Szerokość rynku neutralna."}
      </p>
    </div>
  );
}
