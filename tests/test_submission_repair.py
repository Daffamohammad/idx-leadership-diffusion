"""Regression checks for the submission UI and evidence-backed readiness gate."""
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

import pytest

from scripts import verify_sectors_readiness as readiness

ROOT = Path(__file__).resolve().parents[1]


def bun(code):
    result = subprocess.run(["bun", "-e", code], cwd=ROOT, text=True, capture_output=True, timeout=30, check=True)
    return json.loads(result.stdout)


def test_rotation_domains_include_current_points_and_missing_observations_break_trails():
    result = bun('''
      import {rotationPlotRanges, rotationTrailSegments} from "./app/web/src/data/mapGeometry.ts";
      const points = [{x:25.5,y:-7,history:[]},{x:0,y:0,history:[{x:null,y:100},{x:NaN,y:4}]}];
      const trail = [{x:1,y:2,date:"a"},{x:2,y:3,date:"b"},{x:null,y:0,date:"gap"},{x:4,y:5,date:"c"},{x:5,y:6,date:"d"}];
      console.log(JSON.stringify({ranges:rotationPlotRanges(points),segments:rotationTrailSegments(trail).map(s=>s.map(p=>p.date)),gap:trail[2]}));
    ''')
    assert result["ranges"]["x"][0] < 0 < 25.5 < result["ranges"]["x"][1]
    assert result["ranges"]["y"][0] < -7 < 0 < result["ranges"]["y"][1] < 100
    assert result["segments"] == [["a", "b"], ["c", "d"]]
    assert result["gap"]["x"] is None


def test_parent_loading_errors_and_new_release_never_look_like_absence_or_cached_success():
    result = bun('''
      import {currentWorkspaceState} from "./app/web/src/data/marketWorkspace.ts";
      const loaded={data:{value:1},error:null,loading:false,requestKey:"old"};
      const absent={data:null,error:null,loading:false,requestKey:null};
      console.log(JSON.stringify({
        loading:currentWorkspaceState({loading:true,error:null},absent,null),
        error:currentWorkspaceState({loading:false,error:"Failed to fetch"},loaded,"old"),
        absent:currentWorkspaceState({loading:false,error:null},absent,null),
        changed:currentWorkspaceState({loading:false,error:null},loaded,"new"),
        loaded:currentWorkspaceState({loading:false,error:null},loaded,"old")
      }));
    ''')
    assert result["loading"]["loading"] is True
    assert result["error"]["error"] == "Failed to fetch" and result["error"]["data"] is None
    assert result["absent"]["loading"] is False and result["absent"]["error"] is None
    assert result["changed"]["loading"] is True and result["changed"]["data"] is None
    assert result["loaded"]["data"] == {"value": 1}


def test_loading_error_and_absent_markup_have_distinct_states():
    result = bun('''
      import React from "./app/web/node_modules/react/index.js";
      import {renderToStaticMarkup} from "./app/web/node_modules/react-dom/server.js";
      import {AssetLoadState} from "./app/web/src/components/AssetLoadState.tsx";
      const render=(loading,error)=>renderToStaticMarkup(React.createElement(AssetLoadState,{label:"Breadth",loading,error,absentMessage:"No breadth recording included"}));
      console.log(JSON.stringify({loading:render(true,null),error:render(false,"Failed to fetch"),corrupt:render(false,"Release asset integrity check failed"),absent:render(false,null)}));
    ''')
    assert 'role="status"' in result["loading"] and "Loading and verifying" in result["loading"]
    assert 'role="alert"' in result["error"] and "Retry" in result["error"]
    assert "No breadth recording" not in result["error"]
    assert "integrity check failed" in result["corrupt"]
    assert "No breadth recording" in result["absent"] and "Retry" not in result["absent"]


def test_external_heatmap_uses_its_own_document_and_preserves_daily_and_ytd_configuration():
    result = bun('''
      import React from "./app/web/node_modules/react/index.js";
      import {renderToStaticMarkup} from "./app/web/node_modules/react-dom/server.js";
      import Heatmap from "./app/web/src/components/TradingViewStockHeatmap.tsx";
      console.log(JSON.stringify(["daily","ytd"].map(color=>renderToStaticMarkup(React.createElement(Heatmap,{color})))));
    ''')
    class EmbedParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.frames, self.scripts = [], []
        def handle_starttag(self, tag, attrs):
            if tag == "iframe": self.frames.append(dict(attrs))
            if tag == "script": self.scripts.append(dict(attrs))
    for markup, color in zip(result, ("change", "Perf.YTD"), strict=True):
        page = EmbedParser()
        page.feed(markup)
        assert not page.scripts and len(page.frames) == 1
        frame = page.frames[0]
        assert frame["title"] == "TradingView Indonesian stock heatmap"
        assert '"blockColor":"' + color + '"' in frame["srcdoc"]
        assert '"dataSource":"AllID"' in frame["srcdoc"]
        embedded = EmbedParser()
        embedded.feed(frame["srcdoc"])
        assert len(embedded.scripts) == 1
        assert embedded.scripts[0]["src"].endswith("embed-widget-stock-heatmap.js")


