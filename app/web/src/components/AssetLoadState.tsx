import { publicErrorText } from "../data/publicCopy";
/** Keep unreachable or rejected assets distinct from missing data. */
export function AssetLoadState({ label, loading, error, absentMessage }: {
  label: string;
  loading: boolean;
  error: string | null;
  absentMessage: string;
}) {
  if (error) return <div className="asset-load-state" role="alert">
    <strong>{label} could not be loaded</strong>
    <p>{publicErrorText(error)}</p>
    <button type="button" className="btn btn-outline" onClick={() => window.location.reload()}>Retry</button>
  </div>;
  return <div className="asset-load-state" role="status">
    {loading ? `Loading and verifying ${label.toLowerCase()}…` : absentMessage}
  </div>;
}
