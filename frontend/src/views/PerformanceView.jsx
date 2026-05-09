import { useState, useEffect } from "react";
import { getPerformance, setCapital, getFeedbackStatus, setAlertsConfig, sendTestAlert } from "../api/client";
import QuantLineChart from "../components/quant/QuantLineChart";

function MetricCard({ label, value, sub, color }) {
  return (
    <div className="perf-metric-card">
      <span className="quant-card-label">{label}</span>
      <span className="perf-metric-value" style={{ color: color ?? "var(--text-primary)" }}>{value}</span>
      {sub && <span className="quant-hint" style={{ marginTop: 2 }}>{sub}</span>}
    </div>
  );
}

function OpenPositionBanner({ pos }) {
  if (!pos) return null;
  const color = pos.pnl_pct >= 0 ? "#10b981" : "#ef4444";
  return (
    <div className="perf-open-banner" style={{ borderColor: color }}>
      <span className="perf-open-label">OTWARTA POZYCJA</span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
        Entry: <b>{pos.entry_price?.toFixed(2)}</b>
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
        Cena: <b>{pos.current_price?.toFixed(2)}</b>
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color }}>
        P&L: <b>{pos.pnl_pct >= 0 ? "+" : ""}{pos.pnl_pct?.toFixed(2)}%</b>
        {" "}(<b>{pos.pnl_usd >= 0 ? "+" : ""}{pos.pnl_usd?.toFixed(0)}</b> USD)
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
        SL: {pos.stop_loss?.toFixed(2)} · TP: {pos.take_profit?.toFixed(2) ?? "—"} · Dzień {pos.days_open}/{10}
      </span>
    </div>
  );
}

