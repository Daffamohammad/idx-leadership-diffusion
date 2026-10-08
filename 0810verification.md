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

The verified source and evidence are published to both `main` and
`codex/final-diffusion-repair` at `10e8bd2`. The prior main commit `8c34fed`
remains available for rollback; see the
[source-publication receipt](docs/submission-release/final-audit-2026-10-08/publication.json).

Public hosting remains blocked. The
[fresh launch attempt](docs/submission-release/final-audit-2026-10-08/launch.json)
returned HTTP 400 because Vercel's GitHub integration is missing. Connect
repository access before launching `main` and checking the public URL.
Videos, social publication and final submission remain deferred.
