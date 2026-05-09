function DivRow({ div }) {
  const color = div.type === "bullish" ? "#10b981" : "#ef4444";
  return (
    <div className="pa-event-row">
      <span className="pa-event-badge" style={{ color, borderColor: color }}>
        {div.indicator}
      </span>
      <span className="pa-event-desc">{div.description}</span>
    </div>
  );
}

function BreakoutRow({ bo }) {
  const color = bo.direction === "bullish" ? "#10b981" : "#ef4444";
  const confirmed = bo.type === "CONFIRMED";
  return (
    <div className="pa-event-row">
      <span className="pa-event-badge" style={{ color, borderColor: color }}>
        {confirmed ? "✓" : "?"} {bo.direction === "bullish" ? "↑" : "↓"}
      </span>
      <span className="pa-event-desc">{bo.description}</span>
    </div>
  );
}

export default function DivBreakoutPanel({ divergences = [], breakouts = [] }) {
  const hasDiv = divergences.length > 0;
  const hasBo  = breakouts.length > 0;

  return (
    <div className="pat-card">
      <div className="pat-card-label">Dywergencje</div>
      {hasDiv
        ? divergences.map((d, i) => <DivRow key={i} div={d} />)
        : <p className="quant-hint" style={{ marginTop: 6 }}>Brak dywergencji.</p>
      }

      <div className="pat-card-label" style={{ marginTop: 14 }}>Breakouty</div>
      {hasBo
        ? breakouts.map((b, i) => <BreakoutRow key={i} bo={b} />)
        : <p className="quant-hint" style={{ marginTop: 6 }}>Brak aktywnych breakoutów.</p>
      }
    </div>
  );
}