def test_verified_asset_failed_fetch_and_corrupted_digest_can_retry_without_provider_calls():
    result = bun('''
      import {loadActiveRelease,loadReleaseAsset,loadReleaseAdditionalFile} from "./app/web/src/data/release.ts";
      const root="./app/web/public";
      const pointer=await Bun.file(root+"/releases/active.json").json();
      const manifest=await Bun.file(root+"/releases/"+pointer.active.release_id+"/manifest.json").json();
      const marketPath=manifest.families.market.path;
      let mode="normal", attempts=0;
      globalThis.fetch=async (path)=>{
        if (!String(path).startsWith("/releases/")) throw new Error("Unexpected provider request");
        const file=Bun.file(root+path);
        if(String(path).endsWith("/"+marketPath)) {
          attempts++;
          if(mode==="failed") throw new Error("Failed to fetch");
          if(mode==="corrupt") return new Response("{}",{headers:{"content-type":"application/json"}});
        }
        return new Response(await file.arrayBuffer(),{headers:{"content-type":"application/json"}});
      };
      const release=await loadActiveRelease();
      mode="failed";let error="";try{await loadReleaseAsset(release,release.manifest.families.market);}catch(e){error=e.message;}
      mode="corrupt";let corrupt="";try{await loadReleaseAsset(release,release.manifest.families.market);}catch(e){corrupt=e.message;}
      mode="normal";const recovered=await loadReleaseAsset(release,release.manifest.families.market);
      const absent=await loadReleaseAdditionalFile(release,"not_in_manifest");
      console.log(JSON.stringify({error,corrupt,attempts,as_of:recovered.as_of,absent}));
    ''')
    assert result["error"] == "Failed to fetch"
    assert "integrity check failed" in result["corrupt"]
    assert result["attempts"] == 3 and result["as_of"] == "2026-10-02"
    assert result["absent"] is None


def test_weekly_rows_use_released_cohorts_and_preserve_missing_comparisons():
    result = bun('''
      import {sectorWeeklyComparison,weeklySectorReadings,weightedGroupBreadth} from "./app/web/src/data/adapter.ts";
      const pointer=await Bun.file("./app/web/public/releases/active.json").json();
      const root="./app/web/public/releases/"+pointer.active.release_id;
      const manifest=await Bun.file(root+"/manifest.json").json();
      const entry=manifest.additional_files.find(f=>f.file_id==="historical_comparison");
      const asset=await Bun.file(root+"/"+entry.path).json();
      const comparison=sectorWeeklyComparison(asset);
      const rows=weeklySectorReadings(comparison,[]);
      const latest=comparison.weekly.at(-1).groups;
      const sourceMatches=latest.every(g=>{const p=asset.taxonomies.SECTOR.groups[g.group_id].weekly.at(-1);return g.diffusion===p.diffusion_v2 && g.excess_return_60d===p.excess_return_60d && g.breadth_pct===p.breadth_pct;});
      const matches=rows.every(r=>{const g=latest.find(g=>g.group_id===r.id);return r.excess20d===g.excess_return_20d && r.breadth===g.breadth_pct && r.eligibleConstituents===g.cohort_count && r.diffusionV2===g.diffusion && (g.breadth_change_pp===null?r.prevBreadth===undefined:Math.abs(r.breadth-r.prevBreadth-g.breadth_change_pp)<1e-9);});
      const missing=structuredClone(comparison);missing.weekly=[missing.weekly.at(-1)];
      const changed=structuredClone(comparison);changed.weekly.at(-2).groups[0].cohort_count++;
      const changedId=changed.weekly.at(-2).groups[0].group_id;
      const different=weeklySectorReadings(changed,[]).find(r=>r.id===changedId);
      console.log(JSON.stringify({rows:rows.length,matches,sourceMatches,missing:weeklySectorReadings(missing,[]).every(r=>r.prevBreadth===undefined && r.diffusion==="UNCONFIRMED"),different,
        mean:weightedGroupBreadth([{breadth_pct:100,cohort_count:5},{breadth_pct:0,cohort_count:15},{breadth_pct:null,cohort_count:100}]),empty:weightedGroupBreadth([{breadth_pct:null,cohort_count:5}])}));
    ''')
    assert result["rows"] == 11 and result["matches"] is True and result["sourceMatches"] is True
    assert result["missing"] is True
    assert result["different"]["diffusion"] == "UNCONFIRMED" and "prevBreadth" not in result["different"]
    assert result["mean"] == 25 and result["empty"] is None


