import CandlestickChart from "../components/CandlestickChart";
import InfoPanel from "../components/InfoPanel";
import RegimePanel from "../components/RegimePanel";
import IndicatorToggles from "../components/IndicatorToggles";
import { useCandles, useIndicators, useRegime } from "../hooks/useMarketData";
import { useState } from "react";

const INTERVALS = [
  { id: "4h", label: "4H", days: 60 },
  { id: "1D", label: "1D", days: 365 },
  { id: "1W", label: "1W", days: 1825 },
];

const DAY_RANGES = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "2Y", days: 730 },
  { label: "5Y", days: 1825 },
  { label: "ALL", days: 3650 },
];

const DEFAULT_INDICATORS = { sma50: true, sma200: true, ema9: false, ema21: false, bb: false };

export default function DashboardView() {
  const [interval, setIntervalId] = useState("1D");
  const [days, setDays] = useState(365);
  const [activeIndicators, setActiveIndicators] = useState(DEFAULT_INDICATORS);

  const { data, loading, error, refetch } = useCandles(interval, days);
  const { data: indicators } = useIndicators(interval, days);
  const { regime, loading: regimeLoading } = useRegime(interval);

  const toggleIndicator = (key) =>
    setActiveIndicators((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <>
      <div className="chart-toolbar">
        <div className="toolbar-left">
          <div className="toolbar-group">
            <span className="toolbar-label">Interwał</span>
            {INTERVALS.map((intv) => (
              <button
                key={intv.id}
                className={`toolbar-btn ${interval === intv.id ? "active" : ""}`}
                onClick={() => { setIntervalId(intv.id); setDays(intv.days); }}
              >
                {intv.label}
              </button>
            ))}
          </div>
          <div className="toolbar-group">
            <span className="toolbar-label">Okres</span>
            {DAY_RANGES.map((r) => (
              <button
                key={r.label}
                className={`toolbar-btn ${days === r.days ? "active" : ""}`}
                onClick={() => setDays(r.days)}
              >
                {r.label}
              </button>
            ))}
          </div>
          <IndicatorToggles active={activeIndicators} onChange={toggleIndicator} />
        </div>
      </div>

      <RegimePanel regime={regime} loading={regimeLoading} />

      <div className="chart-container">
        {loading && (
          <div className="loading-state">
            <div className="spinner" /> Ładowanie danych S&P 500...
          </div>
        )}
        {error && (
          <div className="error-state">
            <span>Błąd: {error}</span>
            <button onClick={refetch}>Ponów</button>
          </div>
        )}
        {data && !loading && (
          <CandlestickChart
            candles={data.candles}
            indicators={indicators}
            activeIndicators={activeIndicators}
            interval={interval}
          />
        )}
      </div>

      <InfoPanel />
    </>
  );
}
