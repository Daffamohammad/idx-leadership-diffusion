// Keep provenance identifiers intact; translate archival terms only for display.
export function publicCopy(text: string) {
  return text.replace(/recorded/gi, "observed").replace(/samples?/gi, "coverage").replace(/snapshots?/gi, "market observations").replace(/immutable releases?/gi, "data package").replace(/selected releases?/gi, "selected data").replace(/\breleases?\b/gi, "data package");
}
