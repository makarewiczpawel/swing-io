import { useEffect, useRef } from "react";
import { createChart, LineStyle } from "lightweight-charts";

export default function QuantLineChart({ series = [], referenceLines = [], height = 180 }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !series.length) return;

    const initialH = ref.current.clientHeight || height;

    const chart = createChart(ref.current, {
      layout: { background: { color: "#111827" }, textColor: "#64748b",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
      grid: { vertLines: { color: "rgba(30,41,59,0.4)" }, horzLines: { color: "rgba(30,41,59,0.4)" } },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: false },
      handleScroll: true, handleScale: true,
      height: initialH,
    });

    for (const rl of referenceLines) {
      const s = chart.addLineSeries({
        color: rl.color, lineWidth: 1, lineStyle: LineStyle.Dashed,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      const firstSeries = series.find((s) => s.data?.length);
      if (firstSeries?.data?.length) {
        s.setData([
          { time: firstSeries.data[0].time,  value: rl.value },
          { time: firstSeries.data.at(-1).time, value: rl.value },
        ]);
      }
    }

    for (const s of series) {
      if (!s.data?.length) continue;
      const ls = chart.addLineSeries({
        color: s.color, lineWidth: 1.5,
        priceLineVisible: false, lastValueVisible: true, title: s.label ?? "",
        crosshairMarkerRadius: 3,
      });
      ls.setData(s.data);
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(([e]) => {
      const { width, height: h } = e.contentRect;
      chart.applyOptions({ width, height: h || height });
    });
    ro.observe(ref.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, [series, referenceLines, height]);

  return <div ref={ref} style={{ width: "100%", flex: 1, minHeight: 0 }} />;
}
