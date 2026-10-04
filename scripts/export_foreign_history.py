"""Offline official daily PDF flow export, with complete-session and YTD gates."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from idx_leadership.providers.idx_flow_history import parse_daily_flow, validate_continuity


def main() -> int:
    p = argparse.ArgumentParser()
    for key in ('pdf-root', 'source-list', 'benchmark', 'out'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--monthly', nargs='*', default=[])
    a = p.parse_args()
    try:
        import pdfplumber
        sources = json.loads(Path(a.source_list).read_text())
        rows = []
        for entry in sources:
            path = Path(a.pdf_root) / entry['file']
            stamp = entry['file'][3:9]
            as_of = f'20{stamp[:2]}-{stamp[2:4]}-{stamp[4:]}'
            with pdfplumber.open(path) as pdf:
                row = parse_daily_flow(pdf.pages[0].extract_text(), pdf.pages[1].extract_text(), expected_date=as_of)
            row['source'] = dict(url=entry['url'], file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            rows.append(row)
        rows.sort(key=lambda r: r['as_of'])
        sessions = sorted(set(pd.read_csv(a.benchmark)['date'].str[:10]))
        validate_continuity(rows, sessions)
        by_date = {r['as_of']: r for r in rows}
        comparisons = []
        for filename in a.monthly:
            release = json.loads(Path(filename).read_text())
            if release.get('status') != 'READY':
                raise ValueError('monthly comparison source is unvalidated')
            diffs = [abs(by_date[r['as_of']]['net_foreign_value_idr'] - r['net_foreign_value_idr']) for r in release['daily']]
            if max(diffs) > 5_000_001:
                raise ValueError('daily PDF does not match monthly rupiah net flow')
            comparisons.append(dict(source=release['source'], rows=len(diffs), maximum_difference_idr=max(diffs)))
        payload = dict(schema_version='idx-foreign-history-v1', as_of=rows[-1]['as_of'], start=rows[0]['as_of'], daily=rows,
                       validation=dict(session_continuity=True, ytd_continuity=True, monthly_comparisons=comparisons),
                       scope='All stock trading markets: regular, cash and negotiated', units='IDR', precision_idr=10_000_000,
                       limitations=['Daily PDF figures are rounded to 0.01 billion IDR; period sums retain that rounding.', 'Foreign flow measures transactions, not ownership or legal control.'])
        out = Path(a.out);out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n')
        print(json.dumps(dict(sessions=len(rows), start=payload['start'], as_of=payload['as_of'], monthly_comparisons=len(comparisons))))
        return 0
    except (OSError, ImportError, ValueError, KeyError) as exc:
        print(f'SOURCE_UNAVAILABLE: {exc}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
