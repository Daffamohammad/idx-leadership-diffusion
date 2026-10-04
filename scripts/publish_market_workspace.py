"""Publish validated dated assets; index changes only after all contracts pass."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from idx_leadership.providers.idx_statistics import write_json_atomic
from idx_leadership.providers.idx_flow_history import validate_continuity


def publish(market_path: Path, ownership_path: Path, foreign_path: Path, out: Path) -> dict:
    inputs = {key: (path, json.loads(path.read_text())) for key, path in [('market',market_path),('ownership',ownership_path),('foreign',foreign_path)]}
    market = inputs['market'][1];ownership = inputs['ownership'][1];foreign = inputs['foreign'][1]
    as_of = market['as_of']
    if market['schema_version'] != 'market-workspace-v1' or ownership['schema_version'] != 'idx-ownership-v1' or foreign['schema_version'] != 'idx-foreign-history-v1':
        raise ValueError('workspace schema mismatch')
    if foreign['as_of'] != as_of or ownership['as_of'] > as_of or ownership['five_as_of'] > as_of or ownership['previous_as_of'] >= ownership['as_of']:
        raise ValueError('workspace release dates are incompatible')
    if not foreign['validation']['session_continuity'] or not foreign['validation']['ytd_continuity']:
        raise ValueError('foreign history is unvalidated')
    validate_continuity(foreign['daily'], [r['date'] for r in market['benchmark']])
    if not ownership['registers']['one'] or not ownership['registers']['five']:
        raise ValueError('ownership register is empty')
    for key in ('one','five'):
        expected_date = ownership['as_of'] if key == 'one' else ownership['five_as_of']
        if any(r['as_of'] != expected_date for r in ownership['registers'][key]):
            raise ValueError('ownership row release date mismatch')
    if any(e['as_of'] > as_of or (e.get('control_source') and e['control_source']['as_of'] > as_of) for e in market['ownership_edges']):
        raise ValueError('future ownership evidence')
    assets={}
    for key, (path,payload) in inputs.items():
        # Serialize before any mutation, rejecting nonfinite values in all assets.
        content=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
        name=f'{key}-{payload["as_of"]}.json'
        assets[key]=dict(path='/market/'+name,sha256=hashlib.sha256(content.encode()).hexdigest(),as_of=payload['as_of'],schema_version=payload['schema_version'])
        inputs[key]=(content,payload)
    index=dict(snapshot_id=market['snapshot_id'],as_of=as_of,assets=assets)
    out.mkdir(parents=True,exist_ok=True)
    for key,(content,payload) in inputs.items():
        target=out/Path(assets[key]['path']).name
        temporary=target.with_suffix('.json.tmp');temporary.write_text(content);temporary.replace(target)
    write_json_atomic(out/'index.json',index)
    return index


def main() -> int:
    p=argparse.ArgumentParser()
    for key in ('market','ownership','foreign','out'):
        p.add_argument('--'+key,required=True)
    a=p.parse_args()
    try:
        result=publish(Path(a.market),Path(a.ownership),Path(a.foreign),Path(a.out));print(json.dumps(result));return 0
    except (OSError,ValueError,KeyError) as exc:
        print(f'PUBLICATION_REFUSED: {exc}');return 1

if __name__=='__main__':raise SystemExit(main())
