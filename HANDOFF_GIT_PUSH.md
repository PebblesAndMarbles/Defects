# Handoff: Multi-Commit Git Push (Repo Backlog Catch-Up)

**Written:** 2026-09-21
**Requested by:** tbatson, as pre-work for the VLM Overhaul effort (see `images/Alloy_Class/VLM_Overhaul.md`) — housekeeping should land before new feature/wiring work begins.
**Precedent to follow:** `agents_history/sessions/2026-09-04_002_repo-hygiene-ignore-and-untrack-checkpoint.md` — same pattern (split a large dirty tree into logical, reviewable commits) was used successfully before.

## Goal
The working tree has ~2 weeks of accumulated, uncommitted work across `BOST/`, `WDS/`, `images/Alloy_Class/`, `agents_history/`, and misc BE/surf-scan files. Turn this into a small number of logical commits (not one giant commit), push to `origin/master`, and stop for human review at the checkpoints noted below.

## Hard rules
1. **Do not run `git push` until the final "STOP — review gate" step below has been explicitly cleared by the user.** Creating local commits is fine and expected; publishing them is not this agent's call to make alone.
2. **Do not `git commit --amend` or rewrite any commit that has already been pushed.** `origin/master` currently matches local `master` before this work starts (`git status` shows "up to date with origin/master") — that's the safe starting point.
3. **No `--force` anything.**
4. **Do not reorganize files beyond what's already staged/dirty.** The only file moves already done are `images/Alloy_Class/tools/probe_generic_description_v1.py`..`v8.py` → `images/Alloy_Class/tools/OLD/` (already staged as renames — keep them staged, they belong in Commit 1). Don't invent additional reorganization; that's a separate, not-yet-approved follow-up.
5. **Known gotcha — `OLD/` is globally gitignored** (`.gitignore` line `OLD/`, unanchored, matches any directory named `OLD` at any depth). Already-tracked files moved into an `OLD/` folder via `git mv` stay tracked (verified — the 8 renamed files above show as `R` in `git status`, not dropped). But if this agent or a future one adds *new* untracked files into any `OLD/` directory, plain `git add` will silently skip them. Note this if commit diffs look smaller than expected. Also note: `images/Alloy_Class/docs/OLD/` already has content locally but **none of it is tracked in git** (`git ls-files` returns nothing for that path) — it's silently local-only. Do not try to "fix" that in this pass; flag it back to the user as a separate decision (do they want any of that content committed, or is it intentionally throwaway?).
6. After each commit, run `git show --stat HEAD` and paste/report the output before moving to the next commit, so the user can review the commit boundaries after the fact.
7. If any file listed below is no longer dirty/untracked when you actually run `git status` (state may have moved on since this doc was written), re-derive the current status rather than blindly trusting this list — treat this doc as a grouping *plan*, not a literal script.

## Proposed commit sequence

### Commit 1 — Alloy_Class: generic-description v9 pipeline (canonical) + probe archive
```
git add images/Alloy_Class/tools/probe_generic_description.py
git add images/Alloy_Class/tools/run_generic_description_chunked.py
git add images/Alloy_Class/tools/consolidate_generic_description_registry.py
git add images/Alloy_Class/tools/enrich_production_with_vlm_attributes.py
git add images/Alloy_Class/reporting/build_vlm_attributes_filterable_report.py
git add images/Alloy_Class/reporting/build_generic_description_html_report.py
git add images/Alloy_Class/tools/build_beep_labeling_tranche.py
git add images/Alloy_Class/config/generic_description_prompt_v8.json
git add images/Alloy_Class/config/generic_description_prompt_v9.json
git add images/Alloy_Class/docs/HANDOFF_PROBE_CONSOLIDATION_AND_ENRICHMENT.md
git add images/Alloy_Class/docs/VLMat90percentNEXT_STEPS.md
git add images/Alloy_Class/VLM_Overhaul.md
# the v1-v8 renames are already staged (git mv done earlier this session) -- leave as-is, just include in this commit
git commit -m "Alloy_Class: consolidate generic-description pipeline on v9 prompt; archive v1-v8 probes to tools/OLD/"
```
**Before committing, decide with the user:** `images/Alloy_Class/400pairdebug.txt` is untracked — it reads like an ad hoc debug dump, not a durable artifact. Recommend leaving it untracked (or deleting it) rather than committing it. Do not add it unless the user says otherwise.

