---
session_id: 2026-08-08_005
title: Design Doc Reorganization — Tiered Inline + Surf Scan Pipeline Docs
date: 2026-08-08
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Reorganize all pipeline design documentation into a tiered structure; rename PIPELINE_DESIGN.md with INLINE_ prefix; create feature-doc subfolders under docs/ for both pipelines; trim top-level design docs to concise Tier-2 summaries; update all cross-references and push to GitHub.
retroactive: true
logged_date: 2026-08-08
---

## Original Goal
The workspace had grown large flat design docs (PIPELINE_DESIGN.md,
SURF_SCAN_PIPELINE_DESIGN.md, SURF_SCAN_PIPELINE_DESIGN_RF.md) with deep
implementation detail that made them hard to navigate and maintain.
The goal was to refactor into a three-tier documentation structure:
Tier-1 (DESIGN_INDEX.md), Tier-2 (pipeline summary docs), Tier-3
(feature-specific deep-dive files in docs/<pipeline>/).
All cross-references across the workspace were to be updated and two
clean commits pushed to GitHub.

## Completed Tasks
- [x] Renamed `PIPELINE_DESIGN.md` → `INLINE_PIPELINE_DESIGN.md` (INLINE_ prefix added)
- [x] Created `docs\inline_pipeline\` feature-doc folder with 6 Tier-3 files
- [x] Trimmed `INLINE_PIPELINE_DESIGN.md` into a concise Tier-2 summary routing deep content to `docs\inline_pipeline\`
- [x] Created `docs\surf_scan_pipeline\` feature-doc folder with 6 Tier-3 files
- [x] Trimmed `SURF_SCAN_PIPELINE_DESIGN.md` into a concise Tier-2 summary routing deep content to `docs\surf_scan_pipeline\`
- [x] Deleted `SURF_SCAN_PIPELINE_DESIGN_RF.md` — legacy RF addendum folded into `docs\surf_scan_pipeline\elwc_rf_counters.md`
- [x] Updated `DESIGN_INDEX.md` to reflect new tiered structure
- [x] Updated cross-references in `SURF_SCAN_PIPELINE_DESIGN.md`, `INLINE_PIPELINE_DESIGN.md`, `INLINE_HTML_REPORTS_SCOPE.md`, `html\INLINE_HTML_REPORT_PATTERNS.md`, `docs\EDX CONTEXT.md`
- [x] Updated `images\Alloy_Class\docs\` (4 top-level + 3 learnings/ docs) with inline context system cross-links
- [x] Fixed `.gitignore` to track `images\Alloy_Class\` while keeping `images\defects\` and `images\surf_scan\` ignored
- [x] Pushed two commits to GitHub (PebblesAndMarbles/Defects, master branch)

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `INLINE_PIPELINE_DESIGN.md` | Renamed + Modified | Renamed from `PIPELINE_DESIGN.md`; content trimmed to Tier-2 summary; deep sections routed to `docs\inline_pipeline\` |
| `SURF_SCAN_PIPELINE_DESIGN.md` | Modified | Trimmed to Tier-2 summary; deep sections routed to `docs\surf_scan_pipeline\` |
| `SURF_SCAN_PIPELINE_DESIGN_RF.md` | Deleted | Legacy RF addendum; content absorbed into `docs\surf_scan_pipeline\elwc_rf_counters.md` |
| `DESIGN_INDEX.md` | Modified | Updated to reflect three-tier structure with links to new feature-doc folders |
| `INLINE_HTML_REPORTS_SCOPE.md` | Modified | Cross-reference update to INLINE_PIPELINE_DESIGN.md (new filename) |
| `html\INLINE_HTML_REPORT_PATTERNS.md` | Modified | Cross-reference update |
| `docs\EDX CONTEXT.md` | Modified | Cross-reference update |
| `docs\inline_pipeline\README.md` | Created | Ownership and change-routing table for inline pipeline Tier-3 docs |
| `docs\inline_pipeline\runtime_contract.md` | Created | Runtime contract: input/output schema, column guarantees, failure modes |
| `docs\inline_pipeline\wafer_stage.md` | Created | Wafer stage deep dive: manifest join, stage logic, coordinate mapping |
| `docs\inline_pipeline\coordinates_and_images.md` | Created | Coordinate assignment and image capture pipeline detail |
| `docs\inline_pipeline\benchmark_stage.md` | Created | Benchmark stage: candidate selection, scoring, output format |
| `docs\inline_pipeline\operations_and_hardening.md` | Created | Operational notes: scheduling, error handling, alerting, known edge cases |
| `docs\surf_scan_pipeline\README.md` | Created | Ownership and change-routing table for surf scan pipeline Tier-3 docs |
| `docs\surf_scan_pipeline\runtime_contract.md` | Created | Runtime contract for surf scan pipeline |
| `docs\surf_scan_pipeline\coordinates_and_metrics.md` | Created | Coordinate and metric extraction detail |
| `docs\surf_scan_pipeline\elwc_rf_counters.md` | Created | ELWC + RF counter logic; absorbed content from deleted SURF_SCAN_PIPELINE_DESIGN_RF.md |
| `docs\surf_scan_pipeline\images_and_retention.md` | Created | Image capture, retention policy, and cleanup rules |
| `docs\surf_scan_pipeline\operations_and_hardening.md` | Created | Operational notes for surf scan pipeline |
| `images\Alloy_Class\docs\HANDOFF_START_HERE.md` | Modified | Added inline context system cross-links |
| `images\Alloy_Class\docs\PHASE1_RUNBOOK.md` | Modified | Added inline context system cross-links |
| `images\Alloy_Class\docs\DEFECT_CLASSIFICATION_NEXT_STEPS_HANDOFF.md` | Modified | Added inline context system cross-links |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | Modified | Added inline context system cross-links |
| `images\Alloy_Class\docs\learnings\` (3 files) | Modified | Added inline context system cross-links to all three learnings docs |
| `.gitignore` | Modified | Added `!images/Alloy_Class/` exception to track Alloy_Class docs while keeping images/defects and images/surf_scan ignored |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BE_QUERY_FILES\BACKFILL_WORKWEEK_COLUMNS.py` | Identified as untracked in git | Yes — commit pending (THREAD-008) |
| `BE_QUERY_FILES\backfill_vlm_metadata.py` | Identified as modified/uncommitted | Yes — commit pending (THREAD-008) |
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | Identified as modified/uncommitted | Yes — commit pending (THREAD-008) |
| `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py` | Identified as modified/uncommitted | Yes — commit pending (THREAD-008) |
| `BE_QUERY_FILES\reconcile_prune_images.py` | Identified as modified/uncommitted | Yes — commit pending (THREAD-008) |
| `html\` (dynamic reports) | Excluded from git | No — intentional exclusion confirmed |
| `BOST\` (CSV files) | Excluded from git | No — intentional exclusion confirmed |

## Bugs Encountered
(none)

## Excursions / Scope Creep Discovered
- Several Python files in `BE_QUERY_FILES\` were discovered to be untracked or modified
  without a corresponding commit. Noted as THREAD-008; not addressed this session.

## Open Threads
- [ ] THREAD-007: Alloy VLM Phase 2 (pair-aware BF/DF classification) in progress — Alloy_Class docs now tracked but model work not yet started
- [ ] THREAD-008: Untracked/uncommitted Python files in BE_QUERY_FILES need a cleanup commit

## Key Decisions Made
- `PIPELINE_DESIGN.md` renamed to `INLINE_PIPELINE_DESIGN.md` to disambiguate from surf scan design doc; all callers updated
- `SURF_SCAN_PIPELINE_DESIGN_RF.md` deleted — content was stale addendum; superseded content moved to `docs\surf_scan_pipeline\elwc_rf_counters.md`
- Tiered documentation structure adopted: DESIGN_INDEX.md (Tier-1) → pipeline summary docs (Tier-2) → `docs\<pipeline>\` feature docs (Tier-3)
- `images\Alloy_Class\` tracked in git going forward; `images\defects\` and `images\surf_scan\` remain ignored
- Two separate commits used: one for design context refactor, one for Alloy VLM initialization docs

## Git Status
| Commit | Hash | Message | Files | Insertions |
|--------|------|---------|-------|------------|
| 1 | c0727d3 | Design Context Refactor | 27 files | 3633 insertions |
| 2 | 4420cda | Design Context Refactor +Alloy VLM Initialization | 23 files | 5088 insertions |

- Branch: `master`
- Remote: `PebblesAndMarbles/Defects`
- Status after push: clean (committed work)
- Still uncommitted: BE_QUERY_FILES Python files (see THREAD-008)

## Recommended Re-Entry
**Load these files for context:**
- `agents_history\index.md`
- `DESIGN_INDEX.md`
- `docs\inline_pipeline\README.md`
- `docs\surf_scan_pipeline\README.md`
- `images\Alloy_Class\docs\DEFECT_CLASSIFICATION_NEXT_STEPS_HANDOFF.md`

**Suggested starting prompt:**
> "Read agents_history/index.md and DESIGN_INDEX.md. The documentation was reorganized this session into a three-tier structure. Next priorities are: (1) THREAD-007 — begin Alloy VLM Phase 2 pair-aware BF/DF classification; (2) THREAD-008 — commit remaining BE_QUERY_FILES Python changes. Read the relevant Tier-3 docs before touching any pipeline code."

## Notes for Future Agent
- `PIPELINE_DESIGN.md` no longer exists — it is now `INLINE_PIPELINE_DESIGN.md`. Any search or cross-reference to the old name will fail silently.
- `SURF_SCAN_PIPELINE_DESIGN_RF.md` no longer exists. RF counter and ELWC content lives in `docs\surf_scan_pipeline\elwc_rf_counters.md`.
- The `docs\inline_pipeline\` and `docs\surf_scan_pipeline\` folders are new this session. Check them before editing either top-level pipeline doc.
- The `images\Alloy_Class\` folder is now git-tracked. Be mindful of what you write there.
- THREAD-004 (Alloy_Class folder reorg confirmation) is still technically open — the git push succeeded which implies the new layout is real, but an explicit directory listing was not done during the session.
