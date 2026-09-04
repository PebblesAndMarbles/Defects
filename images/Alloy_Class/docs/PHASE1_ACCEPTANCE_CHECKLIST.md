# Phase 1 Acceptance Checklist

## Purpose
Define clear go/no-go criteria to move from Phase 1 experimentation into Phase 2 integration planning for Alloy-based defect classification.

## Current position snapshot
- ScriptHost-parity runtime path is validated for current baseline pins.
- Pair-safe bounded runs are working with the production-aligned interpreter.
- HTML review visualization is available and usable for analyst triage.
- Transient raw image mode is validated in bounded run: raw download/use/delete completed per processed image while preserving burned-image linkage fields.

Reference docs:
- `WHEELHOUSE_BLOCKER_20260726.md`
- `PHASE1_RUNBOOK.md`
- `DEFECT_CLASSIFICATION_NEXT_STEPS_HANDOFF.md`

## Acceptance gates

### Gate A: Runtime and reproducibility
Pass criteria:
- [x] Wheelhouse audit reports zero missing packages for active lockfile.
- [x] Bootstrap succeeds using UNC-only wheelhouse and lockfile.
- [x] Import check passes in required interpreter (`import alloy` and `from alloy.core.llm import image`).
- [x] Runbook commands execute without local-path edits.

Fail criteria:
- Any dependency is pulled from non-approved index/path during parity validation.

### Gate B: Pairing and input integrity
Pass criteria:
- [x] BF/DF pairing behavior is deterministic and documented.
- [x] Bounded first-pass runs are enforced (`max_pairs` configured and tested).
- [x] Pair coverage report exists for each run: total images, total pairs, selected pairs, unpaired images.
- [x] Unpaired behavior is explicit (skipped by default unless intentionally enabled).

Suggested threshold:
- Pair coverage >= 95% on the selected validation cohort.

### Gate C: Structured output contract stability
Pass criteria:
- [x] JSONL output is parseable for all processed rows.
- [x] Required fields are consistently present for successful rows.
- [x] Error rows are captured with actionable messages (not silent failures).
- [x] Pair-level linkage fields are present and correct (`pair_key`, paired counterpart fields).

Suggested threshold:
- Parse success rate = 100% for `status=ok` rows in acceptance batch.

### Gate D: Classification quality and consistency
Pass criteria:
- [x] Confidence distribution is reviewed and reasonable for known defect examples.
- [x] BF/DF pair consistency is reviewed for disagreement patterns.
- [ ] Review escalation policy is applied and measurable.
- [ ] Metadata is used as context, not as pseudo-ground-truth override.

Suggested thresholds (initial):
- [ ] Manual review rate between 10% and 35% on acceptance cohort.
- [ ] High-confidence contradiction rate below agreed tolerance.

Validation snapshot (2026-07-26):
- Quality review script: `reporting/review_phase1_quality.py`
- Summary artifact: `artifacts/phase1_quality_review_summary.json`
- Cohort: 10 `ok` rows (5 BF/DF pairs)
- Confidence distribution: avg=0.86, min=0.76, max=0.95, buckets=`0.75-0.90: 8`, `>=0.90: 2`
- Pair disagreement rate: 0.80 (4/5 pairs) -> indicates normalization/escalation policy gap
- review_required rate: 0.00 (0/10) -> below target band 10%-35%

### Gate E: Analyst triage usability (HTML)
Pass criteria:
- [x] Report renders BF and DF images side-by-side with captions and structured output.
- [x] Pair/sample rows are easy to locate and compare.
- [x] Report includes enough context for triage decisions without opening raw JSON for every row.

Suggested enhancement before Phase 2:
- [x] Include pair-level metadata columns and reviewer flags in report table.

Validation snapshot (2026-07-26):
- Updated builder: `reporting/build_phase1_html_report.py`
- Generated artifact: `outputs/phase1_combined_report.html`
- Added columns: `Pair Metadata`, `Reviewer Flags`

### Gate G: Transient raw image handling
Pass criteria:
- [x] Raw-image mode can run in bounded pair-safe cohort without persistent raw library growth.
- [x] Processed rows record transient raw provenance (`used_transient_raw`, `raw_download_status`, raw source fields).
- [x] Burned-to-inference linkage is preserved (`burned_image_path`, `inference_image_path`).
- [x] Run summary records both raw-use and raw-delete counters and demonstrates cleanup behavior.

Validation snapshot (2026-07-26, run_id `phase1_raw_transient_verify_20260726`):
- processed=6, failed=0, skipped=0
- total_pairs=3, selected_pairs=3
- raw_used=6, raw_deleted=6

### Gate F: Integration readiness (Phase 2 entry)
Pass criteria:
- [ ] Separate artifact approach is used (no baseline table mutation in first integration pass).
- [ ] Join keys are stable and validated (`WAFER_KEY`, `INSPECTION_TIME`, `DEFECT_ID`).
- [ ] Run-level provenance fields are present (run_id, model, prompt version, timestamp).
- [ ] Consumer path for analyst queue is defined.

## Required discussion: process-context and pattern-context model

## Why this is needed
Image interpretation depends on where and how images were captured in process context:
- Different product and layer patterns can change normal background morphology.
- Defect visual significance can vary with die location and wafer location.
- Defect is expected near image center in this workflow, which changes localization assumptions and prompt policy.

## When this extended conversation should happen
Recommended timing:
- Primary session: end of Phase 1B, before scaling beyond bounded cohorts and before Phase 2 data-contract lock.
- Final policy lock: immediately before Phase 2 integration artifacts are frozen.

Practical trigger:
- Hold this conversation once pair-safe runs are stable and before evaluating larger cohorts (for example, before moving from 3 to 5 pairs into 20+ pairs).

## Conversation outputs (must produce)
- [ ] Context field inventory and ownership:
  - product/family identifier
  - process/layer context
  - chamber/tool context where applicable
  - die/wafer positional context (normalized coordinates or bins)
- [ ] Pattern-variability policy:
  - what background variability is expected by context
  - when to force `review_required` for unfamiliar context
- [ ] Center-target assumption policy:
  - expected defect-near-center rule
  - tolerance window for off-center cases
  - handling for multiple salient candidates
- [ ] Prompt/schema updates:
  - fields added for context-awareness
  - explicit uncertainty rules when context is absent
- [ ] Acceptance metrics by context slice:
  - performance and review rates segmented by product/layer/wafer-position bins

## Suggested meeting format
- 60-minute working session with process/domain owner + inline pipeline owner + classification owner.
- 5-day follow-up with updated schema, prompt revisions, and one context-segmented validation report.

## Sign-off block
- [ ] Runtime owner sign-off
- [ ] Classification owner sign-off
- [ ] Process/domain owner sign-off
- [ ] Integration owner sign-off

Decision:
- [ ] Promote to Phase 2
- [ ] Continue Phase 1 refinement
- [ ] Blocked (document blocker and owner)
