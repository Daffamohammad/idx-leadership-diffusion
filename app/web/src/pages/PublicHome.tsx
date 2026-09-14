import { Link } from "react-router"
import { useEffect, useMemo, useRef, useState } from "react"
import ThemeToggle from "../components/ThemeToggle"
import ImageWithFallback from "../components/ImageWithFallback"
import leadershipMap from "../imports/image.png"
import { useSnapshot } from "../data/SnapshotProvider"
import {
  mapX,
  mapY,
  mapViewDomain,
  mapViewLabels,
  mapYBaseline,
  mapYValue,
  type MapViewMode,
  type MapPlotBounds,
} from "../data/mapGeometry"
import { BrandLockup } from "../components/BrandMark"
import { placeMapLabels } from "../data/mapLabels"
import { EvidenceBadge } from "../components/EvidenceModel"

// ── Dia text reveal ──────────────────────────────────────────────────────────
// Gradient band sweeps left-to-right; text settles from muted → brand sweep → final color.
// Inspired by magicui dia-text-reveal, implemented without Framer Motion.

function DiaTextReveal({
  text,
  delay = 0,
  endColor = "#16191c",
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
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          const t = setTimeout(() => setActive(true), delay)
          observer.disconnect()
          return () => clearTimeout(t)
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
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
        animation: active ? "dia-sweep 1.5s cubic-bezier(0.77, 0, 0.175, 1) forwards" : "none",
        display: "inline",
        ...style,
      }}
    >
      {text}
    </span>
  )
}

// ── Text scramble ────────────────────────────────────────────────────────────
// RAF loop resolves random glyphs left-to-right into the real text.
// Inspired by beui.dev TextScramble — respects the same timing formula.

const GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#%&@$?/"

function TextScrambleLine({
  text,
  sectionRef,
  delay = 0,
  style,
}: {
  text: string
  sectionRef: { current: HTMLElement | null }
  delay?: number
  style?: React.CSSProperties
}) {
  const [phase, setPhase] = useState<"idle" | "scrambling" | "done">("idle")
  const [display, setDisplay] = useState(text)

  useEffect(() => {
    const el = sectionRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          const t = setTimeout(() => setPhase("scrambling"), delay)
          observer.disconnect()
          return () => clearTimeout(t)
        }
      },
      { threshold: 0.2 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [delay, sectionRef])

  useEffect(() => {
    if (phase !== "scrambling") return
    const duration = Math.min(760, Math.max(420, text.replace(/\s/g, "").length * 32))
    const start = performance.now()
    let lastUpdate = 0
    let raf: number

    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const resolvedCount = Math.floor(progress * text.length)

      if (now - lastUpdate >= 40) {
        const chars = text.split("").map((ch, i) => {
          if (ch === " " || i < resolvedCount) return ch
          return GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
        })
        setDisplay(chars.join(""))
        lastUpdate = now
      }

      if (progress < 1) {
        raf = requestAnimationFrame(tick)
      } else {
        setDisplay(text)
        setPhase("done")
      }
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [phase, text])

  return (
    <span
      aria-label={text}
      style={{
        display: "inline",
        opacity: phase === "idle" ? 0.18 : 1,
        transition: "opacity 0.15s ease",
        fontFamily: phase === "scrambling" ? "'Geist Mono', monospace" : "inherit",
        ...style,
      }}
    >
      <span aria-hidden>{display}</span>
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

// ── Word-by-word reveal (kept for other h2s) ─────────────────────────────────

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
            {i < words.length - 1 ? " " : ""}
          </span>
        </span>
      ))}
    </span>
  )
}

// ── Staggered dot field ──────────────────────────────────────────────────────

const DotField = ({ narrow = false }: { narrow?: boolean }) => (
  <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 5, marginTop: 18 }}>
    {Array.from({ length: 36 }, (_, i) => (
      <span
        key={i}
        style={{
          height: 8,
          background: narrow ? (i < 12 ? "#315d87" : "#e6e7e4") : i < 28 ? "#178477" : "#e6e7e4",
          opacity: narrow && i < 4 ? 1 : 0.75,
          transformOrigin: "bottom",
          animation: `bar-in 0.45s cubic-bezier(0.23, 1, 0.32, 1) ${i * 20}ms both`,
        }}
      />
    ))}
  </div>
)

// ── Mini map (homepage variant) ──────────────────────────────────────────────