@pytest.fixture
def browser_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    (tmp_path / "app/web").mkdir(parents=True)
    (tmp_path / "app/web/index.html").write_text("verified source")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()
    git("init", "-q")
    git("add", "app/web/index.html")
    git("-c", "user.name=QA", "-c", "user.email=qa@example.invalid", "commit", "-qm", "source")
    commit = git("rev-parse", "HEAD")
    screenshots = []
    # Small PNG fixtures test evidence validation; they are not real browser evidence.
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2ZAAAAABJRU5ErkJggg==")
    for viewport in ("1036x799", "1369x799", "1440x900", "390x844"):
        image = tmp_path / f"docs/{viewport}.png"
        image.parent.mkdir(exist_ok=True)
        image.write_bytes(png)
        screenshots.append({"path":str(image.relative_to(tmp_path)),"sha256":hashlib.sha256(png).hexdigest(),"viewport":viewport})
    metrics = {"ranking_rows":11,"sectors_map_marks":9}
    receipt = {"schema_version":"diffusion-browser-qa-v1","status":"PASS","source_commit":commit,
               "release_id":"rel-test","manifest_sha256":"a"*64,"metrics":metrics,
               "checks":{key:{"status":"PASS","observed":{"fixture":True}} for key in readiness.REQUIRED_BROWSER_CHECKS},
               "screenshots":screenshots,"unexpected_console_errors":0,"unexpected_data_request_failures":0,"sectors_provider_requests":0}
    receipt["checks"]["navigation_smoke"]["observed"] = {"routes":list(readiness.REQUIRED_ROUTES)}
    path = tmp_path / "docs/browser.json"
    def verify():
        path.write_text(json.dumps(receipt))
        return readiness.verify_browser_receipt(path,release_id="rel-test",manifest_sha256="a"*64,expected_metrics=metrics)
    return receipt, verify, tmp_path, git


def test_browser_receipt_accepts_exact_source_and_later_documentation_only_commits(browser_receipt):
    receipt, verify, root, git = browser_receipt
    assert verify()["source_commit"] == receipt["source_commit"]
    git("add", "docs")
    git("-c", "user.name=QA", "-c", "user.email=qa@example.invalid", "commit", "-qm", "evidence")
    assert verify()["status"] == "PASS"


@pytest.mark.parametrize("failure", ["failed", "missing_check", "no_observations", "different_release", "wrong_metrics", "console", "missing_screenshot", "bad_hash", "missing_route", "changed_source", "untracked_source"])
def test_browser_receipt_rejects_incomplete_stale_or_failed_evidence(browser_receipt, failure):
    receipt, verify, root, _ = browser_receipt
    if failure == "failed": receipt["checks"]["overview"]["status"] = "FAIL"
    elif failure == "missing_check": del receipt["checks"]["fetch_error_retry"]
    elif failure == "no_observations": receipt["checks"]["context_map"]["observed"] = {}
    elif failure == "different_release": receipt["release_id"] = "rel-other"
    elif failure == "wrong_metrics": receipt["metrics"] = {"ranking_rows":11,"sectors_map_marks":0}
    elif failure == "console": receipt["unexpected_console_errors"] = 1
    elif failure == "missing_screenshot": (root / receipt["screenshots"][0]["path"]).unlink()
    elif failure == "bad_hash": receipt["screenshots"][0]["sha256"] = "0"*64
    elif failure == "missing_route": receipt["checks"]["navigation_smoke"]["observed"]["routes"].remove("/sources")
    elif failure == "changed_source": (root / "app/web/index.html").write_text("untested code")
    elif failure == "untracked_source": (root / "app/web/extra.ts").write_text("untested code")
    with pytest.raises(ValueError): verify()