### Commit 2 — BOST: replace legacy dispo/process-family scripts with accumulating-history pipeline
```
git add BOST/11_build_accumulating_bost_csv.py
git add BOST/BOST_ENRICHMENT_REGISTRY_PLAN.md
git add BOST/adhoc_bost_accumulating_history.csv
git add BOST/adhoc_bost_gate_rollout.py
git add BOST/COMMS/ BOST/ONE_OFFS/ BOST/archive/ BOST/artifacts/ BOST/docs/ BOST/registry/
git add BOST2/
git add artifacts/definition_registry_new_2026-09-14.csv
git add artifacts/adhoc_bost_dryrun_summary.json artifacts/adhoc_bost_full_summary.json artifacts/adhoc_bost_pilot_summary.json
git add -u "BOST/AMEct 1278 Inline Defects Fleet Dispo.jsl" BOST/BOST_DefectQuery_Plan.md \
  BOST/adhoc_bost_enriched_dryrun_8M5CL_8M6CL.csv BOST/adhoc_bost_pilot_enriched_8M5CL_8M6CL.csv \
  BOST/adhoc_pilot_manifest_8M5CL_8M6CL.csv BOST/sDTT_bost_process_family_explore.py \
  artifacts/adhoc_bost_definition_columns.csv
git commit -m "BOST: add LOT7-keyed accumulating history builder; retire superseded dispo/process-family scripts"
```
(`git add -u` stages the deletions of the six superseded files — confirm each is genuinely superseded per `agents_history/sessions/2026-09-13_001_bost-track-a-removal-checkpoint.md` and `2026-09-14_004_bost-accumulating-csv-lot7-initialization-checkpoint.md` before staging; don't re-derive that judgment from scratch.)

### Commit 3 — WDS: new APEX_ENTITY enrichment module
```
git add WDS/
git add dev/wds-decoder-cache/
git commit -m "WDS: add APEX_ENTITY incremental enrichment module"
```
**Before committing:** run `git status --short WDS/ dev/wds-decoder-cache/` after `git add` and confirm nothing matching the `.gitignore` "proprietary process IP" carve-outs (`WDS/wds_ca_bundle.pem`, `WDS/wds_columns_probe_*.txt`, `WDS/wds_etch_fdc_schema.md`, `WDS/FULL_FLOW_ALIASES_SCHEMA.md`, `dev/wds-clients/`, `dev/idealapex/`) is staged. Those should already be silently excluded by `.gitignore`, but verify rather than assume — this is exactly the kind of thing worth a second look before a push.

### Commit 4 — BE_QUERY_FILES: routine data refresh
```
git add BE_QUERY_FILES/8M5CL_NCDD_EDI.csv BE_QUERY_FILES/8M6CL_NCDD_EDI.csv BE_QUERY_FILES/8M6CL_NCDD_EDI_LONG.csv
git add BE_QUERY_FILES/DEFECT_COORDINATES_RECLASS_LOG.csv
git add BE_QUERY_FILES/merged_sources/8M5CL_NCDD_merged_dedup.csv BE_QUERY_FILES/merged_sources/8M6CL_NCDD_merged_dedup.csv
git add BE_QUERY_FILES/surf_scan_daily.py
git add BE_QUERY_FILES/8M6HM2_HVF_NCDD_EDI_LONG.jsl
git commit -m "BE_QUERY_FILES: routine NCDD/reclass data refresh; surf_scan_daily update; add 8M6HM2 HVF query"
```
**Flag, don't auto-include:** `BE_QUERY_FILES/SUBSET_SUBSET_SS_EDX_STACKED By (INSPECTION_TIME, PRIMARY_EQUIP).csv` — filename looks like a one-off ad hoc export (double "SUBSET_SUBSET", spaces/parens). Ask the user whether this is a durable artifact or scratch output before adding it anywhere.

### Commit 5 — html/ + surf-scan reporting updates
```
git add html/INLINE_PRODUCTION_SUBENTITY_REPORTS.py html/SS_INLINE_CHAMBER_REPORT.py html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py
git add html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS_7DAY.py
git add "SS_Wafermaps_BivReport.jsl" SS_Wafermaps_BivReport_debug.txt SURF_SCAN_PIPELINE_DESIGN.md docs/FLEET.txt
git add artifacts/surf_scan_elwc_pm_stage_apply_summary.json artifacts/surf_scan_elwc_pm_stage_full_summary.json artifacts/surf_scan_run_summary.json artifacts/update_run_artifacts.json artifacts/benchmark_artifacts.json
git commit -m "SurfScan/Inline reporting: add 7-day subentity report variant, refresh run artifacts"
```

### Commit 6 — agents_history backlog + saved planning prompts
```
git add agents_history/sessions/2026-09-04_003_tranche-builder-manifest-matching-checkpoint.md
git add agents_history/sessions/2026-09-06_001_generic-description-probe-html-report-checkpoint.md
git add agents_history/sessions/2026-09-07_001_alloy-step2-truth-state-enrichment-and-handoff-cleanup.md
git add agents_history/sessions/2026-09-09_001_alloy-generic-description-registry-consolidation-checkpoint.md
git add agents_history/sessions/2026-09-09_002_generic-description-registry-bootstrap-and-tranche-fix.md
git add agents_history/sessions/2026-09-09_003_alloy-generic-description-chunked-submission-follow-through-checkpoint.md
git add agents_history/sessions/2026-09-09_004_generic-description-chunked-submission-bug-fixes-and-verification-checkpoint.md
git add agents_history/sessions/2026-09-10_001_bost-enrichment-registry-pilot-and-coverage-escalation-checkpoint.md
git add agents_history/sessions/2026-09-10_002_bost-enrichment-investigation-complete.md
git add agents_history/sessions/2026-09-11_003_bost-column-refactor-complete.md
git add agents_history/sessions/2026-09-11_003_bost-column-refactoring-complete.md
git add agents_history/sessions/2026-09-12_001_decoder-client-pilot-dead-end-and-bost2-scoping.md
git add agents_history/sessions/2026-09-12_002_bost-query-core-baseline-rollback.md
git add agents_history/sessions/2026-09-13_001_bost-track-a-removal-checkpoint.md
git add agents_history/sessions/2026-09-14_001_bost-full-flow-aliases-fix-and-handoffs-closure.md
git add agents_history/sessions/2026-09-14_002_wds-apex-entity-enrichment-checkpoint.md
git add agents_history/sessions/2026-09-14_003_wds-apex-entity-incremental-accumulator-checkpoint.md
git add agents_history/sessions/2026-09-14_004_bost-accumulating-csv-lot7-initialization-checkpoint.md
git add agents_history/sessions/2026-09-04_002_repo-hygiene-ignore-and-untrack-checkpoint.md
git add agents_history/index.md agents_history/file_map.md agents_history/open_threads.md
git add .github/prompts/
git commit -m "agents_history: log backlog of BOST/WDS/Alloy sessions 2026-09-04 through 2026-09-14; add saved planning prompts"
```
**Note:** two files exist for what looks like the same BOST column-refactor session — `2026-09-11_003_bost-column-refactor-complete.md` and `2026-09-11_003_bost-column-refactoring-complete.md` (same session number, different filenames). This is the same duplicate-log pattern seen and resolved in `2026-09-09_004`. Don't silently pick one — flag it back to the user or diff them first; if one is a byte-for-byte duplicate, follow the same resolution precedent (delete the redundant one, keep the one referenced in `index.md`).

### Commit 7 — repo hygiene
```
git add .gitignore USEFUL_COMMANDS.txt
git commit -m "Repo hygiene: gitignore 7-day subentity report output; add USEFUL_COMMANDS reference"
```

## STOP — review gate
After Commit 7, **do not push**. Instead:
1. Run `git log --oneline -8` and `git status --short` (should show a clean tree except anything explicitly deferred above — `400pairdebug.txt`, the `SUBSET_SUBSET` CSV, the duplicate BOST session log).
2. Report the commit list and any deferred/flagged items back to the user.
3. Wait for explicit approval before running `git push origin master`.

## What this handoff deliberately does not cover
- The larger Alloy_Class "move Stage A/B substrate + benchmark scoring tooling to `OLD/`" housekeeping pass discussed separately — only the v1-v8 probe archive (already staged) is in scope here. Do not expand scope.
- Any changes to `C:\RAW_IMAGES` (outside this git repo entirely).
- Deciding whether `images/Alloy_Class/docs/OLD/` content should ever be tracked — surfaced as an open question above, not resolved here.
