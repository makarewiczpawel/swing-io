import { useState, useEffect } from "react";
import { runAnalysis, getSignals } from "../api/client";
import { signalsStore } from "../store/signalsStore";

const SIGNAL_COLOR = { BUY: "#10b981", SELL: "#ef4444", HOLD: "#f59e0b" };
const INTERVALS = ["1D", "4h", "1h"];

function ConfidenceBar({ value }) {
  const color = value >= 70 ? "#10b981" : value >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 2 }}>
        <span>CONFIDENCE</span><span style={{ color }}>{value}%</span>
      </div>
      <div style={{ height: 4, background: "var(--border)", borderRadius: 2 }}>
        <div style={{ width: `${value}%`, height: "100%", background: color, borderRadius: 2, transition: "width 0.5s" }} />
      </div>
    </div>
  );
}

function AnalystCard({ title, data }) {
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const hasError = data.error;
  return (
    <div className="sig-analyst-card">
      <button className="sig-analyst-header" onClick={() => setOpen(!open)}>
        <span>{title}</span>
        <span style={{ color: hasError ? "#ef4444" : "#10b981", fontSize: 10, fontFamily: "var(--font-mono)" }}>
          {hasError ? "ERR" : "OK"} {open ? "▲" : "▼"}
        </span>
      </button>
      {open && (
        <pre className="sig-analyst-body">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function SignalCard({ result }) {
  if (!result) return null;
  const sig = result.signal;
  const color = SIGNAL_COLOR[sig] ?? "#94a3b8";

  return (
    <div className="sig-result-card" style={{ borderColor: color }}>
      <div className="sig-result-header">
        <div className="sig-signal-badge" style={{ color, borderColor: color }}>{sig}</div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            {new Date(result.timestamp).toLocaleString("pl-PL")}
          </div>
          {!result.risk_approved && (
            <div style={{ fontSize: 10, color: "#ef4444", fontFamily: "var(--font-mono)", marginTop: 2 }}>
              ⚠ Risk Manager odrzucił
            </div>
          )}
        </div>
      </div>

      <ConfidenceBar value={result.confidence} />

      {sig !== "HOLD" && result.entry_price && (
        <div className="sig-levels">
          <div><span className="qs-label">Entry</span><span className="qs-value">{result.entry_price?.toFixed(2)}</span></div>
          <div><span className="qs-label">Stop Loss</span><span className="qs-value" style={{ color: "#ef4444" }}>{result.stop_loss?.toFixed(2) ?? "—"}</span></div>
          <div><span className="qs-label">Take Profit</span><span className="qs-value" style={{ color: "#10b981" }}>{result.take_profit?.toFixed(2) ?? "—"}</span></div>
          <div><span className="qs-label">R/R</span><span className="qs-value">{result.rr_ratio?.toFixed(2) ?? "—"}</span></div>
          <div><span className="qs-label">Size</span><span className="qs-value">{result.position_size_pct?.toFixed(1) ?? "—"}%</span></div>
        </div>
      )}

      {result.reasoning && (
        <p className="sig-reasoning">{result.reasoning}</p>
      )}

      {result.key_factors?.length > 0 && (
        <div className="sig-factors">
          {result.key_factors.map((f, i) => (
            <span key={i} className="sig-factor-chip">{f}</span>
          ))}
        </div>
      )}

      <div className="sig-analysts-grid">
        <AnalystCard title="Trend"   data={result.analysts?.trend} />
        <AnalystCard title="Pattern" data={result.analysts?.pattern} />
        <AnalystCard title="Volume"  data={result.analysts?.volume} />
        <AnalystCard title="Quant"   data={result.analysts?.quant} />
      </div>
    </div>
  );
}

const OUTCOME_STYLE = {
  WIN:       { color: "#10b981", label: "WIN" },
  LOSS:      { color: "#ef4444", label: "LOSS" },
  BREAKEVEN: { color: "#94a3b8", label: "BE" },
  EXPIRED:   { color: "#f59e0b", label: "EXP" },
  PENDING:   { color: "#475569", label: "…" },
  "N/A":     { color: "#1e293b", label: "" },
};

function HistoryRow({ sig, isSelected, onClick }) {
  const color = SIGNAL_COLOR[sig.signal] ?? "#94a3b8";
  const outcome = sig.outcome ? (OUTCOME_STYLE[sig.outcome] ?? OUTCOME_STYLE["N/A"]) : null;
  return (
    <div
      className={`sig-hist-row ${isSelected ? "sig-hist-row-selected" : ""}`}
      onClick={onClick}
      style={{ cursor: "pointer" }}
    >
      <span className="sig-hist-badge" style={{ color, borderColor: color }}>{sig.signal}</span>
      <span className="sig-hist-conf" style={{ color: sig.confidence >= 70 ? "#10b981" : "#f59e0b" }}>{sig.confidence}%</span>
      <span className="sig-hist-price">{sig.entry_price?.toFixed(0) ?? "—"}</span>
      <span className="sig-hist-date">{new Date(sig.timestamp).toLocaleDateString("pl-PL")}</span>
      {outcome?.label ? (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, color: outcome.color }}>{outcome.label}</span>
      ) : (
        <span />
      )}
      <span className="sig-hist-reason">{sig.reasoning?.slice(0, 50)}{sig.reasoning?.length > 50 ? "…" : ""}</span>

      {isSelected && (
        <div className="sig-hist-detail">
          {sig.reasoning && <p className="sig-hist-detail-text">{sig.reasoning}</p>}
          {sig.key_factors?.length > 0 && (
            <div className="sig-factors" style={{ marginTop: 6 }}>
              {sig.key_factors.map((f, i) => (
                <span key={i} className="sig-factor-chip">{f}</span>
              ))}
            </div>
          )}
          {sig.stop_loss && (
            <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 11, fontFamily: "var(--font-mono)" }}>
              <span>SL: <span style={{ color: "#ef4444" }}>{sig.stop_loss?.toFixed(2)}</span></span>
              <span>TP: <span style={{ color: "#10b981" }}>{sig.take_profit?.toFixed(2) ?? "—"}</span></span>
              {sig.rr_ratio && <span>R/R: {sig.rr_ratio?.toFixed(2)}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SignalsView() {
  const [interval, setIntervalVal] = useState("1D");
  const [result,   setResult]   = useState(() => signalsStore.result);
  const [history,  setHistory]  = useState(() => signalsStore.history);
  const [position, setPosition] = useState(() => signalsStore.position);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [selectedHistIdx, setSelectedHistIdx] = useState(null);

  useEffect(() => {
    // Only fetch from backend if store is empty
    if (signalsStore.history.length === 0) {
      getSignals().then(({ signals, position: pos }) => {
        const h = signals ?? [];
        setHistory(h);
        signalsStore.history = h;
        if (pos) { setPosition(pos); signalsStore.position = pos; }
      }).catch(() => {});
    }
  }, []);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runAnalysis(interval);
      setResult(res);
      signalsStore.result = res;

      const newHistory = [res, ...history].slice(0, 50);
      setHistory(newHistory);
      signalsStore.history = newHistory;

      const newPos = res.analysts ? {
        status: res.signal === "BUY" ? "LONG" : (res.signal === "SELL" ? "FLAT" : position?.status ?? "FLAT"),
        entry_price: res.signal === "BUY" ? res.entry_price : position?.entry_price,
        stop_loss: res.stop_loss,
        take_profit: res.take_profit,
      } : position;
      setPosition(newPos);
      signalsStore.position = newPos;

      setSelectedHistIdx(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleHistRow = (i) => setSelectedHistIdx((prev) => prev === i ? null : i);

  return (
    <div className="sig-view">
      {/* Toolbar */}
      <div className="sig-toolbar">
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {INTERVALS.map((iv) => (
            <button key={iv} className={`toolbar-btn ${interval === iv ? "active" : ""}`}
              onClick={() => setIntervalVal(iv)}>{iv}</button>
          ))}
        </div>
        <button className="sig-analyze-btn" onClick={analyze} disabled={loading}>
          {loading ? "Analizuję…" : "Analizuj rynek"}
        </button>
        {position && (
          <div className="sig-position-badge" style={{
            color: position.status === "LONG" ? "#10b981" : "#94a3b8",
            borderColor: position.status === "LONG" ? "#10b981" : "#1e293b",
          }}>
            {position.status}
            {position.status === "LONG" && position.entry_price && ` @ ${position.entry_price?.toFixed(0)}`}
          </div>
        )}
      </div>

      {error && <div className="error-state" style={{ height: 60 }}>Błąd: {error}</div>}

      <div className="sig-layout">
        {/* Latest result */}
        <div className="sig-main">
          {loading && (
            <div className="loading-state" style={{ height: 200 }}>
              <div className="spinner" /> Uruchamiam 4 agenty + Claude…
            </div>
          )}
          {!loading && result && <SignalCard result={result} />}
          {!loading && !result && (
            <div className="sig-empty">
              <p>Naciśnij "Analizuj rynek" aby uruchomić pełną analizę.</p>
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>
                4 agenty algorytmiczne → Orchestrator (Claude) → Risk Manager (Claude)
              </p>
            </div>
          )}
        </div>

        {/* History */}
        <div className="sig-history">
          <div className="pat-card-label" style={{ marginBottom: 8 }}>Historia sygnałów</div>
          {history.length === 0 && <p className="quant-hint">Brak sygnałów.</p>}
          {history.map((s, i) => (
            <HistoryRow
              key={i}
              sig={s}
              isSelected={selectedHistIdx === i}
              onClick={() => toggleHistRow(i)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
