"""Produce explicitly versioned market lenses from dated classification/holdings evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import yaml


def build_catalogs(universe: dict, ownership: dict, rules: dict) -> tuple[dict, dict, list]:
    if rules['as_of'] != ownership['as_of']:
        raise ValueError('holdings rule date mismatch')
    tickers = {r['ticker'].removesuffix('.JK') for r in universe['universe']}
    source = ownership['sources'][0]['url']
    controls = {(r['owner'], r['ticker']): r for r in rules.get('control_evidence', [])}
    konglo_members = []; edges = []
    for group in rules['groups']:
        positions = [r for r in ownership['registers']['one'] if r['holder'] in group['owners'] and r['percentage'] >= rules['minimum_percentage'] and not r['identity_ambiguous'] and r['ticker'] in tickers]
        seen = set()
        for row in positions:
            control = controls.get((row['holder'], row['ticker']))
            edge = dict(group_id=group['id'], group_name=group['name'], holder=row['holder'], ticker=row['ticker'], percentage=row['percentage'],
                        as_of=ownership['as_of'], source=source, relationship=control['relationship'] if control else 'Disclosed shareholding', control_source=control)
            edges.append(edge)
            if row['ticker'] not in seen:
                konglo_members.append(dict(ticker=row['ticker'] + '.JK', taxonomy_group_id=group['id'], taxonomy_group_name=group['name'], source=source,
                                          source_as_of=ownership['as_of'], confidence=1., relationship=edge['relationship']))
                seen.add(row['ticker'])
        parent = group.get('parent')
        if positions and parent and parent in tickers and parent not in seen:
            konglo_members.append(dict(ticker=parent + '.JK', taxonomy_group_id=group['id'], taxonomy_group_name=group['name'], source=source,
                                      source_as_of=ownership['as_of'], confidence=1., relationship='Named listed parent; does not imply self-ownership'))
    theme_members = []
    for row in universe['universe']:
        activity = row.get('subindustry')
        if not activity or not row.get('classification_as_of'):
            continue
        theme_members.append(dict(ticker=row['ticker'], taxonomy_group_id='ACTIVITY_' + re.sub(r'[^A-Z0-9]+', '_', activity.upper()).strip('_'),
                                  taxonomy_group_name=activity, confidence=1., source='Captured issuer business-activity classification: ' + activity,
                                  source_as_of=row['classification_as_of'], relationship='Business activity; exact captured subindustry match'))
    def taxonomy(kind, members, version, as_of, description):
        return dict(taxonomy_id=kind.lower(), taxonomy_name=description, taxonomy_version=version, taxonomy_kind=kind, source_kind='ANALYST_DEFINED',
                    source_as_of=as_of, membership_policy='MULTI', provider_mode='PUBLIC_PROTOTYPE', memberships=members)
    return (taxonomy('KONGLO', konglo_members, rules['version'], ownership['as_of'], 'Documented corporate and named-holder portfolios'),
            taxonomy('THEMES', theme_members, 'market-business-activities-v1', '2026-08-27', 'Business-activity themes: exact captured subindustry inclusion'), edges)


def main() -> int:
    p=argparse.ArgumentParser()
    for key in ('universe','ownership','rules','out-dir','edges-out'):
        p.add_argument('--'+key,required=True)
    a=p.parse_args()
    try:
        universe=yaml.safe_load(Path(a.universe).read_text());ownership=json.loads(Path(a.ownership).read_text());rules=yaml.safe_load(Path(a.rules).read_text())
        konglo,themes,edges=build_catalogs(universe,ownership,rules)
        provenance={key:hashlib.sha256(Path(getattr(a,key)).read_bytes()).hexdigest() for key in ('universe','ownership','rules')}
        for name,payload in (('konglo',konglo),('themes',themes)):
            payload['source_hashes']=provenance
            out=Path(a.out_dir)/f'{name}.yaml';out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(yaml.safe_dump(payload,sort_keys=False,allow_unicode=True))
        out=Path(a.edges_out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(edges,separators=(',',':'))+'\n')
        print(json.dumps(dict(konglo_groups=len({r['taxonomy_group_id'] for r in konglo['memberships']}),konglo_memberships=len(konglo['memberships']),theme_groups=len({r['taxonomy_group_id'] for r in themes['memberships']}),theme_memberships=len(themes['memberships']),edges=len(edges))))
        return 0
    except (OSError,ValueError,KeyError) as exc:
        print(f'SOURCE_UNAVAILABLE: {exc}');return 1

if __name__=='__main__':raise SystemExit(main())
