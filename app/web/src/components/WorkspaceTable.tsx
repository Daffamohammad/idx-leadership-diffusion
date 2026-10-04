import { useState, type ReactNode } from "react";
export function WorkspaceTable<T>({ rows, columns, rowKey }: { rows: T[]; columns: { label: string; cell: (row: T) => ReactNode }[]; rowKey: (row: T) => string }) {
  const [page, setPage] = useState(0);
  const total = Math.max(1, Math.ceil(rows.length / 40)); const current = Math.min(page, total - 1);
  return <><div className="workspace-table-scroll"><table className="workspace-table"><thead><tr>{columns.map(c => <th key={c.label} scope="col">{c.label}</th>)}</tr></thead><tbody>{rows.slice(current * 40, current * 40 + 40).map(row => <tr key={rowKey(row)}>{columns.map(c => <td key={c.label}>{c.cell(row)}</td>)}</tr>)}</tbody></table></div>{!rows.length && <p>No matching records.</p>}<div className="workspace-controls"><button className="btn btn-outline" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button><span aria-live="polite">{rows.length.toLocaleString()} records · Page {current + 1} of {total}</span><button className="btn btn-outline" disabled={current + 1 >= total} onClick={() => setPage(current + 1)}>Next</button></div></>;
}
