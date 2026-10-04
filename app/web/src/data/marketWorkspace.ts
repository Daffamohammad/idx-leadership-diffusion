import { useEffect, useState } from "react";
import { useSnapshot } from "./SnapshotProvider";

export interface MarketStock {
  ticker: string; company_name: string; instrument_type: string; analysis_requested: boolean;
  close: number | null; previous_close: number | null; return_1d: number | null; return_1w: number | null;
  market_cap: number | null; traded: boolean; signal_eligible: boolean; history_status: string;
  foreign_buy_shares: number | null; foreign_sell_shares: number | null; foreign_net_shares: number | null;
  taxonomy: { sector?: string; subindustry?: string }; classification_as_of: string | null; listing_board: string | null;
}
export interface OwnershipEdge {
  group_id: string; group_name: string; holder: string; ticker: string; percentage: number;
  as_of: string; source: string; relationship: string;
  control_source: { source: string; as_of: string; ultimate_holders?: string[] } | null;
}
export interface MarketWorkspace {
  schema_version: "market-workspace-v1"; snapshot_id: string; as_of: string;
  records: MarketStock[]; benchmark: { date: string; close: number }[];
  breadth: { advancers: number; flat: number; decliners: number; traded_count: number; not_traded_or_unavailable: number; scope: string };
  index_movers: { status: string; reason?: string; residual?: number; calculated_change?: number; official_change?: number; method?: string; source?: string;
    rows: { ticker: string; company_name: string; points: number; return_1d: number | null }[] };
  weekly_start: string; weekly_end: string; ownership_edges: OwnershipEdge[];
  coverage: { requested: number; observed_histories: number; signal_eligible: number; gaps: { failed: string[]; quarantined: string[] } };
  limitations: string[]; sources: Record<string, unknown>;
}
export interface Holder {
  row_id: string; ticker: string; issuer: string; holder: string; classification: string;
  local_foreign: string; shares: number; percentage: number; as_of: string;
  identity_ambiguous: boolean; scripless?: number; scrip?: number;
  previous_shares?: number | null; previous_percentage?: number | null; account_count?: number; account_totals_reconciled?: boolean;
}
export interface HoldingChange {
  ticker: string; holder: string; kind: string; current_shares: number | null; previous_shares: number | null;
  current_percentage: number | null; previous_percentage: number | null; delta_shares: number | null;
}
export interface OwnershipWorkspace {
  schema_version: "idx-ownership-v1"; as_of: string; previous_as_of: string; five_as_of: string;
  registers: { one: Holder[]; five: Holder[] }; changes: HoldingChange[];
  sources: { filename: string; sha256: string; url: string; as_of: string }[];
  coverage: { one_rows: number; one_issuers: number; five_rows: number; five_issuers: number; previous_rows: number }; limitations: string[];
}
export interface ForeignHistory {
  schema_version: "idx-foreign-history-v1"; as_of: string; start: string; scope: string; precision_idr: number;
  daily: { as_of: string; net_foreign_value_idr: number; ytd_net_foreign_value_idr: number; source: { url: string; file: string; sha256: string } }[];
  validation: { session_continuity: boolean; ytd_continuity: boolean; monthly_comparisons: unknown[] }; limitations: string[];
}
interface Asset { path: string; sha256: string; as_of: string; schema_version: string }
interface WorkspaceIndex { snapshot_id: string; as_of: string; assets: Record<string, Asset> }
const requests = new Map<string, Promise<unknown>>();
async function checkedFetch(asset: Asset): Promise<unknown> {
  if (!asset.path.startsWith("/market/") || asset.path.includes("..")) throw new Error("Workspace path is invalid");
  const response = await fetch(asset.path);
  if (!response.ok || !response.headers.get("content-type")?.includes("json")) throw new Error("Workspace file unavailable");
  const bytes = await response.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hash = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
  if (hash !== asset.sha256) throw new Error("Workspace integrity check failed");
  const data = JSON.parse(new TextDecoder().decode(bytes));
  if (data.schema_version !== asset.schema_version || data.as_of !== asset.as_of) throw new Error("Workspace identity mismatch");
  return data;
}
export function useWorkspaceAsset<T extends { as_of: string }>(key: "market" | "ownership" | "foreign") {
  const snapshot = useSnapshot();
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  useEffect(() => {
    let cancelled = false;
    const id = snapshot.snapshotId; const cutoff = snapshot.payload?.as_of?.slice(0, 10);
    if (!id || !cutoff) { setState({ data: null, error: snapshot.error, loading: snapshot.loading }); return; }
    setState({ data: null, error: null, loading: true });
    const requestKey = `${id}:${key}`;
    if (!requests.has(requestKey)) requests.set(requestKey, (async () => {
      const response = await fetch("/market/index.json", { cache: "no-store" });
      if (!response.ok || !response.headers.get("content-type")?.includes("json")) throw new Error("This snapshot has no expanded market workspace");
      const index = await response.json() as WorkspaceIndex;
      const asset = index.assets?.[key];
      if (index.snapshot_id !== id || index.as_of.slice(0, 10) !== cutoff || !asset || asset.as_of > cutoff) throw new Error("Workspace does not belong to this snapshot");
      const data = await checkedFetch(asset) as T;
      if (key === "market" && (data as unknown as MarketWorkspace).snapshot_id !== id) throw new Error("Market snapshot identity mismatch");
      if (key === "ownership" && (data as unknown as OwnershipWorkspace).five_as_of > cutoff) throw new Error("Ownership release is later than this snapshot");
      return data;
    })());
    requests.get(requestKey)!.then(data => { if (!cancelled) setState({ data: data as T, error: null, loading: false }); }).catch(error => { requests.delete(requestKey); if (!cancelled) setState({ data: null, error: String(error.message ?? error), loading: false }); });
    return () => { cancelled = true; };
  }, [key, snapshot.snapshotId, snapshot.payload?.as_of, snapshot.error, snapshot.loading]);
  return state;
}
