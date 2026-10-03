# 0310 Audit — 2026-10-03

Repo: `idx-leadership-diffusion` · HEAD `b71cb46` (`refactor: complete universe and evidence contracts`) · branch `main`.
Mode: offline only. Zero live Sectors calls. Product code untouched by this audit except via the committed refactor under review; this handoff includes the report, `docs/codemap/`, and the separate Archify sequence artifact under `.archify/`.

## 1. Refactor execution contract — verification

Single coherent path confirmed in the persisted bundle (`snap_sectors_2026-08-27`):
`Search (You.com/Tavily) → first-party selection → Parser (LlamaCloud) → deterministic reducer → snapshot contract → UI`.
Search output is discovery evidence only; never promoted directly to a numeric observation.

### 1.1 Universe / taxonomy agent — PASS
- `listing_registry`: `listed=962, discovered=962, persisted=962`, `unique=962`, `duplicates=0`, `full_accessible_universe_listed=true`.
- All 962 rows carry `analysis_requested` + `analysis_status` (500 requested / 462 not; 265 observed features).
- Taxonomy 100% complete from provider fields; Konglo 9 / Themes 40 from `config/konglo.yaml` / `config/themes.yaml`, empty otherwise.
- Known boundary (not a failure): native `security_master.json` is still the 500-row legacy sample (`coverage.is_prefix_sample=true`, 496/500 usable histories); the 962-row registry reads the validated capture. Next authorized bounded live refresh must rewrite the native sidecar with the full list while requesting history only for the demo sample.

### 1.2 Search agent (You.com / Tavily) — PASS
- `quantitative_use=false` end-to-end. Tavily 3/3/3, You 5/5/5 per category (≤5 cap); Tavily crawl 1 record (≤5).
- Provenance records provider, query, result count, selected URL. First-party policy `idx.co.id/ojk.go.id/ksei.co.id`.
- Minor: one Tavily event URL is `http://` (still first-party IDX publication PDF). No numeric promotion.

### 1.3 Parser agent (LlamaCloud) — PASS
- OJK June 2026 context: IHSG 5643.19, net sell −19.63T, YTD −73.61T, RNTH 24.19T, local 59.41%, cap 9897T — all match.
- `parser_file_id 41acfb2f…`, pages `[1,2]`, `llamacloud-parse-v1`, checks/warnings/limitations present, `not_per_ticker` + `not_per_group` explicit, `used_in_leadership_or_diffusion=false`.
- IDX daily PDF: 9 pages bounded, 4 net-foreign values + units checked; discovery `quant=false`; raw parse kept local (`data/raw/llamaparse/`).

### 1.4 Flow / transaction agent — PASS
- Lane 1 (IDX July investor-type): 23 trading days, same-side gross totals retained, reconciliation all true.
- Lane 2 (bounded company sample): 6 market days, 60 obs, 65% mapped, original net preserved, missing legs never inferred.
- Lane 3 (full-universe feed): absent, correctly not promoted. No flow input reaches leadership/breadth/diffusion/concentration.
- Follow-up of the previously reported contract-text defect: the inverted wording ("foreign-to-domestic minus domestic-to-foreign") was not found in current repository documentation. `docs/REFACTOR_EXECUTION_PLAN.md:62`, `README.md:230`, and `docs/IDX_STATISTICS_SOURCE.md:22` already agree with the reducer (`src/idx_leadership/providers/idx_statistics.py:886`): `domestic_to_foreign − foreign_to_domestic`. The historical finding is retained here as reported, rather than as an active repository defect; no calculation change is needed.

### 1.5 Product / interface agent — PASS
- Brief renders `## Coverage Notes`; no `## Data Gaps`; no `DATA_GAP`/`READY_WITH_GAPS` raw badges.
- Streamlit renders via `human_readable_status()`; React via `formatEnumLabel()` ("Not available", "Ready · partial coverage", …). No legacy heading in render paths (only the internal `BRIEF_SECTIONS` enum, mapped at render).
- Market context visibly market-level, separate from per-ticker/group confirmation. Registry panel exposes all 962 tickers with hierarchy + explicit membership.

### 1.6 Operational gates — all green
- Preflight dry-run: no HTTP. Demo defaults verified: 250 symbols / 400 HTTP / 1000 credits; `--full-live` separate and credit-gated. No full-live run executed.
- The snapshot loader fetches local `/snapshots/*.json` and `/idx/*.json`; snapshot reload never invokes a Sectors, search, or parser provider. Search/parser artifacts are cached and reused.
- `pytest`: 729 passed. `tsc -b --noEmit`: clean. `vite build`: green (948 kB single chunk — pre-existing debt, code-split candidate).
- Rendered-language scan: brief has Coverage Notes, no legacy heading, no raw badge.

