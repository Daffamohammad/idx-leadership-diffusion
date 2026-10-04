"""Read the dated rupiah NET FOREIGN card, preserving PDF rounding precision."""
from __future__ import annotations
from datetime import datetime
import re
from typing import Any


def parse_daily_flow(page_one: str, page_two: str, *, expected_date: str) -> dict[str, Any]:
    date_match = re.search(r'(?:Monday|Tuesday|Wednesday|Thursday|Friday), (\d{2} [A-Za-z]+ \d{4})', page_one)
    if not date_match or datetime.strptime(date_match[1], '%d %B %Y').date().isoformat() != expected_date:
        raise ValueError('daily PDF date mismatch')
    card = re.search(r'NET FOREIGN FUNDAMENTAL\s*\n([+-]?[\d,]+\.\d{2})\s+([+-]?[\d,]+\.\d{2})\s*\nMarket PER Market PBV\s*\nToday YTD\s*\n\(billion IDR\) \(billion IDR\)', page_two)
    if not card:
        raise ValueError('unrecognized NET FOREIGN card layout or units')
    daily, ytd = (round(float(v.replace(',', '')) * 1_000_000_000) for v in card.groups())
    directions = re.search(r'\(billion IDR\) \(billion IDR\).*?\n(Net (?:Buy|Sell)) (Net (?:Buy|Sell))', page_two, re.S)
    if not directions or any((v < 0) != (d == 'Net Sell') for v, d in zip((daily, ytd), directions.groups())):
        raise ValueError('NET FOREIGN sign/direction mismatch')
    return dict(as_of=expected_date, net_foreign_value_idr=daily, ytd_net_foreign_value_idr=ytd, precision_idr=10_000_000)


def validate_continuity(rows: list[dict[str, Any]], sessions: list[str]) -> None:
    dates = [r['as_of'] for r in rows]
    expected = [d for d in sessions if dates[0] <= d <= dates[-1]] if dates else []
    if not rows or dates != sorted(set(dates)) or dates != expected:
        raise ValueError('missing or duplicate foreign-flow sessions')
    for old, new in zip(rows, rows[1:]):
        # Three independently rounded values have an aggregate error <= 15m IDR.
        if abs(new['ytd_net_foreign_value_idr'] - old['ytd_net_foreign_value_idr'] - new['net_foreign_value_idr']) > 15_000_001:
            raise ValueError(f'foreign-flow YTD discontinuity: {new["as_of"]}')
