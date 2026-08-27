# IDX Leadership Diffusion — Architecture

## High-level flow

```text
+--------------------+
|     Provider       |  (YFinanceProvider, SectorsProvider, FixtureProvider)
| (raw vendor data)  |
+--------------------+
          |
          v
+--------------------+
|  Raw Cache (TTL)   |  data/cache/  (raw payloads, replayable)
+--------------------+
          |
          v
+--------------------+
|   Normalization    |  src/.../providers/*.py  (canonical DataFrames)
+--------------------+
          |
          v
+--------------------+
| Canonical Data     |  Security master, price observations, benchmark obs
| (Pydantic schemas) |  src/.../models/schemas.py
+--------------------+
          |
          v
+--------------------+
|  Feature Engine    |  returns, relative strength, breadth, concentration
+--------------------+
          |
          v
+--------------------+
| Group Aggregation  |  src/.../aggregation/groups.py
+--------------------+
          |
          v
+--------------------+
| Signal Engine      |  leadership, diffusion, transitions, change digest
+--------------------+
          |
          v
+--------------------+
|  Evidence Builder  |  src/.../evidence/builder.py
+--------------------+
          |
          v
+--------------------+
|  Snapshot /        |  data/snapshots/<snapshot_id>/
|  Manifest          |  manifest.json, change_digest.json, quality.json
+--------------------+
          |
          v
+--------------------+
|  Streamlit UI      |  app/streamlit_app.py (read-only)
+--------------------+
```

## Layer responsibilities

| Layer | Module(s) | Provider-independent? | Notes |
| --- | --- | --- | --- |
| Provider | `idx_leadership.providers.*` | n/a (encapsulates vendor) | Three implementations: `YFinanceProvider`, live-gated `SectorsProvider`, `FixtureProvider` |
| Cache | `idx_leadership.data.RawCache` | yes | TTL-controlled, deterministic |
| Normalization | `idx_leadership.providers.{public,fixture,sectors}` | yes at the boundary | Outputs canonical column names |
| Schemas | `idx_leadership.models.*` | yes | Pydantic-typed, strict at boundaries |
| Features | `idx_leadership.features.*` | yes | No vendor objects reach this layer |
| Aggregation | `idx_leadership.aggregation.*` | yes | Group snapshots |
| Signals | `idx_leadership.signals.*` | yes | Deterministic, threshold-driven |
| Evidence | `idx_leadership.evidence.*` | yes | Structured evidence objects |
| Pipeline | `idx_leadership.pipeline` | yes | Orchestrator |
| Snapshots | `idx_leadership.data.snapshots` | yes | Atomic writes; per-snapshot manifest |
| UI | `app/streamlit_app.py` | yes | Read-only, no business logic |

## Why a provider abstraction?

The application never imports `yfinance` (or any vendor SDK) outside the
`providers/public.py` module. This:

- keeps the analytical engine reproducible on fixtures without internet,
- enables parallel parity checks between public and Sectors data,
- keeps credit economics auditable (every request goes through the
  `RequestLedger`),
- allows future replacement of the data backend without touching
  analytics, snapshots, UI, or tests.

## What is provider-agnostic today?

- All return / excess-return / breadth / concentration math.
- Group aggregation, leadership/diffusion classification.
- Snapshot, manifest, quality, and change-digest infrastructure.
- The Streamlit UI (reads snapshot artifacts only).
- The test suite (uses `FixtureProvider` exclusively).

## What still depends on vendor specifics?

- `YFinanceProvider._call_yfinance_with_retry` (vendor-specific retry shape).
- `SectorsProvider` is a real Sectors v2 implementation behind the same
  interface in `providers/sectors.py`; live HTTP is opt-in and requires
  a credential.
- Cache key format includes vendor-specific fields; cross-vendor cache
  reuse is not supported.

## Design principles

1. **No silent fallbacks.** Missing data returns `None`/`UNCONFIRMED`,
   never 0 or "neutral".
2. **Provenance is mandatory.** Every output row carries a method
   version, feature version, provider, and source timestamp.
3. **Atomic snapshot writes.** Per-file `tmp + rename` so partial
   snapshots never replace a good one.
4. **Deterministic ordering.** Group ranks are stable across reruns.
5. **Testability first.** The full pipeline can be exercised against
   `FixtureProvider` without network or credentials.

## Threading & async

The implementation is single-threaded and synchronous. The `YFinanceProvider`
serializes ticker fetches but does not parallelize them. This is
deliberate: future Sectors requests will be rate-limited, and parallel
calls add complexity without clear benefit in the prototype stage.

## Configuration

- `config/universe.yaml` — ticker list, prototype taxonomy, benchmark ID
- `config/methodology.yaml` — thresholds (horizons, breadth, leadership)
- `config/providers.yaml` — provider enable flags and class paths

All numerical thresholds live in `methodology.yaml`. No magic numbers in
code.
