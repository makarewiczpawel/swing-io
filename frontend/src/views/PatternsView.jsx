import { useState, useEffect, useMemo } from "react";
import { getPatterns, getCandles } from "../api/client";
import CandlestickChart from "../components/CandlestickChart";
import PatternList from "../components/patterns/PatternList";
import SRPanel from "../components/patterns/SRPanel";
import PriceActionPanel from "../components/patterns/PriceActionPanel";
import DivBreakoutPanel from "../components/patterns/DivBreakoutPanel";
import { useSignals } from "../hooks/useMarketData";

function buildSignalMarkers(signals, candles) {
  if (!signals?.length || !candles?.length) return [];
  const candleTimes = candles.map((c) => c.timestamp);
  const findClosest = (t) => {
    let best = candleTimes[0], bestDiff = Math.abs(candleTimes[0] - t);
    for (const ct of candleTimes) {
      const d = Math.abs(ct - t);
      if (d < bestDiff) { best = ct; bestDiff = d; }
    }
    return best;
  };
  return signals
    .filter((s) => s.signal === "BUY" || s.signal === "SELL")
    .map((s) => {
      const t = Math.floor(new Date(s.timestamp).getTime() / 1000);
      const isBuy = s.signal === "BUY";
      return {
        time: findClosest(t),
        position: isBuy ? "belowBar" : "aboveBar",
        color: isBuy ? "#10b981" : "#ef4444",
        shape: isBuy ? "arrowUp" : "arrowDown",
        text: `${s.signal} ${s.confidence ?? ""}%`,
        size: 2,
      };
    });
}

const INTERVALS = ["1D", "4h", "1h"];
const DAY_OPTIONS = [90, 180, 365];

export default function PatternsView() {
  const [interval, setIntervalVal] = useState("1D");
  const [days, setDays] = useState(90);
  const [data, setData] = useState(null);
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getPatterns(interval, days),
      getCandles(interval, days),
    ])
      .then(([p, c]) => { setData(p); setCandles(c.candles ?? []); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [interval, days]);

  const currentPrice = candles.length ? candles[candles.length - 1].close : null;
  const { signals } = useSignals();
  const signalMarkers = useMemo(() => buildSignalMarkers(signals, candles), [signals, candles]);

  return (
    <div className="pat-view">
      {/* Toolbar */}
      <div className="pat-toolbar">
        <div className="pat-toolbar-group">
          <span className="pat-toolbar-label">Interwał</span>
          {INTERVALS.map((iv) => (
            <button
              key={iv}
              className={`toolbar-btn ${interval === iv ? "active" : ""}`}
              onClick={() => setIntervalVal(iv)}
            >{iv}</button>
          ))}
        </div>
        <div className="pat-toolbar-group">
          <span className="pat-toolbar-label">Zakres</span>
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              className={`toolbar-btn ${days === d ? "active" : ""}`}
              onClick={() => setDays(d)}
            >{d}d</button>
          ))}
        </div>
        {loading && <span className="pat-loading-badge">Ładowanie…</span>}
        {!loading && data && (
          <span className="pat-info-badge">
            {data.count} świec · {data.candle_patterns?.length ?? 0} formacji · {data.support_resistance?.length ?? 0} S/R
          </span>
        )}
      </div>

      {error && <div className="error-state" style={{ height: 80 }}>Błąd: {error}</div>}

      {/* Chart */}
      <div className="pat-chart-wrapper">
        <CandlestickChart
          candles={candles}
          interval={interval}
          srLevels={data?.support_resistance}
          patternMarkers={data?.candle_patterns}
          signalMarkers={signalMarkers}
        />
      </div>

      {/* Bottom panels */}
      <div className="pat-panels">
        <PatternList patterns={data?.candle_patterns ?? []} />
        <SRPanel levels={data?.support_resistance ?? []} currentPrice={currentPrice} />
        <PriceActionPanel priceAction={data?.price_action} />
        <DivBreakoutPanel
          divergences={data?.divergences ?? []}
          breakouts={data?.breakouts ?? []}
        />
      </div>
    </div>
  );
}
