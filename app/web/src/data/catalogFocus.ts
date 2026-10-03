import type { TaxonomyKind } from "./snapshot";

// Session-scoped handoff between the group catalog and a group detail view.
// Stored in sessionStorage (never localStorage) so the state dies with the tab
// and a cold deep link still opens the canonical catalog URL.

export const CATALOG_URL_KEY = "catalog-url";
export const CATALOG_FOCUS_KEY = "catalog-focus";

// Remember which row the user left from, so returning to the catalog restores
// focus to that row instead of dropping focus on <body>.
export function rememberCatalogFocus(groupId: string): void {
  try {
    sessionStorage.setItem(CATALOG_FOCUS_KEY, groupId);
  } catch {
    /* storage unavailable — catalog still opens, just without focus restore */
  }
}

export function takeCatalogFocus(): string | null {
  try {
    const value = sessionStorage.getItem(CATALOG_FOCUS_KEY);
    if (value) sessionStorage.removeItem(CATALOG_FOCUS_KEY);
    return value;
  } catch {
    return null;
  }
}

export function peekCatalogFocus(): string | null {
  try {
    return sessionStorage.getItem(CATALOG_FOCUS_KEY);
  } catch {
    return null;
  }
}

export function clearCatalogFocus(): void {
  try {
    sessionStorage.removeItem(CATALOG_FOCUS_KEY);
  } catch {
    /* ignore */
  }
}

// Remember the exact catalog state (filter/view/sort/sort direction) so a
// detail view can come straight back to it.
export function rememberCatalogUrl(pathname: string, search: string): void {
  try {
    sessionStorage.setItem(CATALOG_URL_KEY, `${pathname}${search}`);
  } catch {
    /* storage unavailable — back link falls back to the canonical URL */
  }
}

// Best-effort return to the exact catalog state the user left behind. Falls
// back to the canonical tab URL on a cold deep link.
export function catalogHref(taxonomyKind: TaxonomyKind): string {
  const fallback = `/groups?taxonomy=${taxonomyKind}`;
  try {
    const stored = sessionStorage.getItem(CATALOG_URL_KEY);
    if (stored && stored.startsWith("/groups")) {
      const url = new URL(stored, window.location.origin);
      url.searchParams.set("taxonomy", taxonomyKind);
      return `${url.pathname}${url.search}`;
    }
  } catch {
    /* storage unavailable — canonical URL is still correct */
  }
  return fallback;
}
