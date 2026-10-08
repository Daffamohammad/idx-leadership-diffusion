// TradingViewTechnicalAnalysis — official free technical-analysis embed.
//
// The widget uses TradingView's publicly available technical-analysis embed
// (s3.tradingview.com), injected lazily with a JSON config. It is for
// **context only**: dated IHSG history is the source of truth for the
// overview. TradingView data loads client-side from TradingView's servers;
// if the user's network blocks TradingView the card renders a distinct
// unavailable state with a retry action instead.
//
// References:
//   https://www.tradingview.com/widget-docs/widgets/technical-analysis/technical-analysis-gauge/

import { useCallback, useEffect, useRef, useState } from "react";

const SCRIPT_SRC = "https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js";

type WidgetStatus = "loading" | "ready" | "unavailable";

function buildConfig(colorTheme: "light" | "dark"): Record<string, unknown> {
  return {
    interval: "1D",
    width: "100%",
    height: 320,
    symbol: "IDX:COMPOSITE",
    showIntervalTabs: true,
    displayMode: "single",
    locale: "en",
    colorTheme,
    isTransparent: true,
  };
}

export default function TradingViewTechnicalAnalysis() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const probeTimerRef = useRef<number | null>(null);
  const [status, setStatus] = useState<WidgetStatus>("loading");
  const [attempt, setAttempt] = useState(0);

  // The embed's load probe fires 1.5s after the script resolves; track it so
  // an unmount before the probe cannot call setState on a dead component.
  useEffect(() => () => {
    if (probeTimerRef.current !== null) window.clearTimeout(probeTimerRef.current);
  }, []);

  const embed = useCallback(() => {
    const container = containerRef.current;
    if (!container) {
      setStatus("unavailable");
      return;
    }
    setStatus("loading");
    container.replaceChildren();
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.textContent = JSON.stringify(
      buildConfig(document.documentElement.classList.contains("dark") ? "dark" : "light"),
    );
    script.onload = () => {
      // The embed script injects its iframe synchronously on execution; if no
      // iframe appears the widget was blocked downstream.
      if (probeTimerRef.current !== null) window.clearTimeout(probeTimerRef.current);
      probeTimerRef.current = window.setTimeout(() => {
        if (!containerRef.current) return;
        if (containerRef.current.querySelector("iframe")) setStatus("ready");
        else {
          script.remove();
          setStatus("unavailable");
        }
      }, 1500);
    };
    script.onerror = () => {
      script.remove();
      setStatus("unavailable");
    };
    container.appendChild(script);
  }, []);

  useEffect(() => {
    embed();
  }, [embed, attempt]);

  return (
    <section className="tradingview-analysis-card" aria-labelledby="tradingview-analysis-title" data-widget-status={status}>
      <div className="overview-widget-heading">
        <div>
          <div className="eyebrow-muted">TradingView · external context</div>
          <h3 id="tradingview-analysis-title">Technical analysis</h3>
        </div>
        <a href="https://www.tradingview.com/symbols/IDX-COMPOSITE/" target="_blank" rel="noreferrer noopener">Open ↗</a>
      </div>
      <div className="tradingview-analysis-frame" aria-label="TradingView technical analysis for IDX Composite" hidden={status === "unavailable"}>
        {status === "loading" && <p className="tradingview-widget-fallback">Loading the IDX Composite technical summary…</p>}
        {/* The embed script is injected into this dedicated mount node, never
            into an element that also holds React-rendered children. Mixing
            imperative replaceChildren with React children crashes removal. */}
        <div ref={containerRef} style={{ height: "100%" }} />
      </div>
      {status === "unavailable" && (
        <div className="tradingview-widget-fallback">
          <p style={{ margin: "0 0 10px" }}>The external technical summary could not be loaded.</p>
          <button type="button" className="btn btn-outline" onClick={() => setAttempt((n) => n + 1)}>
            Retry
          </button>
        </div>
      )}
      <p className="tradingview-widget-note">Third-party market summary; separate from the selected date’s calculated readings.</p>
    </section>
  );
}
