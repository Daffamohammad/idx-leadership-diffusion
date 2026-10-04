"""Normalize complete official public registers without publishing private addresses."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from idx_leadership.providers.idx_ownership import compare_one, read_five, read_one, source


def main() -> int:
    p = argparse.ArgumentParser()
    for key in ('current', 'previous', 'five', 'current-url', 'previous-url', 'five-url', 'as-of', 'previous-as-of', 'five-as-of', 'five-previous-as-of', 'out'):
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    try:
        current = read_one(Path(a.current), as_of=a.as_of)
        previous = read_one(Path(a.previous), as_of=a.previous_as_of)
        five = read_five(Path(a.five), as_of=a.five_as_of, previous_as_of=a.five_previous_as_of)
        if not current or not previous or not five or a.previous_as_of >= a.as_of or a.five_as_of < a.as_of:
            raise ValueError('empty or nonchronological register')
        payload = dict(schema_version='idx-ownership-v1', as_of=a.as_of, previous_as_of=a.previous_as_of, five_as_of=a.five_as_of,
                       registers={'one': current, 'five': five}, changes=compare_one(current, previous),
                       sources=[source(Path(a.current), a.current_url, a.as_of), source(Path(a.previous), a.previous_url, a.previous_as_of), source(Path(a.five), a.five_url, a.five_as_of)],
                       coverage={'one_rows': len(current), 'one_issuers': len({r['ticker'] for r in current}), 'five_rows': len(five), 'five_issuers': len({r['ticker'] for r in five}), 'previous_rows': len(previous), 'five_unreconciled_account_blocks': sum(r['account_totals_reconciled'] is False for r in five)},
                       limitations=['Public names are not unique SID identities. Equal names are searchable connections, not proof of a single beneficial owner.',
                                    'Disclosure entries and exits can reflect threshold crossings, transfers or corrections; they are not inferred purchases or sales.',
                                    'Shareholding percentages are not voting-right percentages. These registers do not determine free float or legal control.',
                                    '1% and 5% releases have separate dates and populations. Never combine their totals.',
                                    'Some 5% custody-account cells do not reconcile to the published investor total. Retain the published combined total and flag those blocks; do not infer missing scale or sum repeated totals.'])
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
        print(json.dumps(payload['coverage']))
        return 0
    except (OSError, ImportError, ValueError, KeyError) as exc:
        print(f'SOURCE_UNAVAILABLE: {exc}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
