import { useEffect, useMemo, useRef, useState } from "react";

type HeatmapColor = "daily" | "ytd";

export default function TradingViewStockHeatmap({ color }: { color: HeatmapColor }) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
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

  // Navigation or a color change destroys this document, including pending scripts.
  // A script injected into the app document can execute after its container is removed.
  const embedDocument = useMemo(() => {
    const configuration = JSON.stringify({
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
    return `<!doctype html><html><head><style>html,body,.tradingview-widget-container,.tradingview-widget-container__widget{width:100%;height:100%;margin:0}</style></head><body><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script async src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js">${configuration}</script></div></body></html>`;
  }, [color, dark]);

  useEffect(() => {
    setStatus("loading");
    const timeout = window.setTimeout(() => {
      if (!frameRef.current?.contentDocument?.querySelector("iframe")) setStatus("unavailable");
    }, 15000);
    return () => window.clearTimeout(timeout);
  }, [embedDocument]);

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
          TradingView could not load in this browser. The dated local heatmap remains available in the IDX stocks tab.
        </p>
      )}
      <iframe ref={frameRef} title="TradingView Indonesian stock heatmap" className="tradingview-heatmap-frame" style={{ width: "100%", border: 0 }} sandbox="allow-scripts allow-same-origin" srcDoc={embedDocument} onLoad={() => setStatus(frameRef.current?.contentDocument?.querySelector("iframe") ? "loaded" : "unavailable")} />
      <p className="meta tradingview-heatmap-note">
        TradingView supplies an external end-of-day market view. Its prices, timing, and coverage may differ from this app’s attached observations and do not feed leadership or diffusion calculations. (Block size: listed market capitalization.)
      </p>
    </section>
  );
}
