import { useEffect, useRef } from "react";
import { createChart, CrosshairMode, LineStyle } from "lightweight-charts";

const INDICATOR_COLORS = {
  sma50:  "#f59e0b",
  sma200: "#6366f1",
  ema9:   "#06b6d4",
  ema21:  "#ec4899",
};

export default function CandlestickChart({ candles, indicators, activeIndicators, interval, srLevels, patternMarkers }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const overlaySeriesRef = useRef({});
  const priceLineRefs = useRef([]);

  // Inicjalizacja wykresu (re-tworzona tylko gdy zmienia się interwał)
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#0a0e17" },
        textColor: "#64748b",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 41, 59, 0.5)" },
        horzLines: { color: "rgba(30, 41, 59, 0.5)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(59, 130, 246, 0.3)", labelBackgroundColor: "#3b82f6" },
        horzLine: { color: "rgba(59, 130, 246, 0.3)", labelBackgroundColor: "#3b82f6" },
      },
      rightPriceScale: {
        borderColor: "#1e293b",
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: {
        borderColor: "#1e293b",
        timeVisible: interval === "1h" || interval === "4h",
        secondsVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      handleScroll: true,
      handleScale: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
      drawTicks: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    overlaySeriesRef.current = {};
    priceLineRefs.current = [];

    const resizeObserver = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      chart.applyOptions({ width, height });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      overlaySeriesRef.current = {};
      priceLineRefs.current = [];
    };
  }, [interval]);

  // Aktualizacja danych świecowych
  useEffect(() => {
    if (!candles || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    candleSeriesRef.current.setData(
      candles.map((c) => ({ time: c.timestamp, open: c.open, high: c.high, low: c.low, close: c.close }))
    );

    volumeSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.timestamp,
        value: c.volume,
        color: c.close >= c.open ? "rgba(16,185,129,0.25)" : "rgba(239,68,68,0.25)",
      }))
    );

    if (chartRef.current) chartRef.current.timeScale().fitContent();
  }, [candles]);

  // Aktualizacja serii nakładek — tylko gdy zmienią się dane wskaźników lub toggles
  useEffect(() => {
    if (!chartRef.current || !indicators) return;

    const chart = chartRef.current;
    const overlays = overlaySeriesRef.current;

    // Pomocnik: dodaj lub usuń serię linii
    function setLineSeries(key, data, color, lineWidth = 1, lineStyle = LineStyle.Solid) {
      const shouldShow = activeIndicators[key] && data?.length > 0;
      if (shouldShow) {
        if (!overlays[key]) {
          overlays[key] = chart.addLineSeries({
            color,
            lineWidth,
            lineStyle,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
        }
        overlays[key].setData(data);
      } else if (overlays[key]) {
        chart.removeSeries(overlays[key]);
        delete overlays[key];
      }
    }

    setLineSeries("sma50",  indicators.sma?.["50"],  INDICATOR_COLORS.sma50,  1);
    setLineSeries("sma200", indicators.sma?.["200"], INDICATOR_COLORS.sma200, 1);
    setLineSeries("ema9",   indicators.ema?.["9"],   INDICATOR_COLORS.ema9,   1);
    setLineSeries("ema21",  indicators.ema?.["21"],  INDICATOR_COLORS.ema21,  1);

    // Bollinger Bands — trzy linie + wypełnienie (upper/lower jako linie przerywane)
    if (activeIndicators.bb && indicators.bb?.length > 0) {
      const bbColor = "rgba(148,163,184,0.6)";
      if (!overlays.bbUpper) {
        overlays.bbUpper = chart.addLineSeries({ color: bbColor, lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        overlays.bbMiddle = chart.addLineSeries({ color: bbColor, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        overlays.bbLower = chart.addLineSeries({ color: bbColor, lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      }
      overlays.bbUpper.setData(indicators.bb.map((p) => ({ time: p.time, value: p.upper })));
      overlays.bbMiddle.setData(indicators.bb.map((p) => ({ time: p.time, value: p.middle })));
      overlays.bbLower.setData(indicators.bb.map((p) => ({ time: p.time, value: p.lower })));
    } else {
      ["bbUpper", "bbMiddle", "bbLower"].forEach((k) => {
        if (overlays[k]) { chart.removeSeries(overlays[k]); delete overlays[k]; }
      });
    }
  }, [indicators, activeIndicators]);

  // S/R price lines
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const series = candleSeriesRef.current;
    priceLineRefs.current.forEach((pl) => { try { series.removePriceLine(pl); } catch (_) {} });
    priceLineRefs.current = [];
    if (!srLevels?.length) return;
    srLevels.forEach((lev) => {
      const pl = series.createPriceLine({
        price: lev.price,
        color: lev.type === "support" ? "rgba(16,185,129,0.6)" : "rgba(239,68,68,0.6)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `${lev.type === "support" ? "S" : "R"}${lev.strength > 1 ? lev.strength : ""}`,
      });
      priceLineRefs.current.push(pl);
    });
  }, [srLevels]);

  // Pattern markers
  useEffect(() => {
    if (!candleSeriesRef.current || !patternMarkers?.length) {
      candleSeriesRef.current?.setMarkers?.([]);
      return;
    }
    const markers = patternMarkers
      .filter((m) => m.strength >= 2)
      .map((m) => ({
        time: m.time,
        position: m.direction === "bullish" ? "belowBar" : m.direction === "bearish" ? "aboveBar" : "inBar",
        color: m.direction === "bullish" ? "#10b981" : m.direction === "bearish" ? "#ef4444" : "#94a3b8",
        shape: m.direction === "bullish" ? "arrowUp" : m.direction === "bearish" ? "arrowDown" : "circle",
        text: m.type.replace(/_/g, " "),
        size: m.strength === 3 ? 2 : 1,
      }));
    try {
      candleSeriesRef.current.setMarkers(markers);
    } catch (_) {}
  }, [patternMarkers]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
