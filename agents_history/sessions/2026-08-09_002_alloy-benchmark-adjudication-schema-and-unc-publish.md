---
session_id: 2026-08-09_002
title: Alloy Benchmark CSV Workflow + Adjudication Schema Simplification + UNC Publish
date: 2026-08-09
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.3-Codex
triggered_by: manual-checkpoint
status: complete
original_goal: Finalize benchmark candidate CSV workflow updates, simplify adjudication schema usage, tighten comparator/occlusion guidance, and publish the updated artifacts on UNC with backups.
---

## Original Goal

Capture a formal checkpoint for the Alloy benchmark adjudication workstream after schema and
workflow changes were applied. The session focused on producing a review-ready CSV, reducing
labeling ambiguity through clearer field guidance, and safely publishing outputs to UNC paths
without losing prior working copies.

## Completed Tasks

- [x] Applied benchmark CSV workflow updates and refreshed the active candidate dataset.
- [x] Simplified adjudication schema usage by converging on compact required fields plus optional derived fields.
- [x] Updated comparator/occlusion decision guidance for consistent reviewer behavior.
- [x] Published updated benchmark artifacts to UNC workspace paths.
- [x] Preserved local-prepublish backup copy of the benchmark CSV before overwrite.

## Files Modified

| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` | Modified | Primary adjudication working file; includes expanded/normalized adjudication columns and active row-level labels. |
| `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md` | Modified | Schema and workflow guidance updated, including notes-light usage and optional derived evidence fields. |
| `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md` | Modified | Comparator/occlusion definitions, decision sequence, and shorthand codebook refined for review consistency. |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv.pre_local_copy_20260809_195242.bak` | Created | Pre-publish safety backup of the benchmark CSV before latest edits/publish. |

## Files Affected (referenced but not modified)

| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\artifacts\benchmark_candidates_14day_summary.json` | Used to confirm artifact counts, source-pool mix, fallback join rate, and chamber distribution for checkpoint status. | No |
| `images\Alloy_Class\artifacts\benchmark_slice_v1_template.csv` | Used as schema compatibility baseline; compared against working CSV columns. | Yes |
| `images\Alloy_Class\docs\BENCHMARK_CANDIDATE_TOOL_SCOPE.md` | Source of build/publish contract and output path expectations for 14-day candidate generation. | No |

## Bugs Encountered

(none newly introduced in this session)

## Excursions / Scope Creep Discovered

- Active adjudication rows include shorthand and narrative-entry variability that can leak into downstream analysis unless normalized before scoring.
- Working CSV currently carries columns beyond the baseline template header; tooling/template alignment remains a follow-up item.

## Open Threads

- [ ] THREAD-003: Align `benchmark_slice_v1_template.csv`, candidate-builder output, and adjudication docs to one authoritative column contract.
- [ ] THREAD-004: Normalize adjudication shorthand and free-text anomalies in `benchmark_candidates_14day.csv` before tune/eval scoring.
- [ ] Execute deterministic split assignment and freeze a versioned snapshot for evaluation campaign handoff.

## Key Decisions Made

- Keep the adjudication workflow notes-light by default (`notes_needed` gate) while preserving optional deep evidence fields only when they add signal.
- Treat comparator visibility and occlusion as separate axes; occlusion lowers certainty but does not automatically downgrade comparator visibility.
- Keep UNC artifact publication in-place, with explicit prepublish local backup to reduce overwrite risk.

## Artifact Status And Backup Paths

Current published artifacts:
- `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv` (active adjudication table)
- `images\Alloy_Class\artifacts\benchmark_candidates_14day_summary.json` (status metrics)
- `images\Alloy_Class\artifacts\benchmark_candidates_14day_split_preview.csv` (optional split preview)

Current status summary (from summary JSON):
- rows_written: 145
- rows_pairs_complete: 145 (unpaired: 0)
- source_pool_counts: non_beep_control=96, factory_beep=48, ambiguous=1
- fallback_join_rate: 0.0207
- factory_beep_share: 0.331 (above 30% quality target)

Backup path created during this session:
- `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv.pre_local_copy_20260809_195242.bak`

Publish location context:
- All listed outputs are published under workspace UNC root:
  `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\...`

## Risks / Assumptions

Risks:
- If shorthand/narrative anomalies are not normalized, benchmark analytics can overstate disagreement and error-taxonomy rates.
- If schema drift remains between template and working CSV, future regeneration may drop or reorder adjudication columns.
- UNC availability or permission interruptions can affect downstream reproducibility when reports are opened cross-host.

Assumptions:
- `benchmark_candidates_14day.csv` remains the canonical active adjudication source until a versioned freeze is created.
- Existing artifact summary JSON reflects the same generation window as the currently published CSV.
- Team will preserve the backup file until split assignment and QA checks complete.

## Recommended Re-Entry

**Load these files for context:**
- `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv`
- `images\Alloy_Class\artifacts\benchmark_candidates_14day_summary.json`
- `images\Alloy_Class\docs\BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md`
- `images\Alloy_Class\docs\ADJUDICATION_WORKSHEET_ONE_PAGER.md`
- `images\Alloy_Class\artifacts\benchmark_slice_v1_template.csv`

**Suggested starting prompt:**
> "Read the benchmark CSV, summary JSON, and adjudication docs. First normalize shorthand/value anomalies in `benchmark_candidates_14day.csv`, then align template and builder column contracts, then regenerate split preview and produce an eval-ready frozen snapshot."

## Notes for Future Agent

- The backup file with `pre_local_copy` suffix is part of the publish safety flow and should not be deleted until campaign freeze.
- Comparator/occlusion guidance now explicitly separates visibility from obstruction; preserve this distinction in any future prompt/schema updates.
- Treat this checkpoint as the formal handoff point for moving from schema/workflow prep into scoring and evaluation packaging.