function MiniMap() {
  const { data } = useSnapshot()
  const sectors = data?.sectors ?? []
  const dataSources = data?.dataSources ?? { breadthHistory: false, constituents: false, fundamentals: false, foreignFlow: false, trajectory: false }
  const mapMode: MapViewMode = dataSources.trajectory ? "trajectory" : "current"
  const axisLabels = mapViewLabels(mapMode)
  const plot: MapPlotBounds = { left: 36, top: 24, width: 320, height: 180 }
  const domain = mapViewDomain(mapMode)
  const yBaseline = mapYBaseline(mapMode)
  const plottable = sectors.filter(
    (s) =>
      s.excess20d !== null &&
      mapYValue(s, mapMode) !== null,
  )
  const coverage = data?.coverageHonest
  const listedCoverage = data?.payload.coverage
  const gateMet = coverage?.coverage_gate_60pct_met ?? false
  const labelPositions = useMemo(
    () =>
      placeMapLabels(
        plottable.map((s) => {
          const yValue = mapYValue(s, mapMode) ?? yBaseline
          return {
            id: s.id,
            text: s.name,
            x: mapX(s.excess20d ?? 0, plot, domain),
            y: mapY(yValue, plot, domain),
            radius: 4,
            priority: Math.abs(s.excess20d ?? 0) + Math.abs(yValue - yBaseline) * 0.5,
          }
        }),
        { left: plot.left + 2, right: plot.left + plot.width - 2, top: plot.top + 2, bottom: plot.top + plot.height - 2 },
        4,
      ),
    [domain, mapMode, plottable, yBaseline],
  )
  return (
    <div
      style={{
        background: "#121619",
        color: "#fff",
        padding: 20,
        minHeight: 330,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div className="eyebrow" style={{ color: "#b8bdc0" }}>
        {axisLabels.title}
      </div>
      <div
        style={{
          fontSize: 10,
          color: "#8f9699",
          marginTop: 2,
          marginBottom: 6,
        }}
      >
        {axisLabels.subtitle}
      </div>
      <svg
        viewBox={`0 0 ${plot.left + plot.width + 12} ${plot.top + plot.height + 28}`}
        width="100%"
        height={plot.top + plot.height + 28}
        aria-label={axisLabels.title}
        style={{ display: "block" }}
      >
        {/* Quadrant fills */}
        <rect
          x={mapX(0, plot, domain)}
          y={plot.top}
          width={plot.left + plot.width - mapX(0, plot, domain)}
          height={mapY(yBaseline, plot, domain) - plot.top}
          fill="#1a2426"
        />
        <rect
          x={plot.left}
          y={mapY(yBaseline, plot, domain)}
          width={mapX(0, plot, domain) - plot.left}
          height={plot.top + plot.height - mapY(yBaseline, plot, domain)}
          fill="#1a2426"
        />
        {/* Axes */}
        <line
          x1={mapX(0, plot, domain)}
          x2={mapX(0, plot, domain)}
          y1={plot.top}
          y2={plot.top + plot.height}
          stroke="#ffffff33"
        />
        <line
          x1={plot.left}
          x2={plot.left + plot.width}
          y1={mapY(yBaseline, plot, domain)}
          y2={mapY(yBaseline, plot, domain)}
          stroke="#ffffff33"
        />
        {/* Axis labels */}
        <text x={plot.left + 4} y={plot.top + 10} fill="#8f9699" fontSize="9">
          {axisLabels.y}
        </text>
        <text
          x={plot.left + plot.width - 4}
          y={plot.top + plot.height - 4}
          fill="#8f9699"
          fontSize="9"
          textAnchor="end"
        >
          {axisLabels.x}
        </text>
        {/* Dots */}
        {plottable.map((s) => {
          const x = s.excess20d ?? 0
          const y = mapYValue(s, mapMode) ?? yBaseline
          const fill =
            s.leadership === "LEADING"
              ? "#438b82"
              : s.leadership === "IMPROVING"
                ? "#54718b"
                : s.leadership === "WEAKENING"
                  ? "#aa8750"
                  : s.leadership === "LAGGING"
                    ? "#ad6765"
                    : "#686e73"
          return (
            <circle
              key={s.id}
              cx={mapX(x, plot, domain)}
              cy={mapY(y, plot, domain)}
              r={4}
              fill={fill}
              opacity={s.leadership === "UNCONFIRMED" ? 0.4 : 0.9}
            />
          )
        })}
        {/* Labels only for selected material points */}
        {labelPositions.map((label) => {
          return (
            <text
              key={`lbl-${label.id}`}
              x={label.x}
              y={label.y}
              textAnchor={label.textAnchor}
              fill="#e6e7e4"
              fontSize="9"
              pointerEvents="none"
            >
              {label.text}
            </text>
          )
        })}
      </svg>
      <div
        style={{
          marginTop: 4,
          fontFamily: "Geist Mono",
          fontSize: 9,
          color: "#8f9699",
        }}
      >
        {mapMode === "current"
          ? "Current breadth view · diffusion change awaits comparable prior"
          : "Comparable breadth-delta view"}
      </div>
      {/* Honest coverage strip */}
      <div
        style={{
          display: "flex",
          gap: 10,
          fontSize: 10,
          color: "#8f9699",
          marginTop: 6,
          flexWrap: "wrap",
        }}
        aria-label="Snapshot coverage"
      >
        <span>
          Listed <strong style={{ color: "#e6e7e4" }}>{listedCoverage?.security_master_total ?? listedCoverage?.discovered_count ?? 0}</strong>
        </span>
        <span>
          Sample raw <strong style={{ color: "#e6e7e4" }}>{coverage?.raw_candidate_constituents ?? 0}</strong>
        </span>
        <span>
          Policy-elig{" "}
          <strong style={{ color: "#e6e7e4" }}>
            {coverage?.policy_eligible_constituents ?? 0}
          </strong>
        </span>
        <span>
          Observed{" "}
          <strong style={{ color: "#e6e7e4" }}>
            {coverage?.observed_eligible_features ?? 0}
          </strong>
        </span>
        <span>
          Acq-fail{" "}
          <strong style={{ color: "#e6e7e4" }}>
            {coverage?.acquisition_failed_constituents ?? 0}
          </strong>
        </span>
        <span
          style={{
            color: gateMet ? "#438b82" : "#ad6765",
            fontWeight: 600,
          }}
        >
          {gateMet ? "60% gate met" : "60% gate not met"}
        </span>
      </div>
    </div>
  )
}

// ── Ticker items ─────────────────────────────────────────────────────────────

const tickerItems = [
  { label: "TELCO", value: "LEADING", color: "#315d87" },
  { label: "COAL", value: "NARROWING", color: "#b34e4c" },
  { label: "HEALTH", value: "BROADENING", color: "#178477" },
  { label: "OIL & GAS", value: "LEADING", color: "#f26a3d" },
  { label: "BANKS", value: "STABLE", color: "#747a7d" },
  { label: "INFRA", value: "IMPROVING", color: "#438b82" },
  { label: "TECH", value: "WEAKENING", color: "#ad6765" },
]

// ── Main page ────────────────────────────────────────────────────────────────

export default function PublicHome() {
  const h2ScrambleRef = useRef<HTMLHeadingElement>(null)
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

  const doubled = [...tickerItems, ...tickerItems]

  return (
    <div style={{ background: "#ffffff", minHeight: "100%" }}>
      {/* ── Header ── */}
      <header
        className="public-header"
        style={{
          maxWidth: 1440,
          margin: "auto",
          padding: "16px 40px",
          display: "flex",
          justifyContent: "space-between",
          borderBottom: "1px solid #dfe2e1",
        }}
      >
        <BrandLockup />
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <ThemeToggle />
          <Link
            to="/overview"
            className="link-slide"
            style={{ color: "#16191c", fontSize: 12, textDecoration: "none" }}
          >
            Open workspace ↗
          </Link>
        </div>
      </header>

      <main className="public-main" style={{ maxWidth: 1440, margin: "auto", padding: "0 40px" }}>
        {/* ── Hero ── */}
        <section
          className="public-grid public-hero"
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(320px, .72fr) minmax(500px, 1.28fr)",
            gap: 50,
            padding: "90px 0 110px",
            alignItems: "center",
          }}
        >
          <div>
            <div className="eyebrow-muted reveal" style={{ marginBottom: 24 }}>
              Indonesian equity market intelligence
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
                endColor="#16191c"
              />
              <br />
              <DiaTextReveal
                text="See whether the market agrees."
                delay={950}
                endColor="#686e73"
              />
            </h1>

            <p
              className="reveal"
              style={{ color: "#686e73", lineHeight: 1.65, maxWidth: 440, marginBottom: 28 }}
            >
              IDX Leadership Diffusion scans the Indonesian equity market to identify emerging
              leadership, participation breadth, concentration, and deterioration beneath headline
              performance.
            </p>

            <div className="reveal public-cta-row" style={{ display: "flex", gap: 18, alignItems: "center" }}>
              <ShimmerCTAButton to="/overview">Explore the market →</ShimmerCTAButton>
              <Link
                to="/methodology"
                onMouseEnter={() => setMethodHovered(true)}
                onMouseLeave={() => setMethodHovered(false)}
                style={{
                  color: "#16191c",
                  fontSize: 13,
                  textDecoration: "none",
                  borderBottom: methodHovered ? "1px solid #16191c" : "1px solid transparent",
                  transition: "border-color 0.25s ease",
                }}
              >
                View methodology
              </Link>
            </div>

            <div className="eyebrow-muted reveal" style={{ marginTop: 26 }}>
              Snapshot-driven research · End-of-day
            </div>
            <div
              className="reveal"
              style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 12, alignItems: "center" }}
              aria-label="Hybrid product evidence model"
            >
              <EvidenceBadge kind="SNAPSHOT" compact />
              <EvidenceBadge kind="SAMPLE" compact />
              <EvidenceBadge kind="PROTOTYPE" compact />
              <EvidenceBadge kind="CONTEXT" compact />
            </div>
          </div>

          {/* ── Hero image column ── */}
          <div style={{ position: "relative" }}>
            <div className="eyebrow-muted" style={{ marginBottom: 8, color: "#7a5010" }}>
              Illustrative product view · sample values
            </div>
            <div
              style={{
                background: "#fff",
                border: "1px solid #dfe2e1",
                overflow: "hidden",
                aspectRatio: "835 / 454",
              }}
            >
              <ImageWithFallback
                src={leadershipMap}
                alt="IDX Leadership and Diffusion map showing sector movement across relative leadership and breadth"
                style={{ width: "100%", height: "100%", display: "block", objectFit: "contain" }}
              />
            </div>

            {/* Floating detail card */}
            <div
              className="hero-card-float"
              style={{
                background: "#fafaf8",
                border: "1px solid #dfe2e1",
                padding: 16,
                position: "absolute",
                right: -18,
                top: 36,
                width: 205,
                boxShadow: "0 12px 28px #12161918",
              }}
            >
              <div className="eyebrow-muted">Oil & Gas</div>
              <div style={{ margin: "9px 0", fontSize: 13, fontWeight: 600 }}>
                IMPROVING <span style={{ color: "#f26a3d" }}>→</span> LEADING
              </div>
              <div className="eyebrow-muted">
                Stable <span style={{ color: "#f26a3d" }}>→</span> Broadening
              </div>
              <div
                style={{
                  borderTop: "1px solid #dfe2e1",
                  marginTop: 12,
                  paddingTop: 10,
                  fontFamily: "Geist Mono",
                  fontSize: 11,
                }}
              >
                Breadth <b style={{ float: "right" }}>54% → 72%</b>
                <br />
                20D excess <b style={{ float: "right", color: "#178477" }}>+7.4%</b>
              </div>
            </div>

            {/* Marquee ticker */}
            <div
              className="marquee-wrap"
              style={{
                marginTop: 10,
                background: "#fafaf8",
                border: "1px solid #dfe2e1",
                padding: "10px 0",
              }}
            >
              <div className="marquee-track">
                {doubled.map((item, i) => (
                  <span
                    key={i}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "0 20px",
                      fontFamily: "Geist Mono",
                      fontSize: 10,
                      borderRight: "1px solid #dfe2e1",
                    }}
                  >
                    <span style={{ color: "#a8afb2" }}>{item.label}</span>
                    <b style={{ color: item.color }}>{item.value}</b>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Market fingerprint ── */}
        <section style={{ borderTop: "1px solid #dfe2e1", padding: "78px 0" }}>
          <div className="eyebrow-muted reveal">Market fingerprint / illustrative</div>

          {/* TextScramble headline */}
          <h2
            ref={h2ScrambleRef}
            style={{
              maxWidth: 700,
              fontSize: 42,
              letterSpacing: "-.05em",
              lineHeight: 1.05,
              fontWeight: 500,
            }}
          >
            <TextScrambleLine
              text="Performance tells you what moved."
              sectionRef={h2ScrambleRef}
              delay={0}
            />
            <br />
            <TextScrambleLine
              text="Diffusion tells you how it moved."
              sectionRef={h2ScrambleRef}
              delay={380}
              style={{ color: "#686e73" }}
            />
          </h2>

          <div
            className="public-grid reveal"
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 1,
              background: "#dfe2e1",
              border: "1px solid #dfe2e1",
              marginTop: 40,
            }}
          >
            <div style={{ background: "#fafaf8", padding: 28 }}>
              <div className="eyebrow-muted">Illustrative · sample values — Broad leadership</div>
              <div style={{ fontSize: 28, margin: "10px 0" }}>
                +6.8%{" "}
                <span style={{ fontSize: 13, color: "#686e73" }}>20D excess</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontFamily: "Geist Mono",
                  fontSize: 11,
                }}
              >
                <span>Breadth 76%</span>
                <span>Top-3 34%</span>
                <span style={{ color: "#178477" }}>BROADENING</span>
              </div>
              <DotField />
            </div>
            <div style={{ background: "#121619", color: "white", padding: 28 }}>
              <div className="eyebrow-muted" style={{ color: "#a8afb2" }}>
                Illustrative · sample values — Narrow leadership
              </div>
              <div style={{ fontSize: 28, margin: "10px 0" }}>
                +8.1%{" "}
                <span style={{ fontSize: 13, color: "#a8afb2" }}>20D excess</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontFamily: "Geist Mono",
                  fontSize: 11,
                }}
              >
                <span>Breadth 38%</span>
                <span>Top-3 71%</span>
                <span style={{ color: "#e8a88f" }}>NARROWING</span>
              </div>
              <DotField narrow />
            </div>
          </div>
          <p className="reveal" style={{ fontSize: 21, marginTop: 22 }}>
            Similar headline returns.{" "}
            <span style={{ color: "#686e73" }}>Very different market structure.</span>
          </p>
        </section>

        {/* ── Three lenses ── */}
        <section style={{ borderTop: "1px solid #dfe2e1", padding: "72px 0" }}>
          <div className="eyebrow-muted reveal">Three intelligence lenses</div>
          {[
            ["01", "Leadership", "Where relative strength is migrating."],
            ["02", "Diffusion", "Whether participation is spreading or narrowing."],
            ["03", "Confirmation", "What supports or contradicts the move."],
          ].map(([n, t, d], idx) => (
            <div
              key={n}
              className="reveal"
              style={{
                display: "grid",
                gridTemplateColumns: "80px 1fr 1fr",
                gap: 24,
                padding: "24px 0",
                borderBottom: "1px solid #dfe2e1",
                transitionDelay: `${idx * 80}ms`,
              }}
            >
              <span className="eyebrow-muted">{n}</span>
              <div>
                <h3 style={{ fontSize: 22, margin: 0 }}>{t}</h3>
                <p style={{ color: "#686e73", margin: "6px 0" }}>{d}</p>
              </div>
              <div
                style={{
                  alignSelf: "center",
                  fontFamily: "Geist Mono",
                  fontSize: 11,
                  color: "#686e73",
                  whiteSpace: "pre-line",
                }}
              >
                {t === "Confirmation"
                  ? "Fundamentals  SUPPORTIVE\nForeign Flow   CONFIRMING\nConcentration  ELEVATED"
                  : "····●  →  ····●\nRelative leadership / breadth"}
              </div>
            </div>
          ))}
        </section>

        {/* ── Dark CTA band with grain ── */}
        <section
          className="grain-bg"
          style={{
            background: "#121619",
            color: "white",
            margin: "0 -40px",
            padding: "82px 40px",
          }}
        >
          <div className="reveal" style={{ maxWidth: 1360, margin: "auto" }}>
            <div className="eyebrow-muted" style={{ color: "#a8afb2" }}>
              Sectors data / Research architecture
            </div>
            <h2
              style={{ fontSize: 44, maxWidth: 640, letterSpacing: "-.05em", lineHeight: 1.05 }}
            >
              <RevealText text="Built on the structure beneath IDX." delay={60} />
            </h2>
            <div
              style={{
                display: "flex",
                gap: 12,
                flexWrap: "wrap",
                fontFamily: "Geist Mono",
                fontSize: 12,
                color: "#cbd0d1",
                marginTop: 24,
              }}
            >
              {["SECTORS DATA", "↓", "IDX UNIVERSE", "↓", "SECTOR / INDUSTRY TAXONOMY", "↓"].map(
                (s, i) => (
                  <span key={i}>{s}</span>
                ),
              )}
              <span style={{ color: "#f26a3d" }}>LEADERSHIP INTELLIGENCE</span>
            </div>
          </div>
        </section>

        {/* ── Methodology callout ── */}
        <section style={{ padding: "80px 0 100px" }}>
          <div className="reveal">
            <div className="eyebrow-muted">Methodology / Transparent by design</div>
            <h2
              style={{ fontSize: 42, letterSpacing: "-.05em", marginBottom: 18, fontWeight: 500 }}
            >
              <RevealText text="No black-box conviction score." delay={60} />
            </h2>
            <p style={{ color: "#686e73", maxWidth: 580 }}>
              Leadership, diffusion, concentration, persistence, and confirmation are measured
              independently—and can contradict one another.
            </p>
            <div style={{ marginTop: 24 }}>
              <InteractiveHoverCTA to="/overview" label="Open IDX Leadership Diffusion" />
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
