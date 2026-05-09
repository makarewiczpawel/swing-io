const DIRECTION_COLOR = { bullish: "#10b981", bearish: "#ef4444", neutral: "#94a3b8" };
const DIRECTION_LABEL = { bullish: "BY", bearish: "NIEDŹ", neutral: "NEUT" };

function Strength({ n }) {
  return (
    <span className="pat-strength">
      {"★".repeat(n)}{"☆".repeat(3 - n)}
    </span>
  );
}

export default function PatternList({ patterns = [] }) {
  const sorted = [...patterns].reverse().slice(0, 25);

  if (!sorted.length) return (
    <div className="pat-card">
      <div className="pat-card-label">Formacje świecowe</div>
      <p className="quant-hint" style={{ marginTop: 8 }}>Brak formacji w wybranym zakresie.</p>
    </div>
  );

  return (
    <div className="pat-card">
      <div className="pat-card-label">Formacje świecowe ({patterns.length})</div>
      <div className="pat-list">
        {sorted.map((p, i) => {
          const color = DIRECTION_COLOR[p.direction] ?? "#94a3b8";
          return (
            <div key={i} className="pat-row">
              <span className="pat-dir-badge" style={{ color, borderColor: color }}>
                {DIRECTION_LABEL[p.direction] ?? p.direction.toUpperCase()}
              </span>
              <span className="pat-name">{p.type.replace(/_/g, " ")}</span>
              <Strength n={p.strength} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
