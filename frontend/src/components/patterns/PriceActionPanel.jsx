const STRUCTURE_COLOR = {
  UPTREND:   "#10b981",
  DOWNTREND: "#ef4444",
  RANGING:   "#f59e0b",
};

function EventRow({ event, type }) {
  const color = event.direction === "bullish" ? "#10b981" : "#ef4444";
  return (
    <div className="pa-event-row">
      <span className="pa-event-badge" style={{ color, borderColor: color }}>
        {type}
      </span>
      <span className="pa-event-desc">{event.description}</span>
    </div>
  );
}

export default function PriceActionPanel({ priceAction }) {
  if (!priceAction) return null;
  const { structure, higher_highs: hh, higher_lows: hl, lower_highs: lh, lower_lows: ll, bos, choch } = priceAction;
  const color = STRUCTURE_COLOR[structure] ?? "#94a3b8";

  return (
    <div className="pat-card">
      <div className="pat-card-label">Price Action</div>

      <div className="pa-structure" style={{ color }}>{structure}</div>

      <div className="pa-flags">
        {hh && <span className="pa-flag pa-flag-bull">HH</span>}
        {hl && <span className="pa-flag pa-flag-bull">HL</span>}
        {lh && <span className="pa-flag pa-flag-bear">LH</span>}
        {ll && <span className="pa-flag pa-flag-bear">LL</span>}
        {!hh && !hl && !lh && !ll && <span className="pa-flag pa-flag-neut">—</span>}
      </div>

      {(bos?.length > 0 || choch?.length > 0) && (
        <div className="pa-events">
          {bos?.map((e, i) => <EventRow key={`bos${i}`} event={e} type="BOS" />)}
          {choch?.map((e, i) => <EventRow key={`choch${i}`} event={e} type="CHOCH" />)}
        </div>
      )}

      {!bos?.length && !choch?.length && (
        <p className="quant-hint" style={{ marginTop: 8 }}>Brak aktywnych zdarzeń BOS/CHOCH.</p>
      )}
    </div>
  );
}
