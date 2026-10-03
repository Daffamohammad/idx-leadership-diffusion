// TradingViewWidget — official free embed widget.
//
// The widget uses TradingView's publicly available advanced-chart embed,
// loading the script lazily (one shot per session). The widget is for
// **context only**: the methodology chart (PriceChart) is the source of
// truth for the persisted snapshot. TradingView data is loaded
// client-side from TradingView's servers; if the user's network blocks
// TradingView the snapshot fallback is rendered instead.
//
// References:
//   https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/
//   https://www.tradingview.com/widget-docs/widgets/symbol-info/

import { useEffect, useRef, useState } from "react";

interface TradingViewWidgetProps {
  ticker: string;
  exchange?: string;
  containerId?: string;
  onUnavailable?: (reason: TradingViewUnavailableReason) => void;
}

export type TradingViewUnavailableReason = "network" | "unsupported" | "error";

const SCRIPT_ID = "tradingview-advanced-chart-script";
const SCRIPT_SRC = "https://s3.tradingview.com/tv.js";

function sanitizeTicker(ticker: string, exchange: string): string | null {
  const cleaned = ticker.toUpperCase().trim();
  if (!cleaned.endsWith(".JK")) return null;
  return `${exchange}:${cleaned.replace(".JK", "")}`;
}

let scriptPromise: Promise<boolean> | null = null;
function loadScript(): Promise<boolean> {
  if (window.TradingView) return Promise.resolve(true);
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve) => {
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve(Boolean(window.TradingView));
    script.onerror = () => { script.remove(); scriptPromise = null; resolve(false); };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

interface EmbeddedWidget {
  remove?: () => void;
}

declare global {
  interface Window {
    TradingView?: {
      widget: new (config: Record<string, unknown>) => EmbeddedWidget;
    };
  }
}

export default function TradingViewWidget({
  ticker,
  exchange = "IDX",
  containerId,
  onUnavailable,
}: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const idRef = useRef<string>(
    containerId ?? `tv-widget-${Math.random().toString(36).slice(2, 10)}`,
  );
  const [status, setStatus] = useState<"loading" | "embedded" | "blocked" | "unsupported">(
    "loading",
  );
  const widgetRef = useRef<EmbeddedWidget | null>(null);
  const onUnavailableRef = useRef(onUnavailable);

  useEffect(() => {
    onUnavailableRef.current = onUnavailable;
  }, [onUnavailable]);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    const symbol = sanitizeTicker(ticker, exchange);
    if (!symbol) {
      setStatus("unsupported");
      onUnavailableRef.current?.("unsupported");
      return () => {};
    }
    loadScript().then((loaded) => {
      if (cancelled) return;
      if (!loaded || typeof window.TradingView === "undefined") {
        setStatus("blocked");
        onUnavailableRef.current?.("network");
        return;
      }
      if (!containerRef.current) return;
      containerRef.current.replaceChildren();
      const inner = document.createElement("div");
      inner.id = idRef.current;
      inner.style.height = "100%";
      inner.style.width = "100%";
      containerRef.current.appendChild(inner);
      try {
        widgetRef.current = new window.TradingView.widget({
          symbol,
          autosize: true,
          interval: "D",
          timezone: "Asia/Jakarta",
          theme: "light",
          style: "1",
          locale: "en",
          toolbar_bg: "#faf9f6",
          enable_publishing: false,
          allow_symbol_change: true,
          hide_top_toolbar: false,
          hide_legend: false,
          save_image: false,
          container_id: idRef.current,
        });
        setStatus("embedded");
      } catch (err) {
        console.warn("TradingView widget failed", err);
        setStatus("blocked");
        onUnavailableRef.current?.("error");
      }
    });
    return () => {
      cancelled = true;
      try {
        widgetRef.current?.remove?.();
      } catch {
        // ignore
      }
      widgetRef.current = null;
    };
  }, [ticker, exchange]);

  return (
    <div
      style={{
        border: "1px solid var(--line)",
        background: "var(--surface)",
        padding: 12,
        minWidth: 0,
        maxWidth: "100%",
        boxSizing: "border-box",
      }}
      data-tradingview-status={status}
    >
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 8,
        }}
      >
        <div>
          <div className="eyebrow-muted">TradingView (context only)</div>
          <h3 style={{ margin: "4px 0 0", fontSize: 16, letterSpacing: "-.01em" }}>
            Live chart for {ticker}
          </h3>
        </div>
        <span
          style={{
            fontSize: 11,
            fontFamily: "Geist Mono, monospace",
            color: status === "blocked" ? "var(--down)" : "var(--muted)",
          }}
        >
          {status === "loading" ? "Loading chart…" : status === "embedded" ? "External chart" : "External chart unavailable"}
        </span>
      </header>
      {(status === "blocked" || status === "unsupported") && (
        <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>
          The external chart could not be loaded. Use the snapshot chart above for the recorded observation.
        </p>
      )}
      <div
        ref={containerRef}
        data-tradingview-ticker={ticker}
        className="tradingview-frame"
        hidden={status === "blocked" || status === "unsupported"}
      />
    </div>
  );
}
