# Offline release source plan

`scripts.refresh_release` accepts one `idx-release-source-plan-v1` JSON file and a required `--target-session`. It runs the ordered offline stages in that plan, validates the exact panel inputs, copies the five serialized families and source evidence into a new staging directory, and writes a candidate manifest plus review report. It never activates a release.

The source plan contains:

- `target_session`: the exact completed session, matching the command argument.
- Optional `requested_calendar_date`: kept separate from the completed session.
- `stages`: ordered calls to the existing offline scripts. Each stage has `name`, an allow-listed `module`, `args`, and explicit `outputs`. The panel validation stage must supply the exact panel directory, target session, composite workbook, Stock Summary workbook, every required Daily Statistics PDF, and a staged report path. Validation always receives `--no-publish-fixture` and writes its runtime receipt beside the staged report.
- `families`: exactly `snapshot`, `market`, `ownership`, `foreign`, and `rotation`, each with a local `path`, `sha256`, and `observation_date`.
- `additional_files`: optional snapshot-context JSON files with `file_id`, `path`, `sha256`, `schema`, and `observation_date`. The payload may use an exact `as_of` date or a strict `{ "min": ..., "max": ... }` range; for a range, `observation_date` must equal its maximum date.
- `source_evidence`: exact local evidence files and their expected `sha256`, plus stable source metadata such as `source_id`, `role`, `file_name`, observation/publication/availability dates and the true retrieval timestamp. The runner copies these bytes into the candidate package.
- `snapshot_identity` and `analytical_contracts`: fingerprints copied from the exact candidate inputs and analytical contracts.

All declared stage outputs must resolve inside `--out-dir`. Only existing offline tools are allowed. Publication, latest-file selection, forced historical rebuilds, live-provider and credit-spend flags are refused. Reusing already prepared inputs is allowed when their paths and hashes are pinned. The command requires a fresh `scripts.validate_public_panel` stage before a candidate can pass.

Stage arguments, family paths, and source-evidence paths may use `{target_session}`, `{project_root}`, `{out_dir}`, or `{source:source_id}`. Generated family and evidence outputs should be referenced under `{out_dir}`; paths outside that root are inputs and remain read-only. Every source and output is checked again after the stages complete.

On success, the report contains the release ID, family hashes, source inventory, disclosed market/ownership/foreign/rotation coverage and the separate activation command. On failure, it records the blocker and leaves served releases, canonical history and tracked fixtures untouched. Invocation time and local paths are written to `run-receipt.json`, outside the deterministic manifest.
