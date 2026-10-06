# Local installation and release walkthrough

## Install and run

Requirements: Python compatible with `requirements.lock` (the verified environment used Python 3.14), and the Node.js version supported by the checked-in Vite lockfile.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -r requirements.lock
npm ci --prefix app/web
npm run build --prefix app/web
npm run preview --prefix app/web -- --host 127.0.0.1 --port 4174
```

Open `http://127.0.0.1:4174/overview`. If the port is in use, choose another and pass it with `--port`. The app loads the hash-bound active release from `app/web/public/releases/`; it does not contact the Sectors API. Sectors remains **HOLD**, and the recorded sample page reads a static release asset.

The preview serves `app/web/dist/`, which contains a build-time copy of `releases/active.json`. After any authorized pointer change, rebuild before opening or checking the preview. Refresh an already open browser page after changing the pointer.

## Walkthrough

Use the Overview for the selected market session and breadth horizons, Market Movers for the ranked stock lists, and Leadership Map to switch among Sectors, Konglo, curated themes, and IDXIC activities. Check Healthcare's 2 October diffusion reading, then use the inspector and history controls to see how missing or unconfirmed readings appear. The Recorded Sectors sample page displays the frozen sample and source reconciliation from the release. Methodology and evidence links explain the data limits.

The 5 October captioned recording predates the active release's market breadth and daily replay. Current verification evidence and screenshots are linked from [the release handoff](HANDOFF-2026-10-06.md).

## Repeat the release checks

Use [the Git handoff](GIT_HANDOFF-2026-10-06.md) to obtain and verify the hash-identified source archive, validate the active and rollback packages, run both independent oracles, and repeat the clean-checkout checks. The archive is separate from Git because it contains the exact raw source evidence; its inventory and hash receipt are checked before use.