## 2. Full audit (HEAD b71cb46)

- Tree was clean at audit start (later: modified `docs/codemap/*` + untracked `.archify/` from the Archify diagram task).
- Secrets: `.env` ignored and untracked; no `tvly-/ydc-/llx-` keys in tracked files (endpoint URLs and redaction regexes only); `test_adv_secret`, `test_live_preflight`, `test_brief_contract`, `test_official_market_context` (24 tests) green.
- No scope broadening. `official_market_context.py` isolated from the flow pipeline; no new analytical duplication.
- Next: (1) rewrite native security-master sidecar on the next authorized bounded refresh, (2) code-split the SPA bundle. The reported flow-direction wording defect was not reproduced in current repository documentation (see §1.4).

## 3. Codemap regeneration (docs/codemap/)

Prior lock (`035a01b`, Aug 28, 127-file scope) was stale vs 405 tracked files. Regenerated all three files together from HEAD with an updated 20-node generator (`_build.py`: REPO path fix, verified `path:line symbol` evidence).

- `codemap.json`: 20 nodes / 54 edges / 5 flows, scope 289 files.
- New nodes surfacing the refactor lanes: `search-agents`, `idx-parser`, `taxonomy`; `signals` (merged leadership/diffusion/transitions); `evidence` (builder + intelligence + events); `config-docs` (merged config + docs).
- Stale ids removed (6): `signals-leadership`, `signals-diffusion`, `signals-transitions`, `evidence-builder`, `config`, `docs`. Added (6): `signals`, `evidence`, `config-docs`, `search-agents`, `idx-parser`, `taxonomy`. All 14 retained modules changed fingerprints; none unchanged.
- 5 flows: `flow-build-snapshot`, `flow-search-parse-publish` (new: search → parser → market context), `flow-export-snapshot`, `flow-web-render`, `flow-story-render`.
- Unknowns (1): `web-app → models` (`reads`, JSON-shape boundary, no Python import) — explicitly marked. Fixed 3 stale evidences found during audit (`features→models`, `market-universe→models`, `aggregation→features` pointed at wrong symbols).

### Validation
- JSON parses; 0 bad edge refs; 0 bad flow refs; 0 missing node paths; 0 unlocatable evidence symbols.
- HTML embeds the same nodes/edges/flows; header shows repo, generation time, commit; dark theme default; legend, search/filter/zoom/drag, click-highlight and flow-path select present.
- Lock matches HEAD, dirty flag matches `git status`, taxonomy fingerprint independently recomputed — match; json scope == lock scope; json node ids == lock modules.
- Builder exit 0; `validation.txt` = `OK`.

## 4. Open items
1. Native `security_master.json` (500) vs registry (962) divergence — resolve on the next authorized bounded live refresh.
2. SPA bundle 948 kB single chunk — code-split candidate.

The separate `.archify/sequence-web-request-20261003-170157/` example is included with this handoff and remains outside the product codemap's scope. Its `width-review/` receipts describe the current spread-column artifact; root finalize/browser receipts describe the preceding layout. It is a generic cache-miss sequence example, not an IDX deployment diagram.

## 5. Pre-commit verification

- Corrected the codemap generator's stale repository label, described yfinance as an explicitly selected prototype provider, and aligned the fingerprint-algorithm description with the existing implementation. Regenerated JSON, lock, and HTML together; builder exit 0, `validation.txt` = `OK`.
- Revalidated 20 nodes / 54 edges / 5 flows / 289 scoped files, all 20 independently recomputed module fingerprints, node/edge/flow references, source-evidence locatability, matching JSON/lock scope, and identical embedded HTML data. One explicit unknown remains (`web-app → models`).
- Archify strict provenance check: 9/9 checks pass, zero composition errors or warnings. Current specification SHA-256 `5abc23577efc93910b67bb3314c6502ac5feaecd8500beceb69febf44ef7710a`; current HTML SHA-256 `854205cef9704df55522f62c0dd3367e2b53086860f2ade4379321cc9a2dbb19`. Delivery and `width-review/` browser receipts match these bytes. Browser evidence is from the recorded earlier run; perceptual review remains `not-requested`.
- Changed-file credential-pattern scan passes. Source/documentation staged whitespace checks pass; the full staged check reports 15 trailing-whitespace lines in the immutable generated Archify HTML. Its rendered bytes are preserved so delivery/browser hashes remain valid; this is a recorded formatting warning. The 729-test, typecheck, and product-build results above are retained from the preceding audit; this handoff reran document/artifact checks because product code did not change.
- Handoff scope: this report, four codemap files, and the nine existing Archify example/receipt files. The codemap remains a snapshot of audited HEAD `b71cb46`, including the documented dirty-tree generation state.
