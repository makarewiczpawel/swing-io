export default function SRPanel({ levels = [], currentPrice }) {
  if (!levels.length) return (
    <div className="pat-card">
      <div className="pat-card-label">Wsparcia / Opory</div>
      <p className="quant-hint" style={{ marginTop: 8 }}>Brak danych.</p>
    </div>
  );

  return (
    <div className="pat-card">
      <div className="pat-card-label">Wsparcia / Opory</div>
      <div className="sr-list">
        {levels.map((lev, i) => {
          const isSupport = lev.type === "support";
          const color = isSupport ? "#10b981" : "#ef4444";
          const dist = currentPrice
            ? ((lev.price - currentPrice) / currentPrice * 100).toFixed(2)
            : null;
          return (
            <div key={i} className="sr-row">
              <span className="sr-type-badge" style={{ color, borderColor: color }}>
                {isSupport ? "S" : "R"}
              </span>
              <span className="sr-price" style={{ color }}>{lev.price.toFixed(0)}</span>
              {dist !== null && (
                <span className="sr-dist" style={{ color: dist >= 0 ? "#f59e0b" : "#64748b" }}>
                  {dist >= 0 ? "+" : ""}{dist}%
                </span>
              )}
              <span className="sr-strength">{"●".repeat(Math.min(lev.strength, 4))}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
