export default function StatPanel({ stat }) {
  if (!stat) return null;

  const z50Color  = stat.z_score_50d  >  2 ? "#ef4444" : stat.z_score_50d  < -2 ? "#10b981" : "#94a3b8";
  const z200Color = stat.z_score_200d >  2 ? "#ef4444" : stat.z_score_200d < -2 ? "#10b981" : "#94a3b8";
  const hurstColor = stat.hurst_exponent > 0.55 ? "#10b981" : stat.hurst_exponent < 0.45 ? "#f59e0b" : "#94a3b8";

  return (
    <div className="quant-card">
      <div className="quant-card-label">Statystyczne</div>

      <div className="quant-stats-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div>
          <span className="qs-label">Z-Score 50d</span>
          <span className="qs-value" style={{ color: z50Color, fontSize: "18px" }}>
            {stat.z_score_50d > 0 ? "+" : ""}{stat.z_score_50d?.toFixed(2)}
          </span>
        </div>
        <div>
          <span className="qs-label">Z-Score 200d</span>
          <span className="qs-value" style={{ color: z200Color, fontSize: "18px" }}>
            {stat.z_score_200d > 0 ? "+" : ""}{stat.z_score_200d?.toFixed(2)}
          </span>
        </div>
      </div>

      <div style={{ marginTop: "12px" }}>
        <span className="qs-label">Hurst Exponent</span>
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "2px" }}>
          <span className="quant-big-value" style={{ color: hurstColor, fontSize: "22px" }}>
            {stat.hurst_exponent?.toFixed(3)}
          </span>
          <span className="quant-badge" style={{ color: hurstColor }}>
            {stat.hurst_interpretation}
          </span>
        </div>
      </div>

      <p className="quant-hint" style={{ marginTop: "8px" }}>
        {Math.abs(stat.z_score_50d) > 2
          ? `Z-Score ${stat.z_score_50d > 0 ? "powyżej +2" : "poniżej -2"} — cena statystycznie odchylona.`
          : "Z-Score w normalnym zakresie (±2σ)."}
      </p>
    </div>
  );
}
