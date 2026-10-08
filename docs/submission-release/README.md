# The Diffusion · 8 October 2026

The Diffusion helps equity researchers inspect leadership beneath the Indonesian
index: which sectors outperform IHSG, whether participation changes, and which
constituents drive the move. Open **Dashboard** at `/sectors`, then select a
group, replay a date, inspect an individual price path, or compare baskets.

## Coverage and readings

The Diffusion chooses **66 tracked stocks across 11 sectors, six per sector by
market-cap ranking** on 2 October 2026. This is a retrospective project coverage
choice, not a limit of the Sectors API. Returns use raw Sectors stock closes and
native Sectors IHSG closes. Splits, rights issues, dividends, and other listed
mechanical events exclude affected calculation windows. Missing observations
remain missing. Each horizon has its own eligible contributors; each breadth
comparison uses identical names at both dates. Concentration uses the actual
20D contributors. A one-name change in six names is fragile; two names are firm.

The default map uses **60D excess versus IHSG** and **20D minus 60D excess
momentum**. Its coordinate signs determine rotation phase. Leadership instead
uses 20D excess and 5D-minus-60D acceleration with a 1 percentage-point threshold.
The current core has eleven rankings, nine confirmed points, and two hollow
descriptive points. Confirmed signals require five contributors. Empty
quadrants are valid. Twenty-three supported YTD stock readings retain their
own 2 October end date; no core sector reaches the five-name YTD floor.

The broader IDX workflow uses its separately disclosed Yahoo Finance adjusted
price panel. The catalogue contains all 34 Arthara reference labels and twelve
retained portfolio identifiers, 102 IDXIC groups, and fifteen themes. Current
60D maps contain 11 sector, 46 Konglo, 99 IDXIC, and 15 theme points. Groups
without coordinates remain visible with their coverage reasons. Basket curves
use fixed horizon cohorts and equal-weighted prices rebased at the window start;
missing intermediate prices break the curve rather than changing its membership.

Business-group membership follows dated IDX holder positions, exact issuer
legal-name links, and cited issuer evidence. Holdings, affiliation, and legal
control are separate relationships. The 34-label reconciliation does not claim
complete Arthara constituent counts, family ownership, or control. Analyst
lenses and listed anchors are identified; indirect holdings paths require the
stated ownership threshold and do not establish legal control. Undated issuer
pages have retrieval and assessment dates, not invented publication dates.

Ownership preserves 7,158 prior 1% register rows for genuine share and
percentage-point comparisons. The current/prior 1% dates are 30 September /
31 August 2026; the 5% disclosure date is 1 October. Its published prior shares
remain separate, and prior percentages are not inferred. Ambiguous identities
and account reconciliation flags remain visible. The default scope excludes
KSEI composition and scripless-conversion analysis.

## Verified package and rollback

- Active: `rel-64026e36d49733009fec952086fc95a3121a86efbb196b1c68d00fd6317f33d2`
- Manifest SHA-256: `98e2c260c9afae07ce2b1cb5b5436cda8bbff9978a0239d809d909183ad36e4f`
- Tested source: `2e6c516c3254bbae0d380491487181bae1867f7b`
- Immediate rollback: `rel-fad218940fcc7e2492d97613681175b6cb2b2e38d387254737fafc0cadfa09dc`
- Rollback manifest SHA-256: `2defade3acf1688eb96e0e40d577189f390eafd03fea69a1175ce5e07aa1f11c`

The original recording, ledgers, previous packages, technical asset identifiers,
and historical receipts remain intact. The successor is activated through the
existing immutable publication process. The previous package remains the
pointer's rollback target; the earlier `rel-246dd63…` package is also retained.

**Paid acquisition remains on HOLD.** This repair made zero Sectors calls.
The original budget retains 461 estimated reservations against its 500 ceiling.
The user-reported 221 remaining provider calls have not been consumed or
reconciled with that budget. No further acquisition is authorized by readiness.

Current evidence is in [final repair verification](final-repair-2026-10-08/VERIFICATION.md),
including [browser QA](final-repair-2026-10-08/browser-qa.json),
[readiness](final-repair-2026-10-08/readiness.json),
[clean reproduction](final-repair-2026-10-08/clean-reproduction.json), and
[publication](final-repair-2026-10-08/publication.json). Earlier audit reports
remain dated records and do not replace these checks.

## Reproduce without credentials

Install the locked Python and frontend dependencies, then:

```sh
RELEASE_ID="$(.venv/bin/python -c 'import json; print(json.load(open("app/web/public/releases/active.json"))["active"]["release_id"])')"
RELEASE_DIR="app/web/public/releases/$RELEASE_ID"
.venv/bin/python -m scripts.prepare_final_repair \
  --reproduce "$RELEASE_DIR/manifest.json" --destination /tmp/diffusion-reproduction
.venv/bin/python -m scripts.verify_final_reading_oracle \
  --manifest "$RELEASE_DIR/manifest.json" --out /tmp/diffusion-reading-oracle.json
.venv/bin/python -m pytest -q
npm run typecheck --prefix app/web
npm run build --prefix app/web
npm run preview --prefix app/web -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173/sectors`. All inputs needed to rebuild the native core
and broader group readings are hash-bound in the package. No credentials,
provider transport, or paid requests are needed. Group/ticker links preserve
`scope`, `date`, `cadence`, and `horizon`; `/recorded-sample` redirects to `/sources`.

Readiness accepts a browser receipt, not a boolean approval. It rejects missing,
failed, incomplete, or stale source/release evidence and validates screenshot
hashes for 1036×799, 1369×799, 1440×900, and 390×844:

```sh
.venv/bin/python -m scripts.verify_sectors_readiness \
  --browser-qa-receipt docs/submission-release/final-repair-2026-10-08/browser-qa.json \
  --out /tmp/diffusion-readiness-new.json
```

## Delivery gates

The local application and public repository are separate from public hosting.
See the dated [launch evidence](final-repair-2026-10-08/launch.json) for the latest
Vercel result. A public URL must pass fresh-load checks before hosting is accepted.
Videos, the prescribed social post, and final submission remain deferred; app
verification alone does not complete the submission.

Historical source and acquisition evidence includes the [6 October handoff](GIT_HANDOFF-2026-10-06.md),
[7 October sign-off](signoff-2026-10-07.json), and the earlier
[8 October repair](repair-2026-10-08/VERIFICATION.md). These records are preserved.
