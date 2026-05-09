import { useEffect, useRef } from "react";
import { createChart, LineStyle } from "lightweight-charts";

export default function EquityChart({ trainEquity, testEquity, initialCapital }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || (!trainEquity?.length && !testEquity?.length)) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: "#111827" }, textColor: "#64748b",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      grid: { vertLines: { color: "rgba(30,41,59,0.5)" }, horzLines: { color: "rgba(30,41,59,0.5)" } },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: false },
      handleScroll: true, handleScale: true,
    });

    // Linia bazowa (initial capital)
    if (trainEquity?.length) {
      const baseline = chart.addLineSeries({
        color: "rgba(100,116,139,0.3)", lineWidth: 1,
        lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false,
      });
      baseline.setData([
        { time: trainEquity[0].time, value: initialCapital },
        { time: (testEquity?.length ? testEquity : trainEquity).at(-1).time, value: initialCapital },
      ]);
    }

    if (trainEquity?.length) {
      const s = chart.addLineSeries({ color: "#3b82f6", lineWidth: 2,
        priceLineVisible: false, lastValueVisible: true, title: "TRAIN" });
      s.setData(trainEquity);
    }

    if (testEquity?.length) {
      const s = chart.addLineSeries({ color: "#10b981", lineWidth: 2,
        priceLineVisible: false, lastValueVisible: true, title: "TEST" });
      s.setData(testEquity);
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(([e]) => {
      chart.applyOptions({ width: e.contentRect.width, height: e.contentRect.height });
    });
    ro.observe(containerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, [trainEquity, testEquity, initialCapital]);

  return <div ref={containerRef} style={{ width: "100%", height: "260px" }} />;
}