def test_readiness_does_not_overwrite_historical_receipts(tmp_path):
    path = tmp_path / "readiness.json"
    path.write_text("historical")
    with pytest.raises(ValueError, match="already exists"):
        readiness._write(path,{"status":"PASS"})
    assert path.read_text() == "historical"


def test_ownership_comparison_preserves_unknown_prior_values_and_population_boundaries():
    result = bun('''
      import {ownershipComparisons} from "./app/web/src/data/ownershipComparison.ts";
      const row=(holder,shares,percentage,extra={})=>({ticker:"TEST",holder,shares,percentage,...extra});
      const data={registers:{one:[row("A",120,12),row("ENTRY",1,1),row("AMB",50,5,{identity_ambiguous:true})],previous_one:[row("A",100,10),row("EXIT",5,2),row("AMB",40,4)],five:[row("A",120,12,{previous_shares:100}),row("UNKNOWN",2,6)]}};
      console.log(JSON.stringify({one:ownershipComparisons(data,false),five:ownershipComparisons(data,true),missing:ownershipComparisons({...data,registers:{...data.registers,previous_one:undefined}},false)}));
    ''')
    assert result["missing"] == []
    positions = {row["holder"]: row for row in result["one"]}
    assert "AMB" not in positions
    assert positions["A"]["delta_shares"] == 20
    assert positions["A"]["current_percentage"] - positions["A"]["previous_percentage"] == 2
    assert positions["ENTRY"]["previous_shares"] is None
    assert positions["EXIT"]["current_shares"] is None
    assert result["five"][0]["previous_percentage"] is None
    assert result["five"][1]["delta_shares"] is None


def test_group_navigation_keeps_universe_and_comparison_controls():
    result = bun('''
      import {groupHref,rotationPhase} from "./app/web/src/data/research.ts";
      console.log(JSON.stringify({href:groupHref({id:"Consumer Cyclicals",taxonomy:"SECTOR",scope:"sectors"},"2026-09-25","weekly","60d"),phases:[rotationPhase(null,1),rotationPhase(-1,2),rotationPhase(-1,-2),rotationPhase(1,-2)]}));
    ''')
    assert "scope=sectors" in result["href"] and "date=2026-09-25" in result["href"]
    assert "cadence=weekly" in result["href"] and "horizon=60d" in result["href"]
    assert result["phases"] == ["UNAVAILABLE", "IMPROVING", "LAGGING", "WEAKENING"]


def test_weekly_replay_persistence_does_not_use_future_observations():
    result = bun('''
      import {weeklySectorReadings} from "./app/web/src/data/adapter.ts";
      const group={group_id:"A",name:"A",cohort_count:6,cohort_hash:"fixed",leadership:"LEADING",diffusion:"STABLE",breadth_pct:50,breadth_change_pp:0};
      const weeks=[1,2,3].map(day=>({as_of:`2026-09-0${day}`,groups:[group]}));
      const comparison={weekly:weeks,persistence:{A:{current_leadership_weeks:3}}};
      const early=weeklySectorReadings({...comparison,weekly:weeks.slice(0,1)},[])[0];
      const latest=weeklySectorReadings(comparison,[])[0];
      console.log(JSON.stringify({early:early.persistence,latest:latest.persistence}));
    ''')
    assert result == {"early": 1, "latest": 3}


def test_group_curves_keep_horizon_names_and_break_missing_observations():
    result = bun('''
      import {buildResearchCurve} from "./app/web/src/components/ResearchChart.tsx";
      const prices=closes=>closes.map((close,i)=>({date:`2026-09-0${i+1}`,close}));
      const inputs={histories:{A:prices([100,110,120]),B:prices([100,0,130]),C:prices([100,150,200])},benchmark:prices([100,101,102]),members:["A","B","C"],date:"2026-09-03",cohorts:{"20d":["A"],"60d":["A","B"]}};
      console.log(JSON.stringify({short:buildResearchCurve(inputs,"20"),long:buildResearchCurve(inputs,"60"),action:buildResearchCurve({...inputs,actions:[{date:"2026-09-02",type:"A:split"}]},"60")}));
    ''')
    assert result["short"]["names"] == ["A"]
    assert result["long"]["names"] == ["A", "B"]
    assert result["long"]["rows"][1]["basket"] is None
    assert result["long"]["rows"][-1]["basket"] == pytest.approx(25)
    assert result["action"]["names"] == ["B"]
