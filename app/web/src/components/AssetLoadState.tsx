/** Keep unreachable or rejected assets distinct from an absent recording. */
export function AssetLoadState({ label, loading, error, absentMessage }: {
  label: string;
  loading: boolean;
  error: string | null;
  absentMessage: string;
}) {
  if (error) return <div className="asset-load-state" role="alert">
    <strong>{label} could not be loaded</strong>
    <p>{/Failed to fetch|NetworkError|Load failed/i.test(error)
      ? "The recorded release could not be reached. Retry when the connection is available."
      : error}</p>
    <button type="button" className="btn btn-outline" onClick={() => window.location.reload()}>Retry</button>
  </div>;
  return <div className="asset-load-state" role="status">
    {loading ? `Loading and verifying ${label.toLowerCase()}…` : absentMessage}
  </div>;
}
