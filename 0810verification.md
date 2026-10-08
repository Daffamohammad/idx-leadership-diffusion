# 0810 verification · 8 October 2026

Local verification **PASS** at `d1a223f` (fixes at `555a27a`).
See [verification and evidence](docs/submission-release/final-audit-2026-10-08/VERIFICATION.md).

- Fresh browser QA: 23 checks; 64 loads across all sixteen routes and four
  required sizes. Figures, playback, ownership comparisons and ticker links work.
- Readiness reissued: zero independent mismatches, exact offline rebuild,
  59 focused tests and four audit regressions passed. Immediate rollback is
  correctly `rel-fad218…`; the active `rel-64026…` package is unchanged.
- Zero paid calls. Original ledgers and historical receipts remain unchanged.
  Paid acquisition stays on HOLD; the reported 221 remaining calls are unused.

Public hosting remains blocked. Vercel has no project linked to this repository,
and checking its integration permissions returned HTTP 403. Connect repository
access before deploying `codex/final-diffusion-repair` and checking the public URL.
The older remote main is not the source verified here. Videos, social publication
and final submission remain deferred.
