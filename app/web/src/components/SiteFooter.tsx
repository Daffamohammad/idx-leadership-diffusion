import { Link } from "react-router"
import { BrandLockup, BrandMark } from "./BrandMark"

export interface SiteFooterLink {
  label: string
  href?: string
  /** Opens in a new tab and shows an outward arrow. */
  external?: boolean
}

export interface SiteFooterColumn {
  title: string
  links: SiteFooterLink[]
}

export interface SiteFooterProps {
  tagline?: string
  columns?: SiteFooterColumn[]
  statusLabel?: string
  statusHref?: string
  year?: number
}

const defaultColumns: SiteFooterColumn[] = [
  {
    title: "Research",
    links: [
      { label: "Dashboard", href: "/sectors" },
      { label: "Leadership map", href: "/map" },
      { label: "Weekly changes", href: "/what-changed" },
      { label: "Stock heatmap", href: "/heatmap" },
    ],
  },
  {
    title: "Coverage",
    links: [
      { label: "Coverage & sources", href: "/sources" },
      { label: "Ownership", href: "/ownership" },
      { label: "Foreign flow", href: "/foreign" },
      { label: "How to read the research", href: "/methodology" },
    ],
  },
  {
    title: "Reference",
    links: [
      { label: "Arthara conglomerates", href: "https://www.arthara.id/konglo", external: true },
      { label: "IDX statistics", href: "https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/", external: true },
    ],
  },
]

function FooterLink({ link }: { link: SiteFooterLink }) {
  const content = (
    <>
      {link.label}
      {link.external && <span aria-hidden="true" style={{ color: "var(--muted)" }}>↗</span>}
    </>
  )
  if (!link.href) return <span className="site-footer-link">{content}</span>
  if (link.external) {
    return (
      <a className="site-footer-link" href={link.href} target="_blank" rel="noopener noreferrer">
        {content}
      </a>
    )
  }
  return (
    <Link className="site-footer-link" to={link.href}>
      {content}
    </Link>
  )
}

// Site footer: link columns with a status row, closing in a large fading
// Diffusion mark. Adapted from the Arc site-footer block to this project's
// components, tokens, and router; no newsletter section — there is no
// backend for one.
export default function SiteFooter({
  tagline = "Indonesian equity market intelligence.",
  columns = defaultColumns,
  statusLabel = "Data through 2 Oct 2026",
  statusHref = "/sources",
  year = new Date().getFullYear(),
}: SiteFooterProps) {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--line)",
        padding: "56px 0 0",
        overflow: "hidden",
      }}
    >
      <div className="site-footer-top reveal">
        <div style={{ minWidth: 0 }}>
          <Link to="/" style={{ textDecoration: "none" }} aria-label="The Diffusion home">
            <BrandLockup />
          </Link>
          <p style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.6, maxWidth: 300, margin: "14px 0 0" }}>
            {tagline}
          </p>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65, maxWidth: 340, margin: "14px 0 0" }}>
            The Diffusion is an analytical market-intelligence prototype for research and
            education. It does not provide investment advice. Pages open verified local
            data and make no provider calls.
          </p>
        </div>
        <nav className="site-footer-columns" aria-label="Footer">
          {columns.map((column) => (
            <div key={column.title} style={{ minWidth: 0 }}>
              <h2
                style={{
                  margin: "0 0 12px",
                  fontFamily: "Geist Mono, monospace",
                  fontSize: 11,
                  letterSpacing: ".08em",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  fontWeight: 500,
                }}
              >
                {column.title}
              </h2>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 8 }}>
                {column.links.map((link) => (
                  <li key={link.label}>
                    <FooterLink link={link} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>

      <div className="site-footer-bottom reveal">
        <span style={{ color: "var(--muted)", fontSize: 12 }}>© {year} The Diffusion</span>
        <Link
          to={statusHref}
          aria-label={`${statusLabel} — open Coverage and sources`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            color: "var(--muted)",
            fontSize: 12,
            textDecoration: "none",
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--up)",
              boxShadow: "0 0 0 3px color-mix(in oklab, var(--up) 18%, transparent)",
            }}
          />
          {statusLabel}
        </Link>
      </div>

      <div className="site-footer-mark reveal" aria-hidden="true">
        <BrandMark size={620} />
      </div>
    </footer>
  )
}
