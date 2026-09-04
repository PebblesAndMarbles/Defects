# Benchmark Schema And Labeling Workflow (BEEP-Focused)

Date: 2026-08-02
Purpose: define a practical benchmark schema and workflow for selecting and adjudicating BF/DF image pairs, using recent-image reports and factory-classified BEEPs as control signal.

## 1) Benchmark Objective

Create a reusable benchmark slice for Gate D prompt/policy tuning with emphasis on:
- reducing false negatives on true/likely BEEPs
- reducing false positives on non-BEEP controls
- preserving a manageable review_required rate on ambiguous cases

This benchmark is for prompt/system evaluation first, not final production certification.

## 2) Suggested Slice Composition

Target initial size: 40 to 80 BF/DF pairs.

Recommended mix:
- 40% likely/verified BEEP controls
- 40% likely/verified non-BEEP controls
- 20% difficult/ambiguous cases

If starting smaller (for example 30 pairs), keep same proportions approximately.

## 3) Source Pools

1. Recent image report pool (for example 7-day report)
- Use for broad candidate harvesting and diversity.

2. Factory-classified BEEP pool
- Use as positive-control candidates (silver labels).

3. Non-BEEP pool
- Use clear particle or benign examples as negative controls.

4. Hard-case pool
- Cases with disagreement, low confidence, occlusion, or confounder patterns.

## 4) Selection Constraints

Apply these to reduce leakage and improve representativeness:
- Include both BF and DF (image_id 2 and 3) for each selected defect.
- Prefer one entry per unique (WAFER_KEY, INSPECTION_TIME, DEFECT_ID).
- Keep diversity across tool/chamber/time buckets.
- Avoid near-duplicates in tuning and evaluation groups.
- Track whether candidate came from factory BEEP label vs manual review.

## 5) Benchmark CSV Schema

File: `images/Alloy_Class/artifacts/benchmark_slice_v1_template.csv`

### A) Identity and traceability fields
- benchmark_id: unique row id (for example `BMK_0001`)
- split: `tune` | `eval`
- source_pool: `factory_beep` | `non_beep_control` | `ambiguous` | `other`
- selection_batch: free text batch tag (for example `7day_2026w31`)
- wafer_key
- inspection_time
- defect_id
- pair_key
- bright_image_name
- dark_image_name
- bright_image_path
- dark_image_path
- query_site
- tool_name
- chamber

### B) Existing/system labels and model outputs (optional at creation, fill later)
- factory_class_label
- manual_optical_class
- stage_a_orientation
- stage_a_context_confidence
- stage_b_defect_coarse_class
- stage_b_blocked_etch_evidence
- stage_b_review_required

### C) Human adjudication fields (core)
- adjudicated_by
- adjudicated_at_utc
- adjudication_status: `complete` | `needs_second_review` | `deferred`
- adjudicated_coarse_class: `particle` | `possible_beep` | `indeterminate`
- adjudicated_blocked_etch_evidence: `none` | `weak` | `moderate` | `strong`
- adjudicated_confidence: `low` | `medium` | `high`
- comparator_visible: `yes` | `no` | `partial`
- occlusion_present: `yes` | `no`
- offset_surface_lines_present: `yes` | `no` | `unclear`
- notes_needed: `yes` | `no`
- sunken_residual_continuity_present: `yes` | `no`
- comparator_boundary_line_present: `yes` | `no`
- mult_particles_present: `yes` | `no`
- review_required_expected: `yes` | `no`

### D) Error taxonomy fields (for model-gap analysis)
- failure_mode_primary: 
  - `substrate_orientation_error`
  - `structure_scale_error`
  - `blocked_etch_overcall`
  - `blocked_etch_undercall`
  - `occlusion_not_handled`
  - `confounder_not_handled`
  - `insufficient_evidence_but_forced_class`
  - `other`
- failure_mode_secondary
- notes_short

### E) Optional structured observation fields
- pre_etch_geometry_match: `yes` | `no` | `unclear`
- evidence_coherence: `high` | `medium` | `low`
- evidence_localization: `surface` | `interior` | `both` | `unclear`
- particle_edge_morphology: `rounded` | `flat` | `notched_or_chipped` | `irregular` | `mixed` | `unclear`
- particle_morphology_match_to_beep_like: `yes` | `no` | `unclear`

## 6) Labeling Guidance

Keep labels compact and consistent first; add narrative only when needed.

Minimum required fields per row:
- adjudicated_coarse_class
- adjudicated_blocked_etch_evidence
- adjudicated_confidence
- comparator_visible
- occlusion_present
- offset_surface_lines_present
- notes_needed
- sunken_residual_continuity_present
- comparator_boundary_line_present
- mult_particles_present
- review_required_expected
- failure_mode_primary (if model and adjudication differ)

