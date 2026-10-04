"""Public IDX/KSEI ownership releases; published names are not SID identities."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import hashlib
import math
from pathlib import Path
import re
from typing import Any, Iterable

ONE_HEADERS = ('DATE', 'SHARE_CODE', 'ISSUER_NAME', 'INVESTOR_NAME', 'INVESTOR_CLASSIFICATION', 'LOCAL_FOREIGN', 'NATIONALITY', 'DOMICILE', 'HOLDINGS_SCRIPLESS', 'HOLDINGS_SCRIP', 'TOTAL_HOLDING_SHARES', 'PERCENTAGE')


def number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError('boolean holding')
    result = float(str(value).replace(',', '').strip())
    if not math.isfinite(result) or result < 0:
        raise ValueError('invalid holding')
    return result


def iso_date(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return date.fromisoformat(str(value)[:10]).isoformat()


def text(value: Any) -> str:
    return str(value or '').strip()


def _code(value: Any) -> str:
    code = 'TRUE' if value is True else text(value).upper()
    if not re.fullmatch(r'[A-Z0-9]{4,5}', code):
        raise ValueError(f'invalid share code: {code}')
    return code


def normalize_one(rows: Iterable[dict[str, Any]], *, as_of: str) -> list[dict[str, Any]]:
    result = []
    for i, row in enumerate(rows):
        if iso_date(row['DATE']) != as_of:
            raise ValueError('ownership date mismatch')
        scripless, scrip, total = (number(row[k]) for k in ONE_HEADERS[8:11])
        pct = number(row['PERCENTAGE'])
        if abs(scripless + scrip - total) > .01 or pct > 100:
            raise ValueError('ownership totals do not reconcile')
        holder = text(row['INVESTOR_NAME'])
        if not holder:
            raise ValueError('missing holder')
        result.append(dict(row_id=f'1:{as_of}:{i + 1}', ticker=_code(row['SHARE_CODE']), issuer=text(row['ISSUER_NAME']), holder=holder,
                           classification=text(row['INVESTOR_CLASSIFICATION']) or 'Unclassified', local_foreign=text(row['LOCAL_FOREIGN']) or 'Unclassified',
                           scripless=scripless, scrip=scrip, shares=total, percentage=pct, as_of=as_of))
    identities = Counter((r['ticker'], r['holder']) for r in result)
    for row in result:
        row['identity_ambiguous'] = identities[row['ticker'], row['holder']] != 1
    return result


def normalize_five(rows: Iterable[list[Any]], *, as_of: str, previous_as_of: str) -> list[dict[str, Any]]:
    """Each numbered block is one published investor, with multiple account rows.

    Aggregate fields are carried on the block's first row. We independently
    reconcile the account sums, never sum repeated aggregate fields.
    """
    result: list[dict[str, Any]] = []
    current = None
    for source in rows:
        row = list(source) + [None] * max(0, 18 - len(source))
        if not text(row[1]):
            continue
        code = _code(row[1])
        if row[0] is not None:
            current = dict(row_id=f'5:{as_of}:{len(result) + 1}', ticker=code, issuer=text(row[2]), holder=text(row[4]), classification='Not supplied',
                           local_foreign=text(row[10]) or 'Unclassified', shares=number(row[15]), percentage=number(row[16]),
                           previous_shares=None if text(row[12]) == '-' else number(row[12]), previous_percentage=None if text(row[13]) == '-' else number(row[13]), as_of=as_of, previous_as_of=previous_as_of,
                           account_count=0, account_shares=0., previous_account_shares=0.)
            if not current['holder'] or current['percentage'] > 100 or (current['previous_percentage'] or 0) > 100:
                raise ValueError('invalid investor block')
            result.append(current)
        if current is None or current['ticker'] != code or (text(row[4]) and text(row[4]) != current['holder']):
            raise ValueError('orphan custody account')
        for idx, key in ((15, 'shares'), (16, 'percentage'), (12, 'previous_shares'), (13, 'previous_percentage')):
            if row[idx] is not None and text(row[idx]) != '-' and (current[key] is None or abs(number(row[idx]) - current[key]) > .01):
                raise ValueError('conflicting repeated investor aggregate')
        current['account_count'] += 1
        current['account_shares'] += number(0 if text(row[14]) == '-' else row[14])
        current['previous_account_shares'] += number(0 if text(row[11]) == '-' else row[11])
    for row in result:
        row['account_totals_reconciled'] = abs(row.pop('account_shares') - row['shares']) <= .01 and (row['previous_shares'] is None or abs(row['previous_account_shares'] - row['previous_shares']) <= .01)
        row.pop('previous_account_shares', None)
    identities = Counter((r['ticker'], r['holder']) for r in result)
    for row in result:
        row['identity_ambiguous'] = identities[row['ticker'], row['holder']] != 1
    return result


def compare_one(current: list[dict[str, Any]], previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exact unique disclosed names only; disappearance is a disclosure exit."""
    now = {(r['ticker'], r['holder']): r for r in current if not r['identity_ambiguous']}
    old = {(r['ticker'], r['holder']): r for r in previous if not r['identity_ambiguous']}
    ambiguous = {(r['ticker'], r['holder']) for r in current + previous if r['identity_ambiguous']}
    changes = []
    for key in sorted(now.keys() | old.keys()):
        if key in ambiguous:
            continue
        a, b = now.get(key), old.get(key)
        if a and b and a['shares'] == b['shares'] and math.isclose(a['percentage'], b['percentage'], rel_tol=0, abs_tol=1e-9):
            continue
        changes.append(dict(ticker=key[0], holder=key[1], kind='Disclosure entry' if not b else 'Disclosure exit' if not a else 'Increase' if a['shares'] > b['shares'] else 'Decrease' if a['shares'] < b['shares'] else 'Percentage change',
                            current_shares=a['shares'] if a else None, previous_shares=b['shares'] if b else None,
                            current_percentage=a['percentage'] if a else None, previous_percentage=b['percentage'] if b else None,
                            delta_shares=a['shares'] - b['shares'] if a and b else None))
    return changes


def load_rows(path: Path) -> list[list[Any]]:
    import openpyxl
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        sheet.reset_dimensions()
        return [list(r) for r in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def read_one(path: Path, *, as_of: str) -> list[dict[str, Any]]:
    rows = load_rows(path)
    header = next((i for i, row in enumerate(rows) if tuple(row[:12]) == ONE_HEADERS), None)
    if header is None:
        raise ValueError('unrecognized 1% register header')
    return normalize_one((dict(zip(ONE_HEADERS, r)) for r in rows[header + 1:] if r and r[0] is not None), as_of=as_of)


def read_five(path: Path, *, as_of: str, previous_as_of: str) -> list[dict[str, Any]]:
    rows = load_rows(path)
    if len(rows) < 5 or rows[2][1] != 'Kode Efek' or rows[3][15] != 'Saham Gabungan Per Investor':
        raise ValueError('unrecognized 5% register header')
    # Verify the dated column labels rather than trusting the operator's dates.
    for idx, expected in ((11, previous_as_of), (14, as_of)):
        label = text(rows[2][idx]).split('Per ')[-1].title()
        if datetime.strptime(label, '%d-%b-%Y').date().isoformat() != expected:
            raise ValueError('5% register date mismatch')
    return normalize_five(rows[4:], as_of=as_of, previous_as_of=previous_as_of)


def source(path: Path, url: str, as_of: str) -> dict[str, str]:
    return dict(filename=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), url=url, as_of=as_of, publisher='IDX / KSEI')
