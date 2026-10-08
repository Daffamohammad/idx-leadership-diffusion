import type { Holder, OwnershipWorkspace } from "./marketWorkspace";

export function ownershipComparisons(data: OwnershipWorkspace, five: boolean) {
  if (five) return data.registers.five.map(row => ({ticker: row.ticker, holder: row.holder,
    previous_shares: row.previous_shares ?? null, current_shares: row.shares,
    delta_shares: row.previous_shares == null || row.shares == null ? null : row.shares - row.previous_shares,
    previous_percentage: null as number | null, current_percentage: row.percentage,
    kind: row.previous_shares == null ? "Prior shares undisclosed" : "Published share comparison"}));
  if (!data.registers.previous_one?.length) return [];
  const key = (row: Holder) => `${row.ticker}\u0000${row.holder}`;
  const index = (rows: Holder[]) => {
    const map = new Map<string, Holder[]>();
    for (const row of rows) map.set(key(row), [...(map.get(key(row)) ?? []), row]);
    return map;
  };
  const previous = index(data.registers.previous_one ?? []), current = index(data.registers.one);
  return [...new Set([...previous.keys(), ...current.keys()])].flatMap(id => {
    const oldRows = previous.get(id) ?? [], newRows = current.get(id) ?? [];
    if (oldRows.length > 1 || newRows.length > 1 || [...oldRows, ...newRows].some(row => row.identity_ambiguous)) return [];
    const old = oldRows[0], row = newRows[0], source = row ?? old;
    const difference = old?.shares != null && row?.shares != null ? row.shares - old.shares : null;
    return [{ticker: source.ticker, holder: source.holder, previous_shares: old?.shares ?? null, current_shares: row?.shares ?? null,
      delta_shares: difference, previous_percentage: old?.percentage ?? null, current_percentage: row?.percentage ?? null,
      kind: !old ? "Disclosure entry" : !row ? "Disclosure exit" : difference === 0 && old.percentage === row.percentage ? "Unchanged position" : "Matched published name"}];
  });
}
