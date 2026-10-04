"""Hermetic regressions for official ownership, flow and market-display contracts."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pandas as pd
import pytest
from idx_leadership.providers.idx_ownership import normalize_one, normalize_five, compare_one
from idx_leadership.providers.idx_flow_history import parse_daily_flow, validate_continuity
from idx_leadership.data.market_workspace import index_contributions, build_workspace
from scripts.prepare_market_catalogs import build_catalogs
from scripts.publish_market_workspace import publish


def one(holder='PARENT', shares=200, pct=20, code='TEST', stamp='2026-09-30'):
    return dict(DATE=stamp,SHARE_CODE=code,ISSUER_NAME='Test Issuer',INVESTOR_NAME=holder,INVESTOR_CLASSIFICATION='Corporate',LOCAL_FOREIGN='L',NATIONALITY=None,DOMICILE=None,HOLDINGS_SCRIPLESS=shares-10,HOLDINGS_SCRIP=10,TOTAL_HOLDING_SHARES=shares,PERCENTAGE=pct)


def test_ownership_reconciles_certificated_and_scripless_and_keeps_ambiguous_names():
    rows=normalize_one([one(),one(shares=300)],as_of='2026-09-30')
    assert all(r['identity_ambiguous'] for r in rows)
    assert [r['shares'] for r in rows]==[200,300]
    assert compare_one(rows,normalize_one([one(stamp='2026-08-31')],as_of='2026-08-31'))==[]
    broken=one();broken['HOLDINGS_SCRIP']=100
    with pytest.raises(ValueError,match='totals'):normalize_one([broken],as_of='2026-09-30')
    with pytest.raises(ValueError,match='date mismatch'):normalize_one([one(stamp='2026-08-31')],as_of='2026-09-30')


def five_rows():
    first=[1,'TEST','Issuer','Custodian','Parent','Account','PRIVATE ADDRESS',None,None,None,'L','40','100','10','50','120','12',10]
    other=[None,'TEST',None,'Other custodian',None,'Another account','PRIVATE ADDRESS',None,None,None,'L','60',None,None,'70',None,None,10]
    return [first,other]


def test_five_percent_uses_investor_total_once_and_never_exports_account_or_address():
    rows=normalize_five(five_rows(),as_of='2026-10-01',previous_as_of='2026-09-30')
    assert len(rows)==1 and rows[0]['shares']==120 and rows[0]['account_count']==2
    assert rows[0]['account_totals_reconciled'] is True
    assert 'PRIVATE ADDRESS' not in json.dumps(rows) and 'Another account' not in json.dumps(rows)
    repeated=five_rows();repeated[1][15]='120';repeated[1][16]='12'
    assert normalize_five(repeated,as_of='2026-10-01',previous_as_of='2026-09-30')[0]['shares']==120
    repeated[1][15]='121'
    with pytest.raises(ValueError,match='conflicting'):normalize_five(repeated,as_of='2026-10-01',previous_as_of='2026-09-30')


def test_account_discrepancy_flag_does_not_invent_aggregate_or_previous_position():
    source=five_rows();source[0][12:14]=['-','-'];source[0][11]='-';source[1][11]='-';source[1][14]=1.7
    row=normalize_five(source,as_of='2026-10-01',previous_as_of='2026-09-30')[0]
    assert row['shares']==120 and row['account_totals_reconciled'] is False
    assert row['previous_shares'] is None and row['previous_percentage'] is None
    source[0][1]=True;source[1][1]=True
    assert normalize_five(source,as_of='2026-10-01',previous_as_of='2026-09-30')[0]['ticker']=='TRUE'


def test_disclosure_crossings_leave_missing_amounts_unreported():
    current=normalize_one([one(holder='NEW'),one(holder='SAME',shares=400)],as_of='2026-09-30')
    previous=normalize_one([one(holder='EXIT',stamp='2026-08-31'),one(holder='SAME',stamp='2026-08-31')],as_of='2026-08-31')
    changes={r['holder']:r for r in compare_one(current,previous)}
    assert changes['NEW']['kind']=='Disclosure entry' and changes['NEW']['delta_shares'] is None and changes['NEW']['previous_shares'] is None
    assert changes['EXIT']['kind']=='Disclosure exit' and changes['EXIT']['current_shares'] is None
    assert changes['SAME']['delta_shares']==200


PAGE_ONE='IDX DAILY STATISTICS\nFriday, 02 October 2026\n'
PAGE_TWO='NET FOREIGN FUNDAMENTAL\n-1,272.93 -82,553.51\nMarket PER Market PBV\nToday YTD\n(billion IDR) (billion IDR) (x) (x)\nNet Sell Net Sell\n'


def test_daily_pdf_preserves_rupiah_units_date_and_direction():
    row=parse_daily_flow(PAGE_ONE,PAGE_TWO,expected_date='2026-10-02')
    assert row['net_foreign_value_idr']==-1_272_930_000_000
    for bad in [PAGE_TWO.replace('billion IDR','million USD'),PAGE_TWO.replace('Net Sell Net Sell','Net Buy Net Sell')]:
        with pytest.raises(ValueError):parse_daily_flow(PAGE_ONE,bad,expected_date='2026-10-02')
    with pytest.raises(ValueError,match='date'):parse_daily_flow(PAGE_ONE,PAGE_TWO,expected_date='2026-10-01')


def test_flow_continuity_rejects_gaps_duplicates_and_ytd_breaks():
    rows=[dict(as_of='2026-10-01',net_foreign_value_idr=20_000_000,ytd_net_foreign_value_idr=100_000_000),dict(as_of='2026-10-02',net_foreign_value_idr=-20_000_000,ytd_net_foreign_value_idr=80_000_000)]
    validate_continuity(rows,['2026-10-01','2026-10-02'])
    with pytest.raises(ValueError,match='missing'):validate_continuity([rows[0],dict(rows[1],as_of='2026-10-03')],['2026-10-01','2026-10-02','2026-10-03'])
    duplicate=rows+rows[-1:]
    with pytest.raises(ValueError,match='duplicate'):validate_continuity(duplicate,['2026-10-01','2026-10-02'])
    broken=copy.deepcopy(rows);broken[1]['ytd_net_foreign_value_idr']=100_000_000
    with pytest.raises(ValueError,match='discontinuity'):validate_continuity(broken,['2026-10-01','2026-10-02'])


def stock(**kw):
    result=dict(ticker='TEST.JK',company_name='Test',weight_for_index=10.,close=110.,previous_close=100.,return_1d=10.,analysis_requested=True,market_cap=1100.)
    result.update(kw);return result


def test_index_points_reconcile_and_fail_closed_on_missing_weights_or_divisor_change():
    rows=[stock(),stock(ticker='ZERO.JK',weight_for_index=0.)]
    result=index_contributions(rows,previous=1000.,close=1100.)
    assert result['status']=='RECONCILED' and len(result['rows'])==1 and result['rows'][0]['points']==100.
    for changed in [stock(weight_for_index=None),stock(close=None)]:
        assert index_contributions([changed],previous=1000.,close=1100.)['rows']==[]
    assert index_contributions(rows,previous=1000.,close=1101.)['status']=='UNAVAILABLE'


def test_weekly_return_requires_every_session_and_eligibility_does_not_follow_price_presence():
    dates=pd.bdate_range('2026-09-25','2026-10-02').date
    benchmark=pd.DataFrame({'date':dates,'close':[100.]*6})
    prices=pd.DataFrame({'ticker':['TEST.JK']*6,'date':dates,'adjusted_close':[100.,101.,102.,103.,104.,110.]})
    daily=dict(as_of='2026-10-02',records=[stock()],breadth={},sources={})
    result=build_workspace(daily,prices,benchmark,eligible=set(),gaps={},edges=[])
    assert result['records'][0]['return_1w']==pytest.approx(10.) and result['records'][0]['signal_eligible'] is False
    missing=build_workspace(daily,prices.drop(index=2),benchmark,eligible={'TEST.JK'},gaps={},edges=[])
    assert missing['records'][0]['return_1w'] is None and missing['records'][0]['signal_eligible'] is True


def test_catalog_requires_exact_owner_name_and_dated_activity_not_shared_directors():
    universe={'universe':[{'ticker':'TEST.JK','subindustry':'Coal Production','classification_as_of':'2026-08-27'},{'ticker':'ROOT.JK'}]}
    ownership={'as_of':'2026-09-30','sources':[{'url':'https://www.idx.co.id/source.xlsx'}],'registers':{'one':normalize_one([one()],as_of='2026-09-30')}}
    rules={'version':'market-test','as_of':'2026-09-30','minimum_percentage':20,'groups':[{'id':'GROUP','name':'Group','parent':'ROOT','owners':['PARENT']}], 'control_evidence':[]}
    konglo,themes,edges=build_catalogs(universe,ownership,rules)
    assert len(konglo['memberships'])==2 and edges[0]['relationship']=='Disclosed shareholding' and edges[0]['control_source'] is None
    assert themes['memberships'][0]['taxonomy_group_name']=='Coal Production'
    rules['groups'][0]['owners']=['Parent']
    assert build_catalogs(universe,ownership,rules)[0]['memberships']==[]


def test_publication_rejects_future_or_broken_data_without_touching_index(tmp_path: Path):
    current=normalize_one([one()],as_of='2026-09-30');five=normalize_five(five_rows(),as_of='2026-10-01',previous_as_of='2026-09-30')
    market=dict(schema_version='market-workspace-v1',snapshot_id='snap_test_2026-10-02',as_of='2026-10-02',benchmark=[{'date':'2026-10-01'},{'date':'2026-10-02'}],ownership_edges=[])
    ownership=dict(schema_version='idx-ownership-v1',as_of='2026-09-30',previous_as_of='2026-08-31',five_as_of='2026-10-01',registers={'one':current,'five':five})
    foreign=dict(schema_version='idx-foreign-history-v1',as_of='2026-10-02',validation={'session_continuity':True,'ytd_continuity':True},daily=[dict(as_of='2026-10-01',net_foreign_value_idr=1,ytd_net_foreign_value_idr=1),dict(as_of='2026-10-02',net_foreign_value_idr=1,ytd_net_foreign_value_idr=2)])
    paths=[]
    for name,payload in [('market',market),('ownership',ownership),('foreign',foreign)]:
        path=tmp_path/f'{name}.json';path.write_text(json.dumps(payload));paths.append(path)
    out=tmp_path/'served';out.mkdir();index=out/'index.json';index.write_bytes(b'previous index')
    ownership['five_as_of']='2026-10-03';paths[1].write_text(json.dumps(ownership))
    with pytest.raises(ValueError,match='incompatible'):publish(*paths,out)
    assert index.read_bytes()==b'previous index' and list(out.iterdir())==[index]
    ownership['five_as_of']='2026-10-01';paths[1].write_text(json.dumps(ownership))
    result=publish(*paths,out)
    assert result['snapshot_id']=='snap_test_2026-10-02' and len(result['assets'])==3
    import hashlib
    for asset in result['assets'].values():assert hashlib.sha256((out/Path(asset['path']).name).read_bytes()).hexdigest()==asset['sha256']


def test_taxonomy_eligibility_requires_snapshot_identity_and_exact_cohort(tmp_path):
    import hashlib
    from scripts.build_taxonomy_views import _workspace_eligible
    path=tmp_path/'workspace.json'
    payload=dict(snapshot_id='market',as_of='2026-10-02',records=[dict(ticker='A.JK',signal_eligible=True),dict(ticker='B.JK',signal_eligible=False)])
    path.write_text(json.dumps(payload))
    entry=dict(as_of='2026-10-02',eligible_ticker_set_hash=hashlib.sha256(json.dumps(['A.JK']).encode()).hexdigest()[:16])
    assert _workspace_eligible(path,'market',entry)=={'A.JK'}
    with pytest.raises(ValueError,match='identity'): _workspace_eligible(path,'older',entry)
    payload['records'][1]['signal_eligible']=True;path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='cohort'): _workspace_eligible(path,'market',entry)


def test_published_workspace_assets_match_active_snapshot_and_hashes():
    import hashlib
    from idx_leadership.utils import project_root
    public=project_root()/'app/web/public'
    index=json.loads((public/'market/index.json').read_text())
    snapshot=json.loads((public/'snapshots'/f'{index["snapshot_id"]}.json').read_text())
    assert index['as_of']==snapshot['as_of']
    for key,asset in index['assets'].items():
        content=(public/asset['path'].lstrip('/')).read_bytes()
        assert hashlib.sha256(content).hexdigest()==asset['sha256']
        payload=json.loads(content)
        assert payload['as_of']==asset['as_of']<=index['as_of']
        assert payload['schema_version']==asset['schema_version']
        if key=='market':
            eligible=sorted(r['ticker'] for r in payload['records'] if r['signal_eligible'])
            cohort=hashlib.sha256(json.dumps(eligible).encode()).hexdigest()[:16]
            entry=snapshot['manifest']['entries'][0]
            assert cohort==entry['eligible_ticker_set_hash']
            assert len(payload['records'])==963
            assert len(eligible)==760
            for view in snapshot['taxonomy_views'].values():
                if view.get('taxonomy_id') in {'konglo','themes'}:
                    assert view['calculation']['eligible_ticker_set_hash']==cohort
                    assert view['calculation']['minimum_eligible_constituents']==5
        if key=='ownership':
            assert payload['coverage']['five_unreconciled_account_blocks']==sum(r['account_totals_reconciled'] is False for r in payload['registers']['five'])
            assert 'PRIVATE ADDRESS' not in content.decode()


def test_monthly_comparison_ignores_excel_percentage_roundoff_but_keeps_real_changes():
    current=normalize_one([one(pct=1.1500000000000001)],as_of='2026-09-30')
    previous=normalize_one([one(pct=1.15,stamp='2026-08-31')],as_of='2026-08-31')
    assert compare_one(current,previous)==[]
    current[0]['percentage']=1.16
    assert compare_one(current,previous)[0]['kind']=='Percentage change'
