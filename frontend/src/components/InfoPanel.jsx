import { useMarketInfo } from "../hooks/useMarketData";

/**
 * Panel dolny z informacjami o rynku.
 */
export default function InfoPanel() {
  const { info, loading } = useMarketInfo();

  if (loading || !info) {
    return (
      <div className="info-panel">
        <InfoCard label="Loading..." value="—" />
      </div>
    );
  }

  const trendStatus = info.above_sma_50 && info.above_sma_200
    ? { text: "BULLISH", class: "up" }
    : !info.above_sma_50 && !info.above_sma_200
    ? { text: "BEARISH", class: "down" }
    : { text: "MIXED", class: "neutral" };

  return (
    <div className="info-panel">
      <InfoCard
        label="52W High"
        value={info.high_52w.toLocaleString("en-US", { minimumFractionDigits: 2 })}
        sub={`${info.distance_from_high_pct.toFixed(2)}% od szczytu`}
      />
      <InfoCard
        label="52W Low"
        value={info.low_52w.toLocaleString("en-US", { minimumFractionDigits: 2 })}
      />
      <InfoCard
        label="SMA 50"
        value={info.sma_50.toLocaleString("en-US", { minimumFractionDigits: 2 })}
        sub={info.above_sma_50 ? "Cena powyżej ▲" : "Cena poniżej ▼"}
        valueClass={info.above_sma_50 ? "up" : "down"}
      />
      <InfoCard
        label="SMA 200"
        value={info.sma_200.toLocaleString("en-US", { minimumFractionDigits: 2 })}
        sub={info.above_sma_200 ? "Cena powyżej ▲" : "Cena poniżej ▼"}
        valueClass={info.above_sma_200 ? "up" : "down"}
      />
      <InfoCard
        label="Trend"
        value={trendStatus.text}
        valueClass={trendStatus.class}
        sub="SMA 50/200 cross"
      />
    </div>
  );
}

function InfoCard({ label, value, sub, valueClass = "" }) {
  return (
    <div className="info-card">
      <div className="info-card-label">{label}</div>
      <div className={`info-card-value ${valueClass}`}>{value}</div>
      {sub && <div className="info-card-sub">{sub}</div>}
    </div>
  );
}
