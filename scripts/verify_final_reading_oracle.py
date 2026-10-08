"""Independent arithmetic oracle for each research horizon, cohort and map.

Reads frozen input CSVs. It does not import the production return, group,
leadership, concentration or diffusion implementations.
"""
from __future__ import annotations
import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path


def verify(manifest_path: Path) -> dict:
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    entries = {row["file_id"]: row for row in manifest["additional_files"]}
    def load(file_id):
        row = entries[file_id]; raw = (root / row["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError(f"oracle source hash mismatch: {file_id}")
        return json.loads(raw)
    def csv_rows(file_id):
        payload = load(file_id); raw = gzip.decompress(base64.b64decode(payload["data"]))
        if hashlib.sha256(raw).hexdigest() != payload["uncompressed_sha256"]:
            raise ValueError("oracle reproduction input hash mismatch")
        return csv.DictReader(io.StringIO(raw.decode()))
    prices = {}
    for row in csv_rows("research_price_input"):
        prices.setdefault(row["ticker"], {})[row["date"]] = float(row["adjusted_close"])
    benchmark = {row["date"]: float(row["close"]) for row in csv_rows("research_benchmark_input")}
    sessions = sorted(benchmark); positions = {day:i for i,day in enumerate(sessions)}
    analysis = load("historical_comparison")
    market = json.loads((root / manifest["families"]["market"]["path"]).read_text())
    eligible = {row["ticker"] for row in market["records"] if row.get("signal_eligible") is True}
    dates = analysis["analysis_dates"]
    bases = [day for day in sessions if day[:4] < dates[-1][:4]]
    baseline = bases[-1] if bases else None
    start = lambda day,h: baseline if h == "ytd" else sessions[positions[day]-int(h[:-1])] if positions[day] >= int(h[:-1]) else None
    mismatch = []; counts = {"horizon_values":0,"cohort_lists":0,"map_values":0,"leadership_states":0,"concentration_values":0,"diffusion_observations":0,"legacy_weekly_consistency":0}
    def check(label, actual, expected):
        okay = actual is None and expected is None if actual is None or expected is None else math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-6) if isinstance(expected,(float,int)) else actual == expected
        if not okay: mismatch.append({"field":label,"actual":actual,"expected":expected})
    def raw(name,day,h):
        base = start(day,h)
        return (prices[name][day] / prices[name][base]-1)*100
    def ex(name,day,h):
        return raw(name,day,h) - (benchmark[day]/benchmark[start(day,h)]-1)*100
    def mean(values):
        return sum(values)/len(values) if values else None
    def phase(x,y):
        if x is None or y is None or not math.isfinite(x) or not math.isfinite(y): return "UNAVAILABLE"
        return ("LEADING" if x >= 0 else "IMPROVING") if y >= 0 else ("WEAKENING" if x >= 0 else "LAGGING")
    for kind,taxonomy in analysis["taxonomies"].items():
        for gid,group in taxonomy["groups"].items():
            cohorts = {}
            members = [row["ticker"] for row in group["members"]]
            for h in ("5d","20d","60d","ytd"):
                required = {endpoint for day in dates for endpoint in (day,start(day,h)) if endpoint}
                cohorts[h] = sorted(name for name in members if name in eligible and all(start(day,h) for day in dates) and all(math.isfinite(prices.get(name,{}).get(day,0)) and prices.get(name,{}).get(day,0) > 0 for day in required))
                check(f"{kind}/{gid}/{h}/cohort",group["cohorts"][h],cohorts[h]); counts["cohort_lists"] += 1
            shared = sorted(set(cohorts["20d"]) & set(cohorts["60d"]))
            leadership = sorted(set(shared) & set(cohorts["5d"]))
            ytd_shared = sorted(set(shared) & set(cohorts["ytd"]))
            for cadence in ("daily","weekly"):
                previous = None
                for point in group[cadence]:
                    day = point["as_of"]; label = f"{kind}/{gid}/{cadence}/{day}"
                    for h,names in cohorts.items():
                        check(label+"/"+h,point["excess_return_"+h],mean([ex(name,day,h) for name in names])); counts["horizon_values"]+=1
                    x = mean([ex(name,day,"60d") for name in shared]); e20 = mean([ex(name,day,"20d") for name in shared]); y = e20-x if x is not None and e20 is not None else None
                    ytdx = mean([ex(name,day,"ytd") for name in ytd_shared]); a=mean([ex(name,day,"20d") for name in ytd_shared]);b=mean([ex(name,day,"60d") for name in ytd_shared]);ytdy=a-b if a is not None and b is not None else None
                    for key,value in {"map_x_60d":x,"relative_momentum":y,"rotation_phase":phase(x,y),"rotation_phase_ytd":phase(ytdx,ytdy),"map_x_ytd":ytdx,"map_y_ytd":ytdy}.items():
                        check(label+"/"+key,point[key],value);counts["map_values"]+=1
                    lead="UNCONFIRMED"
                    if len(leadership)>=5:
                        ahead=mean([ex(name,day,"20d") for name in leadership])>0
                        acceleration=mean([ex(name,day,"5d") for name in leadership])-mean([ex(name,day,"60d") for name in leadership])>=1
                        lead=("LEADING" if ahead else "IMPROVING") if acceleration else ("WEAKENING" if ahead else "LAGGING")
                    check(label+"/leadership",point["leadership"],lead);counts["leadership_states"]+=1
                    names=cohorts["20d"]; n=len(names); count=sum(ex(name,day,"20d")>0 for name in names) if n else None
                    for key,value in {"breadth_count":count,"breadth_denominator":n,"breadth_pct":count/n*100 if n else None}.items():check(label+"/"+key,point[key],value)
                    returns=sorted([abs(raw(name,day,"20d")) for name in names],reverse=True);gross=sum(returns)
                    check(label+"/concentration",point["concentration_top3_pct"],sum(returns[:3])/gross*100 if gross>0 and n>=3 else None);counts["concentration_values"]+=1
                    delta=count-previous if count is not None and previous is not None else None
                    state="UNCONFIRMED"
                    if delta is not None and n>=5:
                        threshold=max(2,math.ceil(n*.1))
                        state="STABLE" if delta==0 or abs(delta)/n*100<10 else ("BROADENING" if delta>0 else "NARROWING")+("_FIRM" if abs(delta)>=threshold else "_FRAGILE")
                    check(label+"/diffusion",point["diffusion_v2"],state);check(label+"/count_change",point["breadth_change_count"],delta);counts["diffusion_observations"]+=1
                    previous=count
    for week in analysis["weekly"]:
        for row in week["groups"]:
            point=next(p for p in analysis["taxonomies"]["SECTOR"]["groups"][row["group_id"]]["weekly"] if p["as_of"]==week["as_of"])
            for key in ("excess_return_20d","excess_return_60d","breadth_pct","breadth_change_pp","leadership","concentration_top3_pct"):
                check("legacy_weekly/"+key,row[key],point[key]);counts["legacy_weekly_consistency"]+=1
    return {"schema_version":"final-reading-oracle-v1","status":"PASS" if not mismatch else "FAIL","release_id":manifest["release_id"],"checks":counts,"mismatch_count":len(mismatch),"mismatches":mismatch[:30],"provider_calls":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--manifest",type=Path,required=True);parser.add_argument("--out",type=Path,required=True);args=parser.parse_args()
    report=verify(args.manifest);args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+"\n");print(json.dumps({key:value for key,value in report.items() if key!="mismatches"}));return report["status"]!="PASS"

if __name__=="__main__":raise SystemExit(main())
