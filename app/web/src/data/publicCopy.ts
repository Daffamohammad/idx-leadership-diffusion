// Keep provenance identifiers intact; translate archival terms only for display.
export function publicCopy(text: string) {
  return text.replace(/recorded/gi, "observed").replace(/samples?/gi, "coverage").replace(/snapshots?/gi, "market observations").replace(/immutable releases?/gi, "data package").replace(/selected releases?/gi, "selected data").replace(/\breleases?\b/gi, "data package").replace(/\bmanifest\b/gi, "data package").replace(/\brollback\b/gi, "previous data package");
}

// Classify load failures before they reach visible copy so integrity and
// provider wording cannot leak into user-facing messages.
export function publicErrorText(error: string) {
  if (/Failed to fetch|NetworkError|Load failed|HTTP \d+|file unavailable/i.test(error)) {
    const code = error.match(/HTTP \d+/)?.[0];
    return `The data could not be reached${code ? ` (${code})` : ""}. Retry when the connection is available.`;
  }
  if (/integrity check failed/i.test(error)) {
    return "Data integrity check failed. The source evidence cannot be verified.";
  }
  return publicCopy(error);
}
