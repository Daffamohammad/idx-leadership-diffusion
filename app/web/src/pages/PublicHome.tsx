import { Link } from "react-router"
import { useEffect, useRef, useState } from "react"
import ThemeToggle from "../components/ThemeToggle"
import { BrandLockup } from "../components/BrandMark"
import SiteFooter from "../components/SiteFooter"
import { groupHref, useResearch } from "../data/research"
import { publicErrorText } from "../data/publicCopy"
import { formatDateLabel, formatPercent } from "../data/format"

// ── Dia text reveal ──────────────────────────────────────────────────────────
// Gradient band sweeps left-to-right; text settles from muted → brand sweep → final color.
// Inspired by magicui dia-text-reveal, implemented without Framer Motion.

function DiaTextReveal({
  text,
  delay = 0,
  endColor = "var(--ink)",
  style,
}: {
  text: string
  delay?: number
  endColor?: string
  style?: React.CSSProperties
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const [active, setActive] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let pending: number | undefined
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          pending = window.setTimeout(() => setActive(true), delay)
          observer.disconnect()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => {
      if (pending !== undefined) window.clearTimeout(pending)
      observer.disconnect()
    }
  }, [delay])

  const gradient = [
    "#a8afb2 0%",
    "#a8afb2 22%",
    "#f26a3d 40%",
    "#d97956 48%",
    "#438b82 56%",
    `${endColor} 66%`,
    `${endColor} 100%`,
  ].join(", ")

  return (
    <span
      ref={ref}
      style={{
        color: "transparent",
        background: `linear-gradient(90deg, ${gradient})`,
        backgroundSize: "300% 100%",
        backgroundPosition: active ? undefined : "0% center",
        WebkitBackgroundClip: "text",
        backgroundClip: "text" as React.CSSProperties["backgroundClip"],
        animation: active ? "dia-sweep 1.1s cubic-bezier(0.77, 0, 0.175, 1) infinite" : "none",
        display: "inline",
        ...style,
      }}
    >
      {text}
    </span>
  )
}

// ── Shimmer CTA button ───────────────────────────────────────────────────────
// Conic gradient orbits the button perimeter + magnetic pull + inset highlight.
// Inspired by magicui shimmer-button, adapted without Framer Motion / Tailwind.

function ShimmerCTAButton({
  to,
  children,
}: {
  to: string
  children: React.ReactNode
}) {
  const ref = useRef<HTMLAnchorElement>(null)

  const onMouseMove = (e: React.MouseEvent) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const x = (e.clientX - rect.left - rect.width / 2) * 0.28
    const y = (e.clientY - rect.top - rect.height / 2) * 0.28
    ref.current.style.transform = `translate(${x}px, ${y}px)`
    ref.current.style.transition = "transform 0.1s ease"
  }

  const onMouseLeave = () => {
    if (!ref.current) return
    ref.current.style.transform = ""
    ref.current.style.transition = "transform 0.65s cubic-bezier(0.23, 1, 0.32, 1)"
  }

  return (
    <Link
      ref={ref}
      to={to}
      className="shimmer-cta"
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      style={{ textDecoration: "none" }}
    >
      <div className="shimmer-cta-border" />
      <span className="shimmer-cta-body">{children}</span>
    </Link>
  )
}

// ── Interactive hover CTA ────────────────────────────────────────────────────
// A dark dot expands to fill the button; text slides out and reveal slides in.
// Inspired by magicui interactive-hover-button.

function InteractiveHoverCTA({
  to,
  label,
}: {
  to: string
  label: string
}) {
  return (
    <Link to={to} className="ihover-cta">
      <span className="ihover-dot" />
      <span className="ihover-label">{label}</span>
      <span className="ihover-reveal">{label} →</span>
    </Link>
  )
}

// ── Word-by-word reveal ──────────────────────────────────────────────────────