function PnlBars({ trades }) {
  if (!trades?.length) return <p className="quant-hint">Brak zamkniętych transakcji.</p>;
  const maxAbs = Math.max(...trades.map(t => Math.abs(t.pnl_pct)));
  return (
    <div className="perf-pnl-bars">
      {trades.slice(0, 20).map((t, i) => {
        const pct = t.pnl_pct ?? 0;
        const color = pct >= 0 ? "#10b981" : "#ef4444";
        const width = maxAbs > 0 ? Math.abs(pct) / maxAbs * 100 : 0;
        return (
          <div key={i} className="perf-pnl-bar-row">
            <span className="perf-pnl-bar-date">{t.close_date}</span>
            <div className="perf-pnl-bar-track">
              <div className="perf-pnl-bar-fill" style={{ width: `${width}%`, background: color }} />
            </div>
            <span className="perf-pnl-bar-val" style={{ color }}>
              {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
            </span>
            <span className="perf-pnl-bar-reason">{t.close_reason}</span>
          </div>
        );
      })}
    </div>
  );
}

function TradesTable({ trades }) {
  if (!trades?.length) return null;
  const REASON_LABEL = { SL: "Stop Loss", TP: "Take Profit", EXPIRY: "Wygasła", MANUAL: "Ręczne", SIGNAL: "Sygnał" };
  return (
    <div className="perf-trades-table-wrap">
      <table className="perf-trades-table">
        <thead>
          <tr>
            <th>Otwarcie</th><th>Zamknięcie</th><th>Entry</th><th>Close</th>
            <th>P&L %</th><th>P&L $</th><th>Powód</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const color = t.win ? "#10b981" : "#ef4444";
            return (
              <tr key={i}>
                <td>{t.entry_date}</td>
                <td>{t.close_date}</td>
                <td style={{ fontFamily: "var(--font-mono)" }}>{t.entry_price?.toFixed(2)}</td>
                <td style={{ fontFamily: "var(--font-mono)" }}>{t.close_price?.toFixed(2)}</td>
                <td style={{ color, fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                  {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct?.toFixed(2)}%
                </td>
                <td style={{ color, fontFamily: "var(--font-mono)" }}>
                  {t.pnl_usd >= 0 ? "+" : ""}{t.pnl_usd?.toFixed(0)}
                </td>
                <td style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  {REASON_LABEL[t.close_reason] ?? t.close_reason}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CapitalForm({ current, onSet }) {
  const [val, setVal] = useState(String(current));
  const [loading, setLoading] = useState(false);
  const submit = async () => {
    const n = parseFloat(val.replace(/[^0-9.]/g, ""));
    if (!n || n <= 0) return;
    setLoading(true);
    try { await onSet(n); } finally { setLoading(false); }
  };
  return (
    <div className="perf-capital-form">
      <span className="quant-card-label">Kapitał startowy (USD)</span>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
        <input
          type="text" value={val} onChange={e => setVal(e.target.value)}
          className="perf-capital-input"
          onKeyDown={e => e.key === "Enter" && submit()}
        />
        <button className="toolbar-btn active" onClick={submit} disabled={loading}>
          {loading ? "…" : "Ustaw"}
        </button>
      </div>
      <p className="quant-hint">Uwaga: zmiana kapitału resetuje historię transakcji.</p>
    </div>
  );
}

function FeedbackPanel() {
  const [fb, setFb]         = useState(null);
  const [password, setPass] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [msg, setMsg]       = useState("");

  useEffect(() => {
    getFeedbackStatus().then(setFb).catch(() => {});
  }, []);

  const saveAlerts = async () => {
    try {
      await setAlertsConfig({ enabled, smtp_password: password });
      setMsg("Zapisano.");
      setTimeout(() => setMsg(""), 3000);
    } catch(e) { setMsg("Błąd: " + e.message); }
  };

  const testAlert = async () => {
    try {
      const r = await sendTestAlert();
      setMsg(r.sent ? "Email wysłany!" : "Alerty wyłączone lub brak konfiguracji SMTP.");
      setTimeout(() => setMsg(""), 4000);
    } catch(e) { setMsg("Błąd: " + e.message); }
  };

  return (
    <div className="perf-feedback-panel">
      <div className="perf-feedback-row">
        {/* Feedback stats */}
        <div>
          <span className="quant-card-label">Feedback Loop</span>
          {fb ? (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                Win rate 30d: <span style={{ color: fb.win_rate_30d >= 55 ? "#10b981" : fb.win_rate_30d >= 45 ? "#f59e0b" : "#ef4444", fontWeight: 700 }}>
                  {fb.win_rate_30d != null ? `${fb.win_rate_30d}%` : "—"}
                </span>
                <span style={{ color: "var(--text-muted)", marginLeft: 16 }}>
                  Win rate 7d: {fb.win_rate_7d != null ? `${fb.win_rate_7d}%` : "—"}
                </span>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-muted)" }}>
                Próg confidence: <span style={{ color: "var(--text-secondary)" }}>{fb.effective_threshold}%</span>
                {fb.confidence_adjustment > 0 && <span style={{ color: "#f59e0b" }}> (+{fb.confidence_adjustment} auto-korekta)</span>}
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
                Ocenionych sygnałów BUY: {fb.total_evaluated}
              </div>
            </div>
          ) : <p className="quant-hint">Ładowanie…</p>}
        </div>

        {/* Email config */}
        <div>
          <span className="quant-card-label">Alerty Email</span>
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
              Włącz alerty (BUY/SELL)
            </label>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="password"
                placeholder="Hasło aplikacji Gmail"
                value={password}
                onChange={e => setPass(e.target.value)}
                className="perf-capital-input"
                style={{ width: 200 }}
              />
              <button className="toolbar-btn active" onClick={saveAlerts}>Zapisz</button>
              <button className="toolbar-btn" onClick={testAlert}>Test</button>
            </div>
            {msg && <span style={{ fontSize: 11, color: "#10b981", fontFamily: "var(--font-mono)" }}>{msg}</span>}
            <p className="quant-hint">Adres: pawel.j.makarewicz@gmail.com · Gmail wymaga hasła aplikacji (nie hasła konta)</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PerformanceView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = () => {
    setLoading(true);
    getPerformance()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSetCapital = async (amount) => {
    await setCapital(amount);
    load();
  };

  if (loading) return (
    <div className="loading-state" style={{ height: 300 }}>
      <div className="spinner" /> Ładowanie danych performance…
    </div>
  );
  if (error) return <div className="error-state" style={{ height: 100 }}>Błąd: {error}</div>;
  if (!data)  return null;

  const { metrics: m, equity_curve, drawdown_curve, closed_trades, open_position,
          initial_capital, current_equity, total_return_pct, benchmark_return_pct } = data;

  const returnColor = total_return_pct >= 0 ? "#10b981" : "#ef4444";
  const benchColor  = (benchmark_return_pct ?? 0) >= 0 ? "#10b981" : "#ef4444";

  // Formatuj equity curve do QuantLineChart
  const equitySeries = equity_curve.length ? [
    {
      data: equity_curve.map(p => ({ time: Math.floor(new Date(p.date).getTime() / 1000), value: p.equity })),
      color: "#3b82f6", label: "Equity",
    },
    ...(equity_curve.some(p => p.benchmark != null) ? [{
      data: equity_curve.filter(p => p.benchmark != null)
                        .map(p => ({ time: Math.floor(new Date(p.date).getTime() / 1000), value: p.benchmark })),
      color: "#64748b", label: "Buy&Hold",
    }] : []),
  ] : null;

  const drawdownSeries = drawdown_curve.length ? [{
    data: drawdown_curve.map(p => ({ time: Math.floor(new Date(p.date).getTime() / 1000), value: p.drawdown })),
    color: "#ef4444", label: "Drawdown %",
  }] : null;

  return (
    <div className="perf-view">
      {/* Top metryki */}
      <div className="perf-metrics-row">
        <MetricCard label="Kapitał"       value={`$${current_equity.toLocaleString("pl-PL", { maximumFractionDigits: 0 })}`}
                    sub={`start: $${initial_capital.toLocaleString("pl-PL", { maximumFractionDigits: 0 })}`} />
        <MetricCard label="Zwrot"          value={`${total_return_pct >= 0 ? "+" : ""}${total_return_pct?.toFixed(2)}%`}
                    color={returnColor}
                    sub={benchmark_return_pct != null ? `Benchmark: ${benchmark_return_pct >= 0 ? "+" : ""}${benchmark_return_pct?.toFixed(2)}%` : "Brak benchmarka"} />
        <MetricCard label="Transakcje"     value={m.total_trades}
                    sub={`Win rate: ${m.win_rate}%`} />
        <MetricCard label="Śr. P&L"        value={`${m.avg_pnl_pct >= 0 ? "+" : ""}${m.avg_pnl_pct?.toFixed(2)}%`}
                    color={m.avg_pnl_pct >= 0 ? "#10b981" : "#ef4444"}
                    sub={`Win: +${m.avg_win_pct?.toFixed(2)}% / Loss: ${m.avg_loss_pct?.toFixed(2)}%`} />
        <MetricCard label="Profit Factor"  value={m.profit_factor?.toFixed(2) ?? "—"}
                    color={m.profit_factor >= 1.5 ? "#10b981" : m.profit_factor >= 1 ? "#f59e0b" : "#ef4444"} />
        <MetricCard label="Sharpe"         value={m.sharpe?.toFixed(2) ?? "—"}
                    color={m.sharpe >= 1 ? "#10b981" : m.sharpe >= 0 ? "#f59e0b" : "#ef4444"} />
      </div>

      {/* Otwarta pozycja */}
      <OpenPositionBanner pos={open_position} />

      {/* Wykresy */}
      {equitySeries ? (
        <div className="perf-charts-row">
          <div className="perf-chart-block">
            <h3 className="quant-chart-title">Equity Curve vs Buy&amp;Hold</h3>
            <QuantLineChart series={equitySeries}
              referenceLines={[{ value: initial_capital, color: "rgba(100,116,139,0.3)" }]}
              height={200} />
          </div>
          <div className="perf-chart-block">
            <h3 className="quant-chart-title">Drawdown (%)</h3>
            <QuantLineChart series={drawdownSeries}
              referenceLines={[{ value: 0, color: "rgba(100,116,139,0.3)" }, { value: -5, color: "rgba(245,158,11,0.3)" }, { value: -10, color: "rgba(239,68,68,0.3)" }]}
              height={200} />
          </div>
        </div>
      ) : (
        <div className="perf-empty-charts">
          <p>Wykresy pojawią się po zamknięciu pierwszej transakcji.</p>
        </div>
      )}

      {/* P&L bars + Tabela */}
      <div className="perf-bottom-row">
        <div className="perf-pnl-card">
          <h3 className="quant-chart-title">P&amp;L per transakcja</h3>
          <PnlBars trades={closed_trades} />
        </div>
        <div className="perf-trades-card">
          <h3 className="quant-chart-title">Historia transakcji</h3>
          <TradesTable trades={closed_trades} />
          {!closed_trades?.length && <p className="quant-hint">Brak zamkniętych transakcji.</p>}
        </div>
      </div>

      {/* Ustawienia kapitału + Feedback Loop */}
      <div className="perf-bottom-config">
        <CapitalForm current={initial_capital} onSet={handleSetCapital} />
        <FeedbackPanel />
      </div>
    </div>
  );
}