Recommended workflow:
1. First pass: fast triage labeling by you.
2. Second pass: review only disputed/low-confidence rows.
3. Freeze benchmark version tag (for example `benchmark_slice_v1`).

## 7) How To Use With Prompt Iteration

For each prompt variant:
- Run on fixed benchmark slice.
- Compute:
  - false negatives on adjudicated possible_beep
  - false positives on adjudicated non-BEEP
  - disagreement vs adjudicated labels
  - review_required calibration vs `review_required_expected`
- Compare by split:
  - tune split for iteration
  - eval split for holdout check

## 8) Request Template For Next Agent

Use this prompt with another agent:

"Build a candidate benchmark input table from my recent 7-day image report and defect manifest. Produce BF/DF pair-level rows with fields required by `images/Alloy_Class/artifacts/benchmark_slice_v1_template.csv`. Include source_pool tagging (`factory_beep`, `non_beep_control`, `ambiguous`) and maximize diversity across tool/chamber/time. Do not run model inference. Output CSV at `images/Alloy_Class/artifacts/benchmark_candidates_from_7day.csv` and a short summary markdown with counts by source_pool and tool/chamber buckets."

Override policy:
- The prompt above is a generic starter template.
- If a campaign-specific scope document (for example `BENCHMARK_CANDIDATE_TOOL_SCOPE.md`) specifies a different lookback window (such as 14-day), follow the campaign-specific scope.

## 9) Versioning

When making updates:
- Copy template to a versioned file (for example `benchmark_slice_v1_20260802.csv`).
- Keep immutable snapshots for each evaluation campaign.

## 10) Adjudication Quick Guide (What To Fill)

Use this as a per-row checklist while reviewing BF/DF pairs.

### A) Usually pre-filled by tooling (do not edit unless obvious error)
- benchmark_id
- source_pool
- selection_batch
- wafer_key
- inspection_time
- defect_id
- pair_key
- bright_image_name / dark_image_name
- bright_image_path / dark_image_path
- query_site / tool_name / chamber
- factory_class_label / manual_optical_class

### B) You should always fill for adjudication

1. adjudicated_by
- Your name or initials.

2. adjudicated_at_utc
- UTC timestamp of your decision.

3. adjudication_status
- complete: sufficient evidence to make a call.
- needs_second_review: ambiguous or high-impact disagreement.
- deferred: insufficient image/context quality to decide now.

4. adjudicated_coarse_class
- particle: contamination/deposit without convincing blocked-etch signature.
- possible_beep: evidence supports blocked-etch type behavior.
- indeterminate: evidence not strong enough either way.

5. adjudicated_blocked_etch_evidence
- none: no blocked-etch evidence.
- weak: suggestive, but comparator support is limited.
- moderate: multiple consistent cues, reasonable comparator support.
- strong: clear blocked-etch pattern with convincing comparator evidence.

6. adjudicated_confidence
- low: high uncertainty, likely requires second review.
- medium: best-effort decision with some uncertainty.
- high: strong visual evidence and coherent comparator logic.

7. comparator_visible
- yes: one or more impacted structures have a strong, like-to-like comparator with enough visible geometry for boundary/shape checks.
- partial: comparator support is mixed or degraded.
  - use when one impacted structure has a likely comparator but another impacted structure does not
  - use when comparator exists but only a small remnant of impacted structure remains, limiting confirmation quality
  - use when comparator match is partial (for example impacted trench is partial-image-height while comparator trench is full-image-height)
  - use when comparators are visible only indirectly due to crop/sparsity
- no: no reliable comparator for impacted structures, and no defensible nearest-structure fallback.

Comparator decision rule:
- if structures are impacted, adjudicate comparator visibility from impacted structures first
- if structures are not impacted, adjudicate from the nearest structure to the material defect

Occlusion interaction:
- treat occlusion_present separately from comparator_visible
- occlusion can reduce confidence, but does not by itself imply comparator_visible=partial or no

8. occlusion_present
- yes if large object/brightness prevents substrate structure assessment.
- no otherwise.

9. offset_surface_lines_present
- yes if SiO-surface line artifacts near trench edges are visible.
- no if absent.
- unclear if visibility/contrast is insufficient.

10. notes_needed
- yes if this row requires free-text context (low confidence, ambiguity, novel morphology, or disagreement).
- no otherwise; notes_short may be left blank.

11. sunken_residual_continuity_present
- yes if material recessed into comparator structure interior with altered contrast is visible.
- no otherwise.

