import { useEffect, useRef, useState } from "react";

type HeatmapColor = "daily" | "ytd";

export default function TradingViewStockHeatmap({ color }: { color: HeatmapColor }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<"loading" | "loaded" | "unavailable">("loading");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const update = () => setDark(root.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    setStatus("loading");
    container.replaceChildren();

    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    container.appendChild(widget);

    const script = document.createElement("script");
    script.async = true;
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js";
    script.textContent = JSON.stringify({
      exchanges: [],
      dataSource: "AllID",
      grouping: "sector",
      blockSize: "market_cap_basic",
      blockColor: color === "ytd" ? "Perf.YTD" : "change",
      locale: "en",
      colorTheme: dark ? "dark" : "light",
      isDataSetEnabled: false,
      isZoomEnabled: true,
      hasSymbolTooltip: true,
      isMonoSize: false,
      width: "100%",
      height: "100%",
    });
    script.onload = () => setStatus("loaded");
    script.onerror = () => setStatus("unavailable");
    container.appendChild(script);

    const timeout = window.setTimeout(() => {
      if (!container.querySelector("iframe")) setStatus("unavailable");
    }, 15000);

    return () => {
      window.clearTimeout(timeout);
      script.onload = null;
      script.onerror = null;
      container.replaceChildren();
    };
  }, [color, dark]);

  return (
    <section className="tradingview-heatmap-card" aria-label="TradingView IDX stock heatmap">
      <div className="tradingview-heatmap-heading">
        <div>
          <div className="eyebrow-muted">External market context</div>
          <h2>Indonesia stocks by sector</h2>
        </div>
        <span className="eyebrow-muted" role="status" aria-live="polite">
          {status === "loading" ? "Loading TradingView…" : status === "loaded" ? "TradingView widget" : "TradingView did not load"}
        </span>
      </div>
      {status === "unavailable" && (
        <p className="tradingview-heatmap-fallback">
          TradingView could not load in this browser. The dated local snapshot heatmap remains available in the Snapshot tab.
        </p>
      )}
      <div ref={containerRef} className="tradingview-heatmap-frame" />
      <p className="meta tradingview-heatmap-note">
        TradingView supplies an external end-of-day market view. Its prices, timing, and coverage may differ from this app’s selected release and do not feed leadership or diffusion calculations. (Block size: listed market capitalization.)
      </p>
    </section>
  );
}
