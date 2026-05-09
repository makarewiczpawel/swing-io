const TOGGLES = [
  { key: "sma50",  label: "SMA 50",  color: "#f59e0b" },
  { key: "sma200", label: "SMA 200", color: "#6366f1" },
  { key: "ema9",   label: "EMA 9",   color: "#06b6d4" },
  { key: "ema21",  label: "EMA 21",  color: "#ec4899" },
  { key: "bb",     label: "BB",      color: "#94a3b8" },
];

export default function IndicatorToggles({ active, onChange }) {
  return (
    <div className="toolbar-group">
      <span className="toolbar-label">Wskaźniki</span>
      {TOGGLES.map(({ key, label, color }) => (
        <button
          key={key}
          className={`toolbar-btn indicator-btn ${active[key] ? "active" : ""}`}
          style={active[key] ? { borderColor: color, color } : {}}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
