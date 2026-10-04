"""Dated whole-market display observations, kept separate from signal eligibility."""
from __future__ import annotations
import math
from typing import Any
import pandas as pd


def index_contributions(records: list[dict[str, Any]], *, previous: float, close: float, tolerance: float = .001) -> dict[str, Any]:
    """Fixed official index-share quantities; fail closed on missing weights/prices or residual."""
    if not all(math.isfinite(v) and v > 0 for v in (previous, close)):
        return dict(status='UNAVAILABLE', rows=[], reason='Invalid benchmark levels')
    weighted = []
    for row in records:
        q = row.get('weight_for_index')
        if q is None or not math.isfinite(q) or q < 0:
            return dict(status='UNAVAILABLE', rows=[], reason='Index-share quantities incomplete')
        if q == 0:
            continue
        if any(row.get(k) is None or not math.isfinite(row[k]) or row[k] <= 0 for k in ('close', 'previous_close')):
            return dict(status='UNAVAILABLE', rows=[], reason='Weighted constituent prices incomplete')
        weighted.append(row)
    base = sum(r['weight_for_index'] * r['previous_close'] for r in weighted)
    if base <= 0:
        return dict(status='UNAVAILABLE', rows=[], reason='No index-share capitalization')
    rows = [dict(ticker=r['ticker'], company_name=r['company_name'], points=previous * r['weight_for_index'] * (r['close'] - r['previous_close']) / base, return_1d=r['return_1d']) for r in weighted]
    calculated = sum(r['points'] for r in rows)
    residual = calculated - (close - previous)
    if abs(residual) > tolerance:
        return dict(status='UNAVAILABLE', rows=[], reason='Contributions do not reconcile to the official index move', residual=residual)
    return dict(status='RECONCILED', rows=rows, calculated_change=calculated, official_change=close - previous, residual=residual, tolerance=tolerance,
                method='Previous IHSG × official index shares × (close − previous close) / sum(previous close × official index shares)',
                source='https://www.idx.co.id/en/products/index/', limitations='Calculated price contributions for this session only. Weight or divisor changes require a new reconciliation.')


def build_workspace(daily: dict, prices: pd.DataFrame, benchmark: pd.DataFrame, *, eligible: set[str], gaps: dict, edges: list) -> dict:
    as_of = daily['as_of']
    benchmark = benchmark.copy();benchmark['date'] = benchmark['date'].astype(str).str[:10]
    benchmark = benchmark[benchmark['date'] <= as_of].sort_values('date')
    if benchmark.empty or benchmark.iloc[-1]['date'] != as_of or benchmark['date'].duplicated().any():
        raise ValueError('benchmark date mismatch or duplicates')
    if not all(math.isfinite(v) and v > 0 for v in benchmark['close']):
        raise ValueError('invalid benchmark observation')
    sessions = benchmark['date'].tolist()
    weekly_dates = sessions[-6:]
    by_ticker = {ticker: frame.assign(date=frame['date'].astype(str).str[:10]).set_index('date') for ticker, frame in prices.groupby('ticker')}
    rows = []
    for raw in daily['records']:
        row = dict(raw)
        ticker = row['ticker']
        row['signal_eligible'] = ticker in eligible
        row['return_1w'] = None
        row['history_status'] = 'Validation quarantine' if ticker in gaps.get('quarantined', []) else 'Unavailable history' if ticker in gaps.get('failed', []) else 'Observed history' if ticker in by_ticker else 'Outside stock-history lane'
        frame = by_ticker.get(ticker)
        if frame is not None and len(weekly_dates) == 6 and all(d in frame.index for d in weekly_dates):
            values = frame.loc[weekly_dates, 'adjusted_close']
            if len(values) == 6 and all(math.isfinite(v) and v > 0 for v in values):
                row['return_1w'] = float(values.iloc[-1] / values.iloc[0] - 1) * 100
        rows.append(row)
    previous, close = map(float, benchmark['close'].iloc[-2:])
    return dict(schema_version='market-workspace-v1', as_of=as_of, records=rows, breadth=daily['breadth'], benchmark=[dict(date=r.date, close=float(r.close)) for r in benchmark.itertuples()],
                index_movers=index_contributions(rows, previous=previous, close=close), weekly_start=weekly_dates[0], weekly_end=as_of,
                ownership_edges=edges, sources=daily['sources'], coverage=dict(requested=sum(r['analysis_requested'] for r in rows), observed_histories=len(by_ticker), signal_eligible=len(eligible), gaps=gaps),
                limitations=['Market cap is official close × listed shares, not free-float market cap.', 'Daily is official close versus previous close; Weekly is the adjusted-price return over five IDX sessions.', 'Stock display coverage and analytical eligibility are separate. Unavailable returns are never zero.'])
