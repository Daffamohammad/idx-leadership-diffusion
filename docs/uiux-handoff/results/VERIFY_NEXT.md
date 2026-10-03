# VERIFY_NEXT — independent sequence for Codex

1. Inspect diff: `git log --oneline -5`, `git show --stat HEAD`, `git diff df33d75..HEAD --check`.
2. Validate sources/formulas/schemas:
   - Confirm no live calls: only `/snapshots/*.json` + `/idx/*.json` fetches in `SnapshotProvider.tsx`; no Sectors/search/parser execution.
   - Rotation formulas in `data/rotation.ts` unchanged (X = YTD excess vs IHSG; Y = 20D − 60D); diagnostic fallback uses documented 20D/60D without phase assignment.
   - Top-3 0–100 (`top3Label`), flow 65% gates, `complete=false`, 962/500/496/265 denominators in proper context.
3. Run checks: `npm run typecheck --prefix app/web`, `npm run build --prefix app/web`, `git diff --check`.
   If Python/schema/exporter/calc changes are added later, run relevant tests first, then `.venv/bin/python -m pytest -q` (do not report the 729 baseline as current without rerunning).
4. Browser walkthrough per VISUAL_QC.md (viewports, themes, routes, geometry, keyboard/search/filter/detail/regression).
5. Polish remaining PARTIALs: treemap parent–child view, Theme/Konglo bounded filing metadata, extended period gating with reasons, SPA code-split.
6. Keep UI and release verdicts separate: UI polish ≠ release readiness (bundle completeness, freshness, comparability, and data gates still HOLD).

Loop: reproduce defect → minimum affected code → rerun relevant checks → update screenshots/matrix → explain before/after. Do not reply “fixed” without patch + evidence. Mark anything unverified as UNVERIFIED with reproduction steps.
