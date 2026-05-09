import { useState, useEffect } from "react";
import { getQuantSnapshot, getQuantVix, getQuantZScore, getQuantCorrelations } from "../api/client";
import RiskScoreMeter from "../components/quant/RiskScoreMeter";
import VixPanel from "../components/quant/VixPanel";
import BreadthPanel from "../components/quant/BreadthPanel";
import StatPanel from "../components/quant/StatPanel";
import CrossMarketPanel from "../components/quant/CrossMarketPanel";
import QuantLineChart from "../components/quant/QuantLineChart";

export default function QuantView() {
  const [snap, setSnap] = useState(null);
  const [vixHist, setVixHist] = useState(null);
  const [zHist, setZHist] = useState(null);
  const [corrHist, setCorrHist] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getQuantSnapshot(),
      getQuantVix(252),
      getQuantZScore(252),
      getQuantCorrelations(252),
    ])
      .then(([s, v, z, c]) => { setSnap(s); setVixHist(v); setZHist(z); setCorrHist(c); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="loading-state" style={{ height: "400px" }}>
      <div className="spinner" /> Ładowanie wskaźników kwantowych…
    </div>
  );

  if (error) return (
    <div className="error-state" style={{ height: "200px" }}>Błąd: {error}</div>
  );

  if (!snap) return null;

  const { volatility: vol, breadth, statistical: stat, cross_market: cross } = snap;

  return (
    <div className="quant-view">
      {/* Top row: Risk Score + VIX + Breadth */}
      <div className="quant-top-row">
        <RiskScoreMeter score={snap.risk_score} signal={snap.quant_signal} />
        <VixPanel vol={vol} />
        <BreadthPanel breadth={breadth} />
        <StatPanel stat={stat} />
      </div>

      {/* Wszystkie 3 wykresy w jednym rzędzie */}
      <div className="quant-charts-row quant-charts-3col">
        <div className="quant-chart-block">
          <h3 className="quant-chart-title">VIX vs HV 20d</h3>
          <QuantLineChart
            series={[
              { data: vixHist?.vix,    color: "#ef4444", label: "VIX" },
              { data: vixHist?.hv_20d, color: "#f59e0b", label: "HV 20d" },
            ]}
            referenceLines={[
              { value: 15, color: "rgba(16,185,129,0.4)" },
              { value: 25, color: "rgba(245,158,11,0.4)" },
              { value: 35, color: "rgba(239,68,68,0.4)"  },
            ]}
            height={180}
          />
        </div>

        <div className="quant-chart-block">
          <h3 className="quant-chart-title">Z-Score vs SMA 50 / 200</h3>
          <QuantLineChart
            series={[
              { data: zHist?.z_score_50d,  color: "#3b82f6", label: "Z 50d" },
              { data: zHist?.z_score_200d, color: "#6366f1", label: "Z 200d" },
            ]}
            referenceLines={[
              { value:  2, color: "rgba(239,68,68,0.4)"   },
              { value: -2, color: "rgba(16,185,129,0.4)"  },
              { value:  0, color: "rgba(100,116,139,0.3)" },
            ]}
            height={180}
          />
        </div>

        <div className="quant-chart-block">
          <h3 className="quant-chart-title">Korelacje (rolling 30d)</h3>
          <QuantLineChart
            series={[
              { data: corrHist?.sp500_tlt,  color: "#06b6d4", label: "S&P/TLT" },
              { data: corrHist?.sp500_gold, color: "#f59e0b", label: "S&P/GLD" },
              { data: corrHist?.sp500_dxy,  color: "#a78bfa", label: "S&P/DXY" },
            ]}
            referenceLines={[
              { value:  0.3, color: "rgba(239,68,68,0.3)"   },
              { value: -0.3, color: "rgba(16,185,129,0.3)"  },
              { value:  0,   color: "rgba(100,116,139,0.3)" },
            ]}
            height={180}
          />
        </div>
      </div>

      {/* Cross-market panel */}
      <CrossMarketPanel cross={cross} />
    </div>
  );
}
