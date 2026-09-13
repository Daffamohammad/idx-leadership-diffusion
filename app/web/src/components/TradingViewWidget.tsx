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

import { useEffect, useRef, useState, useCallback } from "react";

interface TradingViewWidgetProps {
  ticker: string;
  exchange?: string;
  containerId?: string;
  onUnavailable?: (reason: TradingViewUnavailableReason) => void;
}

export type TradingViewUnavailableReason = "network" | "unsupported" | "error" | "timeout";

const SCRIPT_ID = "tradingview-advanced-chart-script";
const SCRIPT_SRC = "https://s3.tradingview.com/tv.js";
const WIDGET_RENDER_TIMEOUT_MS = 8000;

function sanitizeTicker(ticker: string, exchange: string): string | null {
  const cleaned = ticker.toUpperCase().trim();
  if (!cleaned.endsWith(".JK")) return null;
  return `${exchange}:${cleaned.replace(".JK", "")}`;
}

function loadScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof document === "undefined") return resolve(false);
    const tvAvailable = (): boolean =>
      typeof (window as { TradingView?: unknown }).TradingView !== "undefined";
    if (tvAvailable()) return resolve(true);
    if (document.getElementById(SCRIPT_ID)) {
      const handle = window.setInterval(() => {
        if (tvAvailable()) {
          window.clearInterval(handle);
          resolve(true);
        }
      }, 50);
      window.setTimeout(() => {
        window.clearInterval(handle);
        resolve(tvAvailable());
      }, 4000);
      return;
    }
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.head.appendChild(script);
  });
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
  const [status, setStatus] = useState<"loading" | "ready" | "blocked" | "unsupported">(
    "loading",
  );
  const [healthCheckFailed, setHealthCheckFailed] = useState(false);
  const widgetRef = useRef<EmbeddedWidget | null>(null);
  const renderTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const widgetReadyRef = useRef(false);
  const onUnavailableRef = useRef(onUnavailable);

  useEffect(() => {
    onUnavailableRef.current = onUnavailable;
  }, [onUnavailable]);

  const clearRenderTimeout = useCallback(() => {
    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
      renderTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setHealthCheckFailed(false);
    widgetReadyRef.current = false;
    clearRenderTimeout();
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
      inner.style.height = "420px";
      inner.style.width = "100%";
      containerRef.current.appendChild(inner);
      try {
        const markReady = () => {
          if (cancelled) return;
          widgetReadyRef.current = true;
          clearRenderTimeout();
          setStatus("ready");
        };
        widgetRef.current = new window.TradingView.widget({
          symbol,
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
          onChartReady: markReady,
        });
        if (widgetReadyRef.current) {
          clearRenderTimeout();
        } else {
          renderTimeoutRef.current = setTimeout(() => {
            if (!cancelled && widgetRef.current && !widgetReadyRef.current) {
              setHealthCheckFailed(true);
              setStatus("blocked");
              onUnavailableRef.current?.("timeout");
            }
          }, WIDGET_RENDER_TIMEOUT_MS);
        }
      } catch (err) {
        console.warn("TradingView widget failed", err);
        setStatus("blocked");
        onUnavailableRef.current?.("error");
      }
    });
    return () => {
      cancelled = true;
      clearRenderTimeout();
      try {
        widgetRef.current?.remove?.();
      } catch {
        // ignore
      }
      widgetRef.current = null;
    };
  }, [ticker, exchange, clearRenderTimeout]);

  return (
    <div
      style={{
        border: "1px solid #dfe2e1",
        background: "#fff",
        padding: 12,
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
            color:
              status === "ready"
                ? "#178477"
                : status === "blocked"
                  ? "#8f2424"
                  : status === "unsupported"
                    ? "#7c858c"
                    : "#7a5010",
          }}
        >
          {status === "ready"
            ? "Live widget loaded"
            : status === "blocked"
              ? healthCheckFailed
                ? "Widget render timed out"
                : "Network blocked / offline"
              : status === "unsupported"
                ? "Ticker not IDX-formatted"
                : "Loading widget…"}
        </span>
      </header>
      {status === "blocked" && (
        <p style={{ margin: "0 0 12px", fontSize: 12, color: "#686e73" }}>
          {healthCheckFailed
            ? "The widget did not become ready within 8 seconds. The methodology chart (PriceChart) remains the source of truth; this widget is contextual only."
            : "TradingView's CDN is not reachable from this browser. The methodology chart (PriceChart) remains the source of truth; this widget is contextual only."}
        </p>
      )}
      <div
        ref={containerRef}
        data-tradingview-ticker={ticker}
        style={{ minHeight: 420, background: "#faf9f6" }}
      />
    </div>
  );
}
