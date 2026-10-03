// Global Markets typed contract — conditional real-data MVP (P4).
// Status: BLOCKED on source validation in this cycle. No futures/macro cards
// are rendered; this contract prevents fake live quotes and empty nav targets.

export type InstrumentKind =
  | "SPOT_FX"
  | "BI_REFERENCE"
  | "INDEX"
  | "ETF"
  | "FUTURES"
  | "BOND_YIELD";

export interface GlobalQuote {
  symbol: string;
  label: string;
  kind: InstrumentKind;
  exchange: string | null;
  currency: string;
  unit: string;
  last: number | null;
  change: number | null;
  changePct: number | null;
  observationTimestamp: string | null;
  timezone: string;
  status: "LIVE" | "DELAYED" | "CLOSED" | "STALE" | "UNAVAILABLE";
  source: string;
  sourceUrl: string | null;
  contractExpiry: string | null;
  continuousSeriesPolicy: string | null;
  quantitativeUse: boolean;
}

export interface GlobalBoard {
  asOf: string | null;
  quotes: GlobalQuote[];
  limitations: string[];
}

export function emptyGlobalBoard(): GlobalBoard {
  return {
    asOf: null,
    quotes: [],
    limitations: [
      "No validated global board in this cycle; no spot/index/ETF/futures rows are fabricated.",
      "Futures require contract/expiry and continuous-series/roll policy; an interest-rate futures price is not a yield.",
      "TradingView iframes are external context only and are never scraped into a backend feed.",
    ],
  };
}