function RevealText({
  text,
  delay = 0,
  className,
  style,
}: {
  text: string
  delay?: number
  className?: string
  style?: React.CSSProperties
}) {
  const words = text.split(" ")
  return (
    <span className={className} style={style}>
      {words.map((word, i) => (
        <span
          key={i}
          style={{ display: "inline-block", overflow: "hidden", verticalAlign: "bottom" }}
        >
          <span className="word-reveal" style={{ animationDelay: `${delay + i * 72}ms` }}>
            {word}
          </span>
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </span>
  )
}

// ── Dashboard preview ──────────────────────────────────────────────────────
// Live preview of the main Dashboard: the 60D rotation map beside the top
// 20D rankings. Reads the verified Sectors core through the shared research
// hook so the figures always match the Dashboard readings.

const PREVIEW_W = 360
const PREVIEW_H = 230
const PREVIEW_PAD = 30

function DashboardPreview() {
  const { groups, reading, date, cadence, horizon, loading, error, native } = useResearch("sectors")
  const asOf = native?.as_of ?? date

  if (loading) {
    return (
      <section className="dash-card reveal" aria-label="Dashboard preview">
        <div className="eyebrow-muted">Dashboard preview</div>
        <p style={{ color: "var(--muted)", margin: "10px 0 0" }}>Loading the Dashboard preview…</p>
      </section>
    )
  }

  if (error || !native || groups.length === 0) {
    return (
      <section className="dash-card reveal" aria-label="Dashboard preview">
        <div className="eyebrow-muted">Dashboard preview</div>
        <p style={{ color: "var(--muted)", margin: "10px 0 0" }}>
          {error ? `The Dashboard preview could not be loaded. ${publicErrorText(error)}` : "The Dashboard preview is unavailable."}
        </p>
        <div style={{ marginTop: 14 }}>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      </section>
    )
  }

  const ranked = [...groups].sort(
    (a, b) => (reading(b)?.excess_return_20d ?? -Infinity) - (reading(a)?.excess_return_20d ?? -Infinity),
  )
  const leader = ranked[0]
  const plotted = groups.flatMap((group) => {
    const point = reading(group)
    const x = point?.map_x_60d
    const y = point?.relative_momentum
    if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) return []
    return [{ group, x, y, confirmed: (point?.map_contributors ?? 0) >= 5 }]
  })

  const span = (values: number[]) => {
    const lo = Math.min(...values)
    const hi = Math.max(...values)
    const pad = Math.max((hi - lo) * 0.2, 1)
    return [Math.min(lo - pad, 0), Math.max(hi + pad, 0)] as const
  }
  const [x0, x1] = plotted.length > 0 ? span(plotted.map((p) => p.x)) : [-1, 1] as const
  const [y0, y1] = plotted.length > 0 ? span(plotted.map((p) => p.y)) : [-1, 1] as const
  const px = (v: number) => PREVIEW_PAD + ((v - x0) / (x1 - x0)) * (PREVIEW_W - PREVIEW_PAD * 2)
  const py = (v: number) => PREVIEW_PAD + ((y1 - v) / (y1 - y0)) * (PREVIEW_H - PREVIEW_PAD * 2)
  const top = ranked.slice(0, 3)
  const topAbs = Math.max(...top.map((g) => Math.abs(reading(g)?.excess_return_20d ?? 0)), 1e-9)

  return (
    <section className="dash-card reveal" aria-label="Dashboard preview">
      <div className="eyebrow-muted">Dashboard preview · Data through {formatDateLabel(asOf)}</div>
      {plotted.length > 0 ? (
        <svg
          viewBox={`0 0 ${PREVIEW_W} ${PREVIEW_H}`}
          width="100%"
          role="img"
          aria-label="Preview of the 60D rotation map"
          style={{ display: "block", marginTop: 8 }}
        >
          <line x1={px(0)} x2={px(0)} y1={PREVIEW_PAD - 8} y2={PREVIEW_H - PREVIEW_PAD + 8} stroke="var(--line)" />
          <line x1={PREVIEW_PAD - 8} x2={PREVIEW_W - PREVIEW_PAD + 8} y1={py(0)} y2={py(0)} stroke="var(--line)" />
          {plotted.map((p) => {
            const isLeader = leader != null && p.group.id === leader.id
            return (
              <g key={p.group.id}>
                <circle
                  cx={px(p.x)}
                  cy={py(p.y)}
                  r={isLeader ? 7 : 5}
                  fill={p.confirmed ? "var(--accent-ink)" : "none"}
                  stroke="var(--accent-ink)"
                  strokeWidth={p.confirmed ? 0 : 1.5}
                  opacity={p.confirmed ? 0.9 : 0.8}
                />
                {isLeader && (
                  <text
                    x={Math.min(px(p.x) + 10, PREVIEW_W - 4 - Math.max(18, p.group.name.length * 5.6))}
                    y={py(p.y) + 4}
                    fontSize="10"
                    fill="var(--ink)"
                  >
                    {p.group.name}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      ) : (
        <p style={{ color: "var(--muted)", margin: "10px 0 0" }}>No map points for this date.</p>
      )}
      <div style={{ marginTop: 4, fontFamily: "Geist Mono, monospace", fontSize: 9, color: "var(--muted)" }}>
        60D excess vs IHSG → · Hollow marks have fewer than five contributors
      </div>
      <ul style={{ margin: "12px 0 0", padding: 0, listStyle: "none", display: "grid", gap: 8 }}>
        {top.map((group) => {
          const value = reading(group)?.excess_return_20d ?? 0
          return (
            <li key={group.id} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 4, alignItems: "baseline" }}>
              <Link
                to={groupHref(group, date, cadence, horizon)}
                style={{ color: "var(--ink)", fontSize: 13, textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                {group.name}
              </Link>
              <span style={{ fontFamily: "Geist Mono, monospace", fontSize: 12, color: value >= 0 ? "var(--up)" : "var(--down)" }}>
                {formatPercent(value)}
              </span>
              <span
                aria-hidden="true"
                style={{
                  gridColumn: "1 / -1",
                  height: 4,
                  background: "var(--line)",
                  position: "relative",
                }}
              >
                <span
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: `${(Math.abs(value) / topAbs) * 100}%`,
                    background: value >= 0 ? "var(--up)" : "var(--down)",
                  }}
                />
              </span>
            </li>
          )
        })}
      </ul>
      <div style={{ marginTop: 14 }}>
        <Link to="/sectors" style={{ color: "var(--ink)", fontSize: 13, textDecoration: "none", borderBottom: "1px solid var(--line)" }}>
          Open the Dashboard →
        </Link>
      </div>
    </section>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

const lenses: Array<[string, string, string, string, string]> = [
  ["01", "Leadership", "Which groups outperform IHSG, and whether momentum is improving.", "Open the Dashboard", "/sectors"],
  ["02", "Diffusion", "How many constituents outperform, and whether participation is broadening or narrowing.", "Open the leadership map", "/map"],
  ["03", "Confirmation", "Concentration, persistence, and foreign flow — measured separately, so they can disagree.", "How to read the research", "/methodology"],
]

const workflows: Array<[string, string, string]> = [
  ["Dashboard", "Eleven 20D sector rankings, the 60D excess-return map, replay, curves, and all 66 constituent charts.", "/sectors"],
  ["Leadership map", "60D excess vs IHSG with rotation phases, trails, and per-horizon cohorts.", "/map"],
  ["Weekly changes", "What changed between comparable weeks, with breadth and diffusion counts.", "/what-changed"],
  ["Ownership", "Issuer, investor, group, and comparison views with dated holder evidence.", "/ownership"],
  ["Coverage & sources", "The 66-stock coverage choice, observation dates, market flow, and methods.", "/sources"],
  ["How to read the research", "Rotation versus leadership, horizons, eligibility, and relationship boundaries.", "/methodology"],
]

export default function PublicHome() {
  const [methodHovered, setMethodHovered] = useState(false)

  // Scroll reveal for non-animated sections
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("revealed")
            observer.unobserve(e.target)
          }
        })
      },
      { threshold: 0.1 },
    )
    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  return (
    <div style={{ background: "var(--surface)", minHeight: "100%" }}>
      {/* ── Header ── */}
      <header
        className="public-header"
        style={{
          maxWidth: 1440,
          margin: "auto",
          padding: "16px 40px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid var(--line)",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <Link to="/" style={{ textDecoration: "none" }} aria-label="The Diffusion home">
          <BrandLockup />
        </Link>
        <nav
          aria-label="Landing page sections"
          style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}
        >
          <Link to="/sectors" style={{ color: "var(--ink)", fontSize: 12, textDecoration: "none" }}>
            Dashboard
          </Link>
          <Link to="/map" style={{ color: "var(--muted)", fontSize: 12, textDecoration: "none" }}>
            Leadership map
          </Link>
          <Link to="/sources" style={{ color: "var(--muted)", fontSize: 12, textDecoration: "none" }}>
            Coverage &amp; sources
          </Link>
          <ThemeToggle />
        </nav>
      </header>

      <main className="public-main" style={{ maxWidth: 1440, margin: "auto", padding: "0 40px" }}>
        {/* ── Hero ── */}
        <section
          className="public-grid public-hero"
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.05fr) minmax(0, .95fr)",
            gap: 50,
            padding: "90px 0 70px",
            alignItems: "start",
            minWidth: 0,
            maxWidth: "100%",
          }}
        >
          <div style={{ minWidth: 0, maxWidth: "100%", overflowWrap: "anywhere" }}>
            <div className="eyebrow-muted reveal" style={{ marginBottom: 24 }}>
              The Diffusion · Indonesian equity market intelligence
            </div>

            {/* Dia-text-reveal headline */}
            <h1
              style={{
                fontSize: "clamp(42px,5vw,72px)",
                letterSpacing: "-.065em",
                lineHeight: 0.96,
                fontWeight: 500,
                margin: "0 0 26px",
              }}
            >
              <DiaTextReveal
                text="See where leadership is moving."
                delay={200}
                endColor="var(--ink)"
              />
              <br />
              <DiaTextReveal
                text="See whether the market agrees."
                delay={950}
                endColor="var(--muted)"
              />
            </h1>

            <p
              className="reveal"
              style={{ color: "var(--muted)", lineHeight: 1.65, maxWidth: 480, marginBottom: 28 }}
            >
              The Diffusion tracks 66 Indonesian stocks across 11 IDX sectors to show which
              groups lead IHSG, whether participation is broadening, and which constituents
              drive the move. Every reading links to its contributors and observation dates.
            </p>

            <div className="reveal public-cta-row" style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap", minWidth: 0, maxWidth: "100%" }}>
              <ShimmerCTAButton to="/sectors">Open the Dashboard →</ShimmerCTAButton>
              <Link
                to="/methodology"
                onMouseEnter={() => setMethodHovered(true)}
                onMouseLeave={() => setMethodHovered(false)}
                style={{
                  color: "var(--ink)",
                  fontSize: 13,
                  textDecoration: "none",
                  borderBottom: methodHovered ? "1px solid #16191c" : "1px solid transparent",
                  transition: "border-color 0.25s ease",
                }}
              >
                How to read the research
              </Link>
            </div>

            <div className="eyebrow-muted reveal" style={{ marginTop: 26 }}>
              End-of-day observations · Source: Sectors API
            </div>
          </div>

          <DashboardPreview />
        </section>

        {/* ── Three lenses ── */}
        <section style={{ borderTop: "1px solid var(--line)", padding: "72px 0" }}>
          <div className="eyebrow-muted reveal">Three intelligence lenses</div>
          {lenses.map(([n, t, d, cta, to], idx) => (
            <div
              key={n}
              className="reveal lenses-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "80px minmax(0, 1fr) minmax(0, 1fr)",
                gap: 24,
                padding: "24px 0",
                borderBottom: "1px solid var(--line)",
                transitionDelay: `${idx * 80}ms`,
                minWidth: 0,
                maxWidth: "100%",
              }}
            >
              <span className="eyebrow-muted">{n}</span>
              <div style={{ minWidth: 0, maxWidth: "100%", overflowWrap: "anywhere" }}>
                <h3 style={{ fontSize: 22, margin: 0 }}>{t}</h3>
                <p style={{ color: "var(--muted)", margin: "6px 0" }}>{d}</p>
              </div>
              <div style={{ alignSelf: "center", minWidth: 0 }}>
                <Link to={to} style={{ color: "var(--ink)", fontSize: 13, textDecoration: "none", borderBottom: "1px solid var(--line)" }}>
                  {cta} →
                </Link>
              </div>
            </div>
          ))}
          <p className="reveal" style={{ color: "var(--muted)", marginTop: 22, maxWidth: 640, lineHeight: 1.65 }}>
            The map&apos;s coordinates set rotation phase; leadership is classified separately from
            20D excess and 5D-minus-60D acceleration. Empty quadrants are a valid result.
          </p>
        </section>

        {/* ── Dark CTA band with grain ── */}
        <section
          className="grain-bg dark-cta-band"
          style={{
            background: "#121619",
            color: "white",
            margin: "0 -40px",
            padding: "82px 40px",
            minWidth: 0,
            maxWidth: "none",
            boxSizing: "border-box",
          }}
        >
          <div className="reveal" style={{ maxWidth: 1360, margin: "auto" }}>
            <div className="eyebrow-muted" style={{ color: "#9aa4ac" }}>
              Coverage · The Diffusion chooses this coverage
            </div>
            <h2
              style={{ fontSize: 44, maxWidth: 680, letterSpacing: "-.05em", lineHeight: 1.05, fontStyle: "italic" }}
            >
              <RevealText text="Every contributor visible." delay={60} />
            </h2>
            <p style={{ color: "#cbd0d1", maxWidth: 640, lineHeight: 1.65, marginTop: 18 }}>
              An index move can hide sharp differences between sectors. The Diffusion follows
              66 Indonesian stocks — six per IDX sector, chosen by market-cap ranking on
              2 October 2026 — and measures each group against IHSG over 5, 20, and 60
              trading days. Prices are raw Sectors closes; windows touched by splits,
              rights issues, dividends, or other listed mechanical events are left out
              rather than adjusted. Each horizon keeps its own eligible contributors,
              confirmed signals need five of them, and the 23 supported stock YTD readings
              hold their 2 October 2026 end date while earlier dates replay.
            </p>
            <div style={{ marginTop: 24 }}>
              <InteractiveHoverCTA to="/sources" label="Coverage & sources" />
            </div>
          </div>
        </section>

        {/* ── Workflows ── */}
        <section style={{ padding: "80px 0 40px" }}>
          <div className="reveal">
            <div className="eyebrow-muted">Research workflows</div>
            <h2
              style={{ fontSize: 42, letterSpacing: "-.05em", marginBottom: 18, fontWeight: 500, fontStyle: "italic" }}
            >
              <RevealText text="Start from the question." delay={60} />
            </h2>
          </div>
          <div
            className="public-grid reveal"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 1,
              background: "var(--line)",
              border: "1px solid var(--line)",
              marginTop: 32,
              minWidth: 0,
              maxWidth: "100%",
            }}
          >
            {workflows.map(([title, desc, to]) => (
              <Link
                key={to + title}
                to={to}
                style={{ background: "var(--surface-subtle)", padding: 24, textDecoration: "none" }}
              >
                <h3 style={{ fontSize: 17, margin: "0 0 8px", color: "var(--ink)" }}>{title} →</h3>
                <p style={{ color: "var(--muted)", margin: 0, fontSize: 13, lineHeight: 1.6 }}>{desc}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* ── Methodology callout ── */}
        <section style={{ padding: "60px 0 100px" }}>
          <div className="reveal">
            <div className="eyebrow-muted">Methodology / Transparent by design</div>
            <h2
              style={{ fontSize: 42, letterSpacing: "-.05em", marginBottom: 18, fontWeight: 500, fontStyle: "italic" }}
            >
              <RevealText text="No black-box conviction score." delay={60} />
            </h2>
            <p style={{ color: "var(--muted)", maxWidth: 580 }}>
              Leadership, diffusion, concentration, persistence, and confirmation are measured
              independently — and can contradict one another.
            </p>
            <div style={{ marginTop: 24 }}>
              <InteractiveHoverCTA to="/sectors" label="Open The Diffusion" />
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <SiteFooter />
      </main>
    </div>
  )
}
