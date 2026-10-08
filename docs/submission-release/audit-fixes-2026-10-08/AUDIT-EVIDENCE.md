# Audit-fixes evidence · 8 October 2026

Source commit: `4b7a9cb` ("Audit fixes: compliant copy, link params, paired cohorts, oracle coverage").
Active release: `rel-64026e36d49733009fec952086fc95a3121a86efbb196b1c68d00fd6317f33d2` (unchanged; no data assets touched).

## Fresh at this commit

| Check | Evidence | Result |
| --- | --- | --- |
| Python suite | [python-checks.txt](python-checks.txt) | 935 passed (932 + 3 new regression tests) |
| Frontend typecheck | [frontend-typecheck.txt](frontend-typecheck.txt) | clean |
| Frontend build | [frontend-build.txt](frontend-build.txt) | success |
| Sectors oracle (extended: leadership, map/descriptive cohorts+values, signed concentration) | [sectors-oracle.json](sectors-oracle.json) | PASS, 0 mismatches |
| Final reading oracle (incl. new `rotation_phase_ytd`) | [reading-oracle.json](reading-oracle.json) | PASS, 0 mismatches |
| Integer diffusion count oracle | [diffusion-count-oracle.txt](diffusion-count-oracle.txt) | 174 groups, 3,654 daily + 870 weekly, 0 mismatches |
| Route smoke (local preview, fresh build) | [route-smoke.txt](route-smoke.txt) | all 16 routes 200 |
| Clean-checkout reproduction (both analysis assets, credentials unset) | [clean-reproduction.json](clean-reproduction.json) | PASS, 0 provider calls |
| Production-bundle copy checks | frontend-build run | new copy present; old banned strings and 403 widget URL absent |

The market-breadth price oracle is retained from
[final repair verification](../final-repair-2026-10-08/market-breadth-oracle.json):
its price-panel inputs and code are untouched by this audit.

## Pending (requires a real browser; none is installed here)

- Fresh browser QA at this commit, including `/` (new landing + footer + Dashboard preview),
  the fixed TradingView widget on `/overview`, banned-word scan, four viewports, console errors.
- Re-issued readiness receipt bound to the new source commit (also corrects the stale
  `previous_*` pointer noted in the audit).
- Vercel launch after GitHub integration is connected; public hosting remains blocked.
