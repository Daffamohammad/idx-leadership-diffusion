// Indonesia Macro typed contract — conditional real-data MVP (P4).
// Status: BLOCKED on source validation in this cycle. No live cards are rendered
// from this contract; it exists so a future pilot can land without schema drift.
// Sources must be official BI/BPS releases with replayable caches.

export type MacroFrequency = "DAILY" | "MONTHLY" | "QUARTERLY";
export type MacroIndicatorId =
  | "GDP_GROWTH"
  | "CPI_HEADLINE"
  | "CPI_CORE"
  | "BI_RATE"
  | "JISDOR"
  | "RESERVES"
  | "TRADE_BALANCE"
  | "M2";

export interface MacroObservation {
  indicator: MacroIndicatorId;
  observationPeriod: string;
  releaseDate: string;
  fetchedAt: string;
  unit: string;
  frequency: MacroFrequency;
  revisionVintage: string;
  sourceUrl: string;
  sourceName: "BI" | "BPS";
  value: number | null;
  momPct: number | null;
  yoyPct: number | null;
  quantitativeUse: boolean;
  cachePath: string | null;
}

export interface MacroBoard {
  asOf: string | null;
  observations: MacroObservation[];
  limitations: string[];
}

export const MACRO_INDICATORS: MacroIndicatorId[] = [
  "GDP_GROWTH",
  "CPI_HEADLINE",
  "CPI_CORE",
  "BI_RATE",
  "JISDOR",
  "RESERVES",
  "TRADE_BALANCE",
  "M2",
];

export function emptyMacroBoard(): MacroBoard {
  return {
    asOf: null,
    observations: [],
    limitations: [
      "No BI/BPS pilot landed in this cycle; dashboard shows no macro cards rather than fake live values.",
      "Quarterly GDP must not carry a monthly CPI date; quarterly and monthly frequencies stay distinct with no forward-fill.",
      "Consensus/surprise and nowcasts remain future analytical work without validated methods.",
    ],
  };
}
