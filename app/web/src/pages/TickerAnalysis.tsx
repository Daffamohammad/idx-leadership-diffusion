// TickerAnalysis — per-ticker route that surfaces the methodology chart,
// foreign-flow context (when the ticker is in the sample), and the
// TradingView widget as a contextual overlay.
//
// The snapshot-backed yfinance chart (PriceChart) remains the source of
// truth for the persisted price series. TradingView is contextual.

import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { useSnapshot } from "../data/SnapshotProvider";
import PriceChart from "../components/PriceChart";
import TradingViewWidget from "../components/TradingViewWidget";
import { formatDateLabel, formatEnumLabel, formatIdrCompact } from "../data/format";

export default function TickerAnalysis() {
  const { ticker: rawTicker } = useParams<{ ticker: string }>();
  const ticker = (rawTicker ?? "").toUpperCase();
  const snap = useSnapshot();
  const adapted = snap.data;
  const [tradingViewBlocked, setTradingViewBlocked] = useState(false);
  const [tradingViewUnavailable, setTradingViewUnavailable] = useState(false);

  useEffect(() => {
    setTradingViewBlocked(false);
    setTradingViewUnavailable(false);
  }, [ticker]);

  const feature = useMemo(() => {
    if (!adapted || !ticker) return null;
    return adapted.featureLookup[ticker] ?? null;
  }, [adapted, ticker]);

  const security = useMemo(() => {
    if (!adapted || !ticker) return null;
    return adapted.securityLookup[ticker] ?? null;
  }, [adapted, ticker]);

  const priceHistory = useMemo(() => {
    if (!adapted || !ticker) return [];
    return adapted.tickerPriceHistory[ticker] ?? [];
  }, [adapted, ticker]);

  const events = useMemo(() => {
    if (!adapted || !ticker) return [];
    return adapted.researchEvents.filter((event) => event.ticker === ticker);
  }, [adapted, ticker]);

  const foreignContext = useMemo(() => {
    if (!adapted || !adapted.foreignFlow) return null;
    const rows = [
      ...adapted.foreignFlow.topBuys,
      ...adapted.foreignFlow.topSells,
    ];
    return rows.find((row) => row.ticker === ticker) ?? null;
  }, [adapted, ticker]);

  if (!ticker) {
    return (
      <main style={{ padding: 32 }}>
        <h1>Invalid ticker</h1>
        <p>The URL must include an IDX-formatted ticker.</p>
        <Link to="/overview">Return to overview</Link>
      </main>
    );
  }

  if (snap.loading) {
    return (
      <main style={{ padding: 32, color: "#686e73" }}>
        Loading snapshot for ticker analysis…
      </main>
    );
  }

  if (snap.error || !adapted) {
    return (
      <main style={{ padding: 32 }}>
        <h1>Snapshot unavailable</h1>
        <p style={{ color: "#8f2424" }}>{snap.error ?? "No snapshot loaded."}</p>
        <Link to="/overview">Return to overview</Link>
      </main>
    );
  }

  const asOf = adapted.payload.as_of;
  const manifestEntry = adapted.payload.manifest?.entries?.[0];
  const providerMode = manifestEntry?.provider_mode ?? "PUBLIC_PROTOTYPE";
  const priceBasis = manifestEntry?.price_basis ?? "close";

  return (
    <main
      style={{
        padding: "32px 36px 56px",
        display: "grid",
        gap: 24,
        maxWidth: 1180,
        margin: "0 auto",
      }}
    >
      <header
        style={{
          borderBottom: "1px solid #dfe2e1",
          paddingBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <div className="eyebrow-muted">Ticker analysis</div>
          <h1 style={{ margin: "6px 0 4px", fontSize: 32, letterSpacing: "-.02em" }}>
            {security?.name ?? ticker}
          </h1>
          <div
            style={{
              display: "flex",
              gap: 12,
              fontSize: 12,
              fontFamily: "Geist Mono, monospace",
              color: "#686e73",
            }}
          >
            <span>{ticker}</span>
            {security?.sector && (
              <>
                <span>·</span>
                <span>{security.sector}</span>
              </>
            )}
            <span>·</span>
            <span>As of {formatDateLabel(asOf)}</span>
            <span>·</span>
            <span>Provider mode: {formatEnumLabel(providerMode)}</span>
          </div>
        </div>
        <Link
          to="/explorer"
          style={{
            alignSelf: "flex-end",
            padding: "8px 14px",
            border: "1px solid #202325",
            color: "#202325",
            textDecoration: "none",
            fontSize: 12,
          }}
        >
          ← Group explorer
        </Link>
      </header>

      <section
        aria-label="Methodology price chart"
        style={{ display: "grid", gap: 12 }}
      >
        <div className="eyebrow-muted">Methodology chart (snapshot-backed)</div>
        <PriceChart
          ticker={ticker}
          points={priceHistory.map((row) => ({ date: row.date, value: row.value }))}
          benchmarkPoints={priceHistory.map((row) => ({
            date: row.date,
            value: row.benchmark,
          }))}
          asOf={asOf}
          source={`Persisted snapshot · ${formatEnumLabel(providerMode)} · ${formatEnumLabel(priceBasis)}`}
          metricLabel="Rebased index (start = 100)"
          referenceValue={100}
        />
      </section>
      <section
        aria-label="TradingView context chart"
        style={{ display: "grid", gap: 12 }}
      >
        {!tradingViewBlocked && !tradingViewUnavailable && (
          <TradingViewWidget
            ticker={ticker}
            onUnavailable={() => {
              if (navigator.onLine === false) setTradingViewBlocked(true);
              else setTradingViewUnavailable(true);
            }}
          />
        )}
        {(tradingViewBlocked || tradingViewUnavailable) && (
          <div
            style={{
              border: "1px solid #dfe2e1",
              background: "#fff",
              padding: 16,
            }}
          >
            <div className="eyebrow-muted">TradingView (context only)</div>
            <h3 style={{ margin: "6px 0 8px", fontSize: 16 }}>
              Live widget unavailable
            </h3>
            <p style={{ margin: 0, color: "#686e73", fontSize: 13 }}>
              {tradingViewBlocked
                ? "The TradingView CDN is not reachable from this browser; the methodology chart remains the source of truth."
                : "The widget failed to initialise. The snapshot-backed chart above is the methodology series."}
            </p>
          </div>
        )}
      </section>

      <section
        aria-label="Foreign flow sample context"
        style={{
          border: "1px solid #dfe2e1",
          padding: 20,
          background: "#faf9f6",
        }}
      >
        <div className="eyebrow-muted">Foreign-flow sample context</div>
        <h2 style={{ margin: "6px 0 8px", fontSize: 18 }}>
          {foreignContext ? "Sample observation available" : "No sample observation"}
        </h2>
        {foreignContext ? (
          <div style={{ display: "grid", gap: 6, fontSize: 13 }}>
            <div>
              <strong>{foreignContext.direction}</strong> on {foreignContext.asOf}
            </div>
            <div>
              Net: {formatIdrCompact(foreignContext.netValueIdr)}
            </div>
            <div style={{ fontSize: 11, color: "#686e73" }}>
              <a href={foreignContext.sourceUrl} target="_blank" rel="noreferrer">
                Source: {foreignContext.sourceName}
              </a>
            </div>
          </div>
        ) : (
          <p style={{ margin: 0, fontSize: 13, color: "#686e73" }}>
            This ticker does not appear in the latest published top-buy or
            top-sell foreign-flow sample. The sample is bounded to the
            published source articles and is not a full universe observation.
          </p>
        )}
      </section>

      <section
        aria-label="Research events"
        style={{
          border: "1px solid #dfe2e1",
          padding: 20,
          background: "#faf9f6",
        }}
      >
        <div className="eyebrow-muted">Research events</div>
        <h2 style={{ margin: "6px 0 8px", fontSize: 18 }}>
          {events.length === 0 ? "No dated events" : `${events.length} dated event(s)`}
        </h2>
        {events.length === 0 ? (
          <p style={{ margin: 0, fontSize: 13, color: "#686e73" }}>
            No research event for this ticker in the current bundle. Events
            are explicitly context-only — they never become signals.
          </p>
        ) : (
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              display: "grid",
              gap: 8,
              fontSize: 13,
            }}
          >
            {events.map((event) => (
              <li
                key={event.eventId}
                style={{
                  borderLeft: "3px solid #c69f4a",
                  paddingLeft: 12,
                }}
              >
                <div style={{ fontFamily: "Geist Mono, monospace", fontSize: 11, color: "#686e73" }}>
                  {event.eventDate} · {event.category}
                </div>
                <div style={{ fontWeight: 600 }}>{event.title}</div>
                <div style={{ color: "#202325", marginTop: 2 }}>{event.summary}</div>
                <div style={{ fontSize: 11, color: "#686e73", marginTop: 2 }}>
                  <a href={event.sourceUrl} target="_blank" rel="noreferrer">
                    Source: {event.sourceName}
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section
        aria-label="Methodology feature snapshot"
        style={{
          border: "1px solid #dfe2e1",
          padding: 20,
          background: "#fff",
        }}
      >
        <div className="eyebrow-muted">Methodology snapshot</div>
        <h2 style={{ margin: "6px 0 8px", fontSize: 18 }}>Feature row</h2>
        {feature ? (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontFamily: "Geist Mono, monospace",
              fontSize: 12,
            }}
          >
            <thead>
              <tr>
                <th align="left" style={{ borderBottom: "1px solid #dfe2e1" }}>Field</th>
                <th align="left" style={{ borderBottom: "1px solid #dfe2e1" }}>Value</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>{formatEnumLabel("as_of")}</td><td>{formatDateLabel(feature.as_of)}</td></tr>
              <tr><td>{formatEnumLabel("latest_close")}</td><td>{feature.latest_close ?? "—"}</td></tr>
              <tr><td>{formatEnumLabel("return_20d")}</td><td>{feature.return_20d ?? "—"}</td></tr>
              <tr><td>{formatEnumLabel("excess_return_20d")}</td><td>{feature.excess_return_20d ?? "—"}</td></tr>
              <tr><td>{formatEnumLabel("excess_return_60d")}</td><td>{feature.excess_return_60d ?? "—"}</td></tr>
              <tr><td>{formatEnumLabel("relative_strength_level")}</td><td>{feature.relative_strength_level ?? "—"}</td></tr>
            </tbody>
          </table>
        ) : (
          <p style={{ margin: 0, color: "#686e73" }}>
            This ticker does not appear in the snapshot's feature table.
          </p>
        )}
      </section>
    </main>
  );
}