12. comparator_boundary_line_present
- yes if a sharp contrast line coincides spatially with a comparator boundary.
- no otherwise.

13. mult_particles_present
- yes if more than one particle-like deposit is present in the image.
- no otherwise.

14. review_required_expected
- yes if a cautious workflow should escalate this row.
- no if decision is stable enough for automated pass-through.

### C) Fill when model output is wrong or risky

1. failure_mode_primary
- Pick one best root cause from taxonomy.

2. failure_mode_secondary
- Optional secondary contributor.

3. notes_short
- 1 to 2 lines max: why the call was made or why model missed.
- fill only when notes_needed=yes; may be blank otherwise.

### D) Fields you can leave blank during initial adjudication
- split (assign after enough rows exist for stratified tune/eval split)
- stage_a_orientation
- stage_a_context_confidence
- stage_b_defect_coarse_class
- stage_b_blocked_etch_evidence
- stage_b_review_required

These may be backfilled from model outputs later for comparison.

## 11) Column Spec Update (Notes-Light Adjudication — Adopted 2026-08-09)

Goal:
- Keep current objective tight: distinguish pre-etch style blocked-etch behavior from likely post-etch small particles.
- Move repeated notes patterns into categorical fields.
- Keep notes required only for low-confidence or novel cases.

Scope:
- This is a spec proposal for next benchmark revision.
- No re-labeling requirement for historical rows before adoption.

### A) Keep existing core adjudication fields

Retain current core fields exactly as-is:
- adjudicated_coarse_class
- adjudicated_blocked_etch_evidence
- adjudicated_confidence
- comparator_visible
- occlusion_present
- review_required_expected

Retain existing signature fields:
- offset_surface_lines_present
- sunken_residual_continuity_present
- comparator_boundary_line_present
- mult_particles_present

### B) Add one required field and three optional/derived fields

Required:

1. notes_needed
- values: yes | no
- meaning: whether this row requires free-text for ambiguity, novelty, or disagreement context.
- reason: allows notes_short to become optional in routine rows.

Optional/derived:

1. pre_etch_geometry_match
- values: yes | no | unclear
- meaning: defect edge/corner geometry aligns with expected comparator or trench boundary in a non-random way, even when there is little or no interior occlusion.
- reason: captures repeated notes theme of flat edge, shared edge, or corner notch behavior.
- note: often redundant with comparator_boundary_line_present; use only when it adds clarity.

2. evidence_coherence
- values: high | medium | low
- meaning: whether visible cues support one consistent interpretation.
- reason: captures narrative confidence currently written in notes.
- note: usually inferred from adjudicated_confidence.

3. evidence_localization
- values: surface | interior | both | unclear
- meaning: where decisive cues are seen (SiO surface level, recessed interior, or both).
- reason: distinguishes inset-surface-only vs sunken/interior patterns.
- note: usually inferred from offset_surface_lines_present and sunken_residual_continuity_present.

### C) Optional near-term morphology track

Use only if/when morphology study is activated; do not block current adjudication workflow on these.

1. particle_edge_morphology
- values: rounded | flat | notched_or_chipped | irregular | mixed | unclear
- intent: simple, controlled descriptor of particle outline geometry.

2. particle_morphology_match_to_beep_like
- values: yes | no | unclear
- intent: future analysis field for testing whether morphology subclasses enrich pre-etch/beep discrimination.

### D) Notes policy (new default)

Default:
- notes_short optional.

Set notes_needed=yes when any of the following is true:
- adjudicated_confidence=low
- adjudication_status=needs_second_review or deferred
- evidence fields appear contradictory
- morphology or structure pattern does not fit known signatures

When notes are used:
- keep to 1 to 2 lines
- state one decisive cue and one uncertainty (if any)

### E) Shorthand entry set for new fields

Recommended fast-entry codes:
- pre_etch_geometry_match: y | n | u
- evidence_coherence: h | m | l
- evidence_localization: s | i | b | u
- notes_needed: y | n
- particle_edge_morphology: r | f | c | i | m | u
  - r=rounded, f=flat, c=notched_or_chipped, i=irregular, m=mixed, u=unclear
- particle_morphology_match_to_beep_like: y | n | u

### F) Suggested adoption sequence

1. Add the new columns to next working CSV revision.
2. Use shorthand during review and normalize to canonical values before final analysis.
3. Keep notes only when notes_needed=yes.
4. After 50 to 100 rows, review whether morphology fields improve discrimination; if not, retire them.

Lean default for day-to-day adjudication:
- Treat notes_needed as required.
- Treat pre_etch_geometry_match, evidence_coherence, and evidence_localization as optional overrides.
