import { useId, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import type { ListingRegistryAdapted } from "../data/adapter";

export default function TickerSearch({ registry }: { registry: ListingRegistryAdapted | null }) {
  const id = useId();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const matches = useMemo(() => {
    const term = query.trim().toUpperCase();
    if (!term) return [];
    return (registry?.records ?? [])
      .filter(row => `${row.ticker} ${row.company_name}`.toUpperCase().includes(term))
      .sort((a, b) => Number(b.ticker.startsWith(term)) - Number(a.ticker.startsWith(term)))
      .slice(0, 8);
  }, [registry, query]);
  const choose = (ticker: string) => {
    setQuery(""); setOpen(false);
    navigate(`/ticker/${encodeURIComponent(ticker)}`);
  };
  return (
    <div className="ticker-search" onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }}>
      <input role="combobox" aria-label="Search ticker or company" aria-autocomplete="list"
        aria-controls={id} aria-expanded={open && Boolean(query.trim())}
        aria-activedescendant={open && matches[active] ? `${id}-${active}` : undefined}
        placeholder="Search ticker or company…" value={query}
        onFocus={() => setOpen(true)}
        onChange={event => { setQuery(event.target.value); setActive(0); setOpen(true); }}
        onKeyDown={event => {
          if (event.key === "Escape") setOpen(false);
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true);
            setActive(value => matches.length ? (value + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length : 0);
          }
          if (event.key === "Enter" && matches[active]) { event.preventDefault(); choose(matches[active].ticker); }
        }} />
      {open && query.trim() && (
        <div id={id} role="listbox" aria-label="Matching tickers" className="ticker-search-results">
          {matches.map((row, index) => (
            <button key={row.ticker} id={`${id}-${index}`} role="option" aria-selected={active === index}
              onMouseDown={event => event.preventDefault()} onClick={() => choose(row.ticker)}>
              <strong>{row.ticker.replace(/\.JK$/, "")}</strong><span>{row.company_name}</span>
            </button>
          ))}
          {!matches.length && <p role="status">No matching listing.</p>}
        </div>
      )}
    </div>
  );
}
