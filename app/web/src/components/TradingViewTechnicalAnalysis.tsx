import { useEffect, useRef, useState } from "react";

const SCRIPT_ID = "tradingview-technical-analysis-script";
const SCRIPT_SRC = "https://www.tradingview-widget.com/w/en/tv-technical-analysis.js";

let scriptPromise: Promise<boolean> | null = null;

function loadTechnicalAnalysis(): Promise<boolean> {
  if (customElements.get("tv-technical-analysis")) return Promise.resolve(true);
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve) => {
    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    script.id = SCRIPT_ID;
    script.type = "module";
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve(Boolean(customElements.get("tv-technical-analysis")));
    script.onerror = () => {
      script.remove();
      scriptPromise = null;
      resolve(false);
    };
    if (!existing) document.head.appendChild(script);
  });
  return scriptPromise;
}

export default function TradingViewTechnicalAnalysis() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    let cancelled = false;
    loadTechnicalAnalysis().then((loaded) => {
      if (cancelled) return;
      if (!loaded || !containerRef.current) {
        setStatus("unavailable");
        return;
      }
      const widget = document.createElement("tv-technical-analysis");
      widget.setAttribute("symbol", "IDX:COMPOSITE");
      widget.setAttribute("interval", "1D");
      widget.setAttribute("theme", document.documentElement.classList.contains("dark") ? "dark" : "light");
      widget.setAttribute("locale", "en");
      containerRef.current.replaceChildren(widget);
      setStatus("ready");
    });
    return () => {
      cancelled = true;
      containerRef.current?.replaceChildren();
    };
  }, []);

  return (
    <section className="tradingview-analysis-card" aria-labelledby="tradingview-analysis-title" data-widget-status={status}>
      <div className="overview-widget-heading">
        <div>
          <div className="eyebrow-muted">TradingView · external context</div>
          <h3 id="tradingview-analysis-title">Technical analysis</h3>
        </div>
        <a href="https://www.tradingview.com/symbols/IDX-COMPOSITE/" target="_blank" rel="noreferrer">Open ↗</a>
      </div>
      <div ref={containerRef} className="tradingview-analysis-frame" aria-label="TradingView technical analysis for IDX Composite" hidden={status === "unavailable"}>
        {status === "loading" && <p className="tradingview-widget-fallback">Loading the IDX Composite technical summary…</p>}
      </div>
      <p className="tradingview-widget-note">Third-party market summary; separate from the selected release’s calculated readings.</p>
    </section>
  );
}
