# Local installation and Sectors walkthrough

## Install and run

Requirements: a Python version compatible with `requirements.lock` and the
Node.js version supported by the checked-in Vite lockfile.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -r requirements.lock
npm ci --prefix app/web
npm run build --prefix app/web
npm run preview --prefix app/web -- --host 127.0.0.1 --port 4174
```

Open `http://127.0.0.1:4174/`; it redirects to `/sectors`. The page reads
hash-bound assets from the active immutable release and makes no Sectors API
requests. After changing `releases/active.json`, rebuild before checking the
preview because the build copies the pointer into `app/web/dist/`.

## Walkthrough

The primary page ranks 11 sectors by 20-session excess return. Use the map to
compare 60-session excess return with relative momentum. Change replay cadence
between daily and weekly, select a replay date, and choose a sector to inspect
its six recorded constituents, eligible contributor count, leadership,
diffusion, concentration, price gaps, and corporate-action exclusions.
The YTD panel uses the last observed 2025 native IHSG date and reports only
same-date, action-free stock readings. The current release has 23 eligible
YTD constituent readings; none of the 11 sector aggregates reaches the
five-contributor minimum, so those aggregates remain unconfirmed.

The sample is retrospective and uses raw Sectors closes against native IHSG
closes. Read the boundary and methodology disclosures beside the controls.
Broader IDX pages are available under the context section of the navigation.

The dated 5 October walkthrough video documents an earlier interface and is not
a recording of this submission build. See the [current release notes](README.md)
and [readiness receipt](readiness-2026-10-07.json) for current evidence.

## Repeat the checks

```sh
.venv/bin/python -m pytest -q
npm run typecheck --prefix app/web
npm run build --prefix app/web
```

The current Sectors analysis can be rebuilt and checked with the independent
oracle by following the commands in the [release notes](README.md). The dated
6 October Git handoff remains available as historical evidence for the broader
IDX market and price-breadth checks.
