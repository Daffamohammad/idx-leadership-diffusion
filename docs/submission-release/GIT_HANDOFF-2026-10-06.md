# Git handoff and repeatable release checks

The verified release source baseline is on the local branch `codex/release-handoff-2026-10-06`. This branch captures the release pipeline, active application, regression coverage, the active release, and its rollback package in scoped commits. The GitHub remote was not changed.

## Release state in Git

- Active: `rel-514f199a7d88a377ccf623f647e9196bcbbaea3d750b81b550affeefe93520f2`, manifest SHA-256 `bb9c5b655ca52026184787dedff9ddfd4c38774ce2b7ea2f2890c76e7f873ea3`.
- Previous rollback package: `rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7`.
- `app/web/public/releases/active.json` points to those exact two packages.
- Other release packages, staging candidates, acquisition captures, and `data/handoff/` are ignored. They remain available in the original working copy and are not removed by this handoff.

## Source archive

The current candidate's exact source evidence is separate from Git. In the original working copy, the archive is `data/handoff/2026-10-06/candidate-diffusion-count-fix-konglo-2026-10-06.tar.gz` (151,079,885 bytes; SHA-256 `d60c0128cab98b69114553df5e316c0aaf328091d7f4298d6ceaa82a86d00edb`). It contains the candidate directory and preserves relative paths and permission bits. The candidate manifest SHA-256 is `cea9e4a7e17f8a21dc3ad22c351c994ff9ece80297c32a0a47e361306e1c153a`.

The tracked [file inventory](evidence-archive-inventory.tsv) lists each relative path, byte count, original mode, and SHA-256. [The receipt](evidence-archive-receipt.json) binds the archive and inventory hashes. Copy the archive from the original working copy into the same relative path in a fresh checkout, then check it before extraction:

```sh
shasum -a 256 -c docs/submission-release/evidence-archive.sha256
mkdir -p data/handoff/2026-10-06/unpacked
tar -xzpf data/handoff/2026-10-06/candidate-diffusion-count-fix-konglo-2026-10-06.tar.gz \
  -C data/handoff/2026-10-06/unpacked
```

The candidate root after extraction is `data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/`. Git preserves file contents and its executable bit, but does not preserve read-only permission bits; the archive does.

## Validate the source and release packages

Install the locked Python dependencies and the web dependencies as described in [local installation](LOCAL_INSTALLATION_AND_WALKTHROUGH.md). Then validate the extracted candidate and both published packages:

```sh
PYTHONPATH=src:. .venv/bin/python -c 'from pathlib import Path; from idx_leadership.data.releases import validate_manifest_file; p=Path("data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/manifest.json"); r=validate_manifest_file(p, candidate=True); print("PASS candidate", r.release_id)'
PYTHONPATH=src:. .venv/bin/python - <<'PY'
from pathlib import Path
from idx_leadership.data.releases import _read_active_pointer

pointer, active, previous = _read_active_pointer(Path("app/web/public/releases"))
assert pointer is not None and active is not None and previous is not None
assert active.release_id == "rel-514f199a7d88a377ccf623f647e9196bcbbaea3d750b81b550affeefe93520f2"
assert previous.release_id == "rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7"
print("PASS active and rollback packages", active.release_id, previous.release_id)
PY
```

Run the independent oracles from the extracted candidate. They do not call the production diffusion classifier; the market-breadth check also verifies all four price horizons against the archived September panel:

```sh
PYTHONPATH=src:. .venv/bin/python -m scripts.verify_diffusion_count_oracle \
  --analysis data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/assets/context/historical_comparison.json
PYTHONPATH=src:. .venv/bin/python -m scripts.verify_market_breadth_price_oracle \
  --market data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/assets/market.json \
  --prices data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/evidence/public-history-september/prices.csv \
  --benchmark data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/evidence/public-history-september/benchmark.csv \
  --breadth data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/assets/context/market_breadth.json \
  --source-manifest data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/evidence/public-history-september/source_manifest.json \
  --validation data/handoff/2026-10-06/unpacked/candidate-diffusion-count-fix-konglo-2026-10-06/evidence/public-history-september/validation.json \
  --out /tmp/market-breadth-oracle.json
```

Expected diffusion output: 160 groups, 3,360 daily observations, 800 weekly observations, zero mismatches. Expected market-breadth status: `PASS`, with `asset_lists_match: true` for 5d, 20d, 60d, and 52w.

## Clean-checkout verification

From the repository root in a clean checkout, install and run the existing checks:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -r requirements.lock
npm ci --prefix app/web
.venv/bin/python -m pytest -q
npm run typecheck --prefix app/web
npm run build --prefix app/web
```

The build refreshes the preview copy of the active pointer. Smoke-check `/overview` and `/map`: Healthcare on 2 October should show **Broadening Firm**; small or unconfirmed readings should render as an em dash; and switching among the four taxonomies should update the URL and clear the selected group. Preview runs use the immutable local package and make no Sectors requests.
