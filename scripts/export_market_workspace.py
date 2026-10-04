"""Publish the whole-market workspace only from a current independently validated panel."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from idx_leadership.data.market_workspace import build_workspace
from scripts.validate_public_panel import _check_panel_integrity


def main() -> int:
    p=argparse.ArgumentParser()
    for key in ('daily','panel-dir','validation','snapshot-dir','edges','universe','out'):
        p.add_argument('--'+key,required=True)
    a=p.parse_args()
    try:
        root=Path(a.panel_dir);manifest=json.loads((root/'source_manifest.json').read_text());prices=pd.read_csv(root/'prices.csv');benchmark=pd.read_csv(root/'benchmark.csv')
        prices['date']=pd.to_datetime(prices['date']).dt.date;benchmark['date']=pd.to_datetime(benchmark['date']).dt.date
        validation=json.loads(Path(a.validation).read_text());daily=json.loads(Path(a.daily).read_text())
        integrity=_check_panel_integrity(prices,benchmark,manifest,root)
        if validation['status'] != 'PASS' or integrity['status'] != 'PASS' or validation['checks']['panel_integrity'] != integrity:
            raise ValueError('panel validation is missing, failed, or stale')
        snapshot=Path(a.snapshot_dir);entry=json.loads((snapshot/'manifest.json').read_text())['entries'][0]
        provenance=json.loads((snapshot/'panel_provenance.json').read_text())
        fingerprints={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('prices.csv','benchmark.csv')}
        if provenance['panel_files'] != fingerprints or entry['as_of'] != daily['as_of']:
            raise ValueError('snapshot/panel/official-day mismatch')
        from datetime import date
        from scripts.build_snapshot_chain import PanelCacheProvider
        from idx_leadership.providers.market_universe import build_market_universe
        provider=PanelCacheProvider(root,as_of=date.fromisoformat(daily['as_of']),universe_path=a.universe)
        if provenance['input_contracts']['universe_sha256'] != hashlib.sha256(Path(a.universe).read_bytes()).hexdigest():
            raise ValueError('snapshot/universe contract mismatch')
        diagnostics=manifest.get('diagnostics', {})
        gaps=dict(failed=[r['ticker'] if isinstance(r,dict) else r for r in diagnostics.get('failed_symbols',[])], quarantined=[r['ticker'] if isinstance(r,dict) else r for r in diagnostics.get('quarantined_symbols',[])])
        universe=build_market_universe(security_master_provider=provider,cross_section_provider=provider,as_of=date.fromisoformat(daily['as_of']),price_history=prices,acquisition_empties=set(gaps['failed']+gaps['quarantined']))
        eligible=set(universe.loc[universe['eligible'],'ticker'])
        cohort=hashlib.sha256(json.dumps(sorted(eligible)).encode()).hexdigest()[:16]
        if cohort != entry['eligible_ticker_set_hash']:
            raise ValueError('replayed eligibility cohort mismatch')
        payload=build_workspace(daily,prices,benchmark,eligible=eligible,gaps=gaps,edges=json.loads(Path(a.edges).read_text()))
        payload['snapshot_id']=snapshot.name
        payload['sources']['validated_panel'] = dict(files=fingerprints,validation_sha256=hashlib.sha256(Path(a.validation).read_bytes()).hexdigest())
        out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
        print(json.dumps(dict(records=len(payload['records']),weekly=sum(r['return_1w'] is not None for r in payload['records']),index_movers=payload['index_movers']['status'],coverage=payload['coverage'])))
        return 0
    except (OSError,ValueError,KeyError) as exc:
        print(f'EXPORT_REFUSED: {exc}');return 1

if __name__=='__main__':raise SystemExit(main())
