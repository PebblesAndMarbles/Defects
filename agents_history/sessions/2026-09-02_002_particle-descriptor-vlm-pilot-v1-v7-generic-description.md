---
session_id: 2026-09-02_002
title: Particle Descriptor VLM Pilot — Generic-Description Prompt Iteration v1 through v7
date: 2026-09-02
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 5
triggered_by: manual-checkpoint
status: partial
original_goal: Build a Phase 1 VLM (vision-language model) generic-description + structured-attribute labeling pilot for BE etch defect SEM images, scoped to CLASS=='SMALL_PARTICLE' only, to support later clustering.
---

## Current Checkpoint
Current user goal: advance the SMALL_PARTICLE generic-description pilot by landing the v8 substrate-relative texture calibration and validating the local-cache 400-pair probe/report path.

Current state: the v8 local-cache probe completed on the 400-pair slice with `status_ok_rate=1.0`, `parsed_rate=1.0`, and `review_required_rate=0.0`; the HTML review report was generated at `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_review.html`.

Current artifacts and commands: `images\Alloy_Class\tools\probe_generic_description_v8.py`, `images\Alloy_Class\reporting\build_generic_description_html_report.py`, `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400.jsonl`, `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_manifest.csv`, and `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_review.html`; the probe uses the same fixed pilot manifest pattern as v1-v7 and the same HTML report builder, with local-cache image resolution and raw-download status recorded as `local_cache`.

Cleanup: the PowerShell cleanup completed successfully.

Immediate next step: inspect the 400-pair HTML review report and decide whether to keep the v8 texture wording as-is or make one more prompt pass before broader use.

## Original Goal
Build a Phase 1 VLM generic-description + structured-attribute labeling pilot for BE etch
defect SEM images, scoped to `CLASS=='SMALL_PARTICLE'` only (BEEP is explicitly excluded —
it is a separate, pre-existing manual disposition effort tracked in its own tranche system).
Phase 1 = open-ended description + exploratory structured attributes to support later
clustering. The clustering method itself, and the final "produce decided labels" prompt
(Phase 3), are both explicitly deferred to a future session — not attempted this session.

This log supersedes/refocuses an earlier draft summary that had incorrectly folded
BEEP-classification-tranche context into this session's primary narrative. That tranche
work is real but belongs to a separate track (see "Secondary/Adjacent Context" below) and
to [2026-09-02_001](2026-09-02_001_be-alloy-class-tranche-0007-misclassified-beep-checkpoint.md),
which documents real, separate tranche_0007 work and stands untouched.

## Completed Tasks
- [x] Built one-time stratified sample selector (`select_generic_description_sample.py`) — 40 BF/DF pairs across chambers, `outputs/probes/generic_description_pilot_manifest.csv`, case IDs `SMP_PILOT_001`-`040`, reused unchanged across all 7 prompt versions
- [x] Built `probe_generic_description_v1.py` through `v7.py` — raw (non-burned) image VLM probe scripts, gpt-5.4-mini, reusing raw-image download/GAJT/SecureFTP plumbing from `pipelines/classify_phase1_batch.py`
- [x] Built `build_generic_description_html_report.py` — schema-agnostic per-case HTML report generator, with optional reviewer feedback widget
- [x] Ran all 7 prompt versions over the full 40-case manifest — all final runs 40/40 raw_ok, 40/40 parsed_ok
- [x] Iterated prompt vocabulary v1 -> v7 via a "propose spec -> confirm -> wire -> run -> report -> gather feedback" loop, with a standalone canonical spec txt file per version
- [x] Found and resolved 4 real bugs (Windows MAX_PATH, two VLM enum-echo failures, a feedback-form JS null deref) plus clarified one non-bug (ALLOY_API_KEY)
- [x] Collected reviewer feedback (v1+v2 round, v7 round in progress at checkpoint time)
- [x] Wired and ran the v8 local-cache probe over 400 pairs using the fixed local-cache manifest path; the run completed cleanly with 400/400 `status_ok` and 400/400 parsed results
- [x] Generated the v8 local-cache HTML review report for the 400-pair run
- [x] Completed the PowerShell cleanup
- [ ] v8 prompt (substrate-relative texture calibration) — drafted as a `[CHANGE]` note only, not yet wired into any prompt (see Open Thread #1)
- [ ] Decision on how the VLM labeling pilot connects to the hand-labeled BEEP tranche data — not decided (see Open Thread #2)
- [ ] Clustering method and Phase 3 "decided labels" prompt — explicitly out of scope this session

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\select_generic_description_sample.py` | Created | One-time sample selector: filters `outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv` to `CLASS=='SMALL_PARTICLE'`, pairs IMAGE_ID 2/3 (BF/DF), stratified-samples 40 pairs across chambers (SUBENTITY) |
| `images\Alloy_Class\outputs\probes\generic_description_pilot_manifest.csv` | Created | 40-case manifest (`SMP_PILOT_001`-`040`); reused UNCHANGED across all 7 prompt versions — do not resample without a specific reason |
| `images\Alloy_Class\tools\probe_generic_description_v1.py` ... `v7.py` (7 files) | Created | Near-identical scripts differing mainly in the `GENERIC_DESCRIPTION_PROMPT_Vn` constant; model gpt-5.4-mini, DEFAULT_MAX_TOKENS=1800, retry-at-2400-on-empty-response; SKIPS a pair entirely (never falls back to burned images) if raw download fails |
| `images\Alloy_Class\reporting\build_generic_description_html_report.py` | Created | New report generator (separate from pre-existing `build_probe_html_report.py`); schema-agnostic attributes table, raw model_call JSON `<details>` block, optional `--with-feedback-portal` comment-only feedback widget, `_master_submit_assets()` page-top "Submit All Feedback" button |
| `images\Alloy_Class\outputs\probes\generic_description_v1_20260830T222707Z.jsonl` ... `generic_description_v7_20260902T224006Z.jsonl` | Created | Raw run outputs, one per version; all final runs 40/40 raw_ok, 40/40 parsed_ok |
| `images\Alloy_Class\outputs\probes\generic_description_v1..v7_pilot_review*.html` | Created | HTML reports per version, generated via `build_generic_description_html_report.py` |
| `images\Alloy_Class\outputs\probes\generic_description_v1_pilot_feedback.csv` | Created | Reviewer feedback CSV, v1+v2 review rounds, reviewer "Trey" |
| `images\Alloy_Class\outputs\probes\generic_description_v7_pilot_feedback.csv` | Created | Reviewer feedback CSV, v7 review round — **in progress at time of this checkpoint; read this file directly for latest comments, don't assume complete** |
| `images\Alloy_Class\tools\probe_generic_description_v8.py` | Created | v8 local-cache probe: same structure as v7, updated prompt to substrate-relative coarse_texture calibration, run against the fixed 400-pair local-cache slice |
| `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400.jsonl` | Created | 400-pair local-cache probe output; completed successfully with 400/400 `status_ok` and 400/400 parsed responses |
| `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_manifest.csv` | Created | Local-cache 400-pair manifest used by the v8 probe |
| `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_review.html` | Created | HTML review report for the 400-pair local-cache probe run |
| `images\Alloy_Class\Particle_Descriptors.txt`, `Particle_Descriptors copy.txt`, `Particle_Descriptors copy 2.txt`, `Particle_Descriptors_v4.txt` | Created | Pre-canonical draft spec files leading up to v3 |
| `images\Alloy_Class\Particle_Descriptors_v3_canonical.txt` | Created | v3 canonical spec |
| `images\Alloy_Class\Particle_Descriptors_v4_canonical.txt` | Created (now empty) | v4 canonical spec — **wiped by the user's own editor undo/redo mishap; content was intentionally reconstructed forward into v5 rather than restored backward. Leave this file empty, do not "fix" it without asking.** |
| `images\Alloy_Class\Particle_Descriptors_v5_canonical.txt` | Created | v5 canonical spec |
| `images\Alloy_Class\Particle_Descriptors_v6_canonical.txt` | Created | v6 canonical spec |
| `images\Alloy_Class\Particle_Descriptors_v7_canonical.txt` | Created | v7 (current/latest) canonical spec; contains the unwired `[CHANGE]` note under section 2a driving Open Thread #1 (v8) |
| `images\Alloy_Class\reporting\build_probe_html_report.py` | Modified | Fixed `submitFeedback()` JS to use optional chaining (`?.value \|\| ''`) on `agrees_${domId}`/`corrected_${domId}` — shared helper used by both the probe-report and generic-description-report tracks; backward compatible |

### Secondary/adjacent (BEEP tranche mechanics — background only, separate track)
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\tools\build_beep_labeling_tranche.py` | Modified | Added `lot` output column — affects all FUTURE tranches automatically |
| `images\Alloy_Class\reporting\build_beep_labeling_report.py` | Modified | Added `lot` output column, matching the tranche builder change |
| `outputs\beep_evidence\tranche_0005_cases.csv` | Modified | Backfilled `lot` column, 100/100 matched. Tranches 0001-0004 still lack `lot` — left as optional/deferred, not an oversight |
| `images\Alloy_Class\docs\HANDOFF_BEEP_MISCLASSIFIED_REPORT.md` | Created | Handoff doc for a future agent to build a static HTML report of tranche cases hand-labeled BEEP (factory misclassifications) — report itself NOT built, only the handoff doc exists |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Source of reused `_call_image`/`_load_env_from_supported_locations` helpers | No |
| `images\Alloy_Class\pipelines\classify_phase1_batch.py` | Source of reused `RawImageConfig`/`_download_raw_image_to_temp`/`_load_secureftp_runtime`/`DEFAULT_GAJT_DLL_SEARCH_PATHS` (GAJT/SecureFTP/pythonnet raw image download) | No |
| `images\Alloy_Class\reporting\feedback_portal\backend\main.py` | Existing Flask feedback backend (port 8000, `-DataFile`/`FEEDBACK_DATA_FILE`-driven, append-only CSV, CORS open) reused as-is for generic-description feedback | No |
| `outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | Source population filtered by `select_generic_description_sample.py` | No |
| `outputs\beep_evidence\beep_evidence_ground_truth.csv` | Hand-labeled BEEP/SMALL_PARTICLE ground truth (tranches 1-5, 143 BEEP / 357 SMALL_PARTICLE) — join target under consideration for Open Thread #2 | Decision pending, see Open Thread #2 |
| `outputs\beep_evidence\tranche_000N_cases.csv` | Per-tranche hand-labeled case files — join target under consideration for Open Thread #2 | Decision pending, see Open Thread #2 |
| `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_manifest.csv` | Source manifest used by the local-cache 400-pair probe | No |
| `images\Alloy_Class\outputs\probes\generic_description_v8_localcache_400_review.html` | HTML review output to inspect before deciding whether the v8 wording is final | No |
| `C:\Users\tbatson\My Programs\SQLPathFinder3\Python3\alloy\core\config.py` (external, not in this workspace) | Confirmed `ALLOY_API_KEY="demo-sandbox-key-12345"` is hardcoded as a plain string literal, used directly as the Bearer token — no env var setup is actually required | No |

## Bugs Encountered

### BUG-001: Windows MAX_PATH (260 char) exceeded on raw-image temp staging
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\tools\probe_generic_description_v1.py` (and inherited by v2-v7)
- **Root Cause:** Raw-image temp staging used a long UNC path; v1's first run failed all 40/40 pairs on Windows MAX_PATH limits
- **Fix Applied:** Changed the temp staging dir to a short local path: `C:\Users\tbatson\AppData\Local\Temp\generic_description_raw_temp`
- **Notes:** Same fix pattern should be assumed for any future probe script in this lineage

### BUG-002: `location_relative` invalid enum echo (v5)
- **Status:** Resolved (fixed in v6)
- **File(s):** `images\Alloy_Class\tools\probe_generic_description_v5.py`, `Particle_Descriptors_v6_canonical.txt`
- **Root Cause:** The enum list and its explanation were interleaved in one sentence, so the model echoed prose ("touches without crossing") instead of picking a valid enum word, on 1/40 cases
- **Fix Applied:** v6 separated the plain enum list from its explanation and added "answer must be exactly one of these four words." Confirmed 0/40 invalid after fix.
- **Notes:** See generalizable lesson under Key Decisions

### BUG-003: `coarse_shape` invalid enum echo (v6)
- **Status:** Resolved (fixed in v7)
- **File(s):** `images\Alloy_Class\tools\probe_generic_description_v6.py`, `Particle_Descriptors_v7_canonical.txt`
- **Root Cause:** Same root-cause pattern as BUG-002 — the model echoed the fine-flag name `shape_shard` (independently also true for that case) instead of a valid coarse-shape enum word, on 1/40 cases
- **Fix Applied:** v7 removed the colliding fine-flag names (`shape_shard`, and also `shape_rounded_edges`) entirely, AND added the same explicit "must be exactly one of these four words: circle, round, angular, clumped" constraint to `coarse_shape` as defense-in-depth. Confirmed 0/40 invalid for both fields after fix.
- **Notes:** See generalizable lesson under Key Decisions

### BUG-004: `submitFeedback()` JS null dereference on generic-description report
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\reporting\build_probe_html_report.py`
- **Root Cause:** Shared `submitFeedback()` JS in `_feedback_portal_assets()` did an unconditional `document.getElementById(\`agrees_${domId}\`).value` (and same for `corrected_${domId}`). After the generic-description report's feedback form was simplified to comment-only, those elements don't exist there, so `.value` on `null` threw a TypeError OUTSIDE the try/catch, silently killing every submission (no alert, no status update) even though the backend itself tested healthy via direct HTTP POST.
- **Fix Applied:** Optional chaining (`?.value || ''`) — backward compatible with the original probe report, which still has those fields.
- **Notes:** none

### Clarification (not a bug)
No `ALLOY_API_KEY` env var setup is actually required. `alloy/core/config.py` (external to this workspace, at `C:\Users\tbatson\My Programs\SQLPathFinder3\Python3\alloy\core\config.py`) hardcodes `ALLOY_API_KEY="demo-sandbox-key-12345"` as a plain string literal, used directly as the Bearer token.

## Excursions / Scope Creep Discovered
- Distribution/quality checks between prompt versions were done via small ad hoc throwaway scripts (`images\Alloy_Class\tools\_check_vN_*.py` pattern), written, run once, then deleted immediately after reporting stats. None should remain in the tree; if any do, they are leftover clutter from a possibly-missed cleanup round (a terminal display glitch earlier in the session may have caused one round to be missed) — worth a quick `dir` check by a future agent.
- BEEP tranche mechanics work (lot column, tranche_0005 backfill, misclassified-report handoff doc) — real work, but a separate track from this session's actual focus; see Secondary/Adjacent Context tables above. Do not conflate with the VLM pilot work when reading this log.

## Open Threads
- [ ] **THREAD-031 (highest priority)** — v8 substrate-relative texture calibration not yet wired into any prompt (see below)
- [ ] **THREAD-032** — Decision pending: how does the VLM generic-description pilot connect to the hand-labeled BEEP tranche ground truth? (see below)
- [ ] Confirm no leftover `_check_vN_*.py` throwaway scripts remain in `images\Alloy_Class\tools\`
- [ ] Confirm whether the v8 local-cache 400-pair report warrants any final prompt wording tweaks before wider use

### THREAD-031 detail — v8 substrate-relative texture calibration
The user proposed (documented as a `[CHANGE]` note under section 2a of
`images\Alloy_Class\Particle_Descriptors_v7_canonical.txt`, NOT YET wired into any prompt)
that `coarse_texture` (currently Smooth/Textured/Rough, judged as an absolute call) should
instead be calibrated RELATIVE to the SiO substrate's own visible texture wavelength in the
same image:
- texture comparable to the substrate's wavelength -> Textured
- texture coarser than the substrate's -> Rough
- texture finer than or absent relative to the substrate's -> Smooth

Next-step task for a future agent:
1. Read the `[CHANGE]` note in `Particle_Descriptors_v7_canonical.txt` section 2a
2. Draft an updated canonical spec (`Particle_Descriptors_v8_canonical.txt`) reflecting this substrate-relative calibration
3. Confirm with the user
4. Create `images\Alloy_Class\tools\probe_generic_description_v8.py` (copy v7.py's structure, update only `GENERIC_DESCRIPTION_PROMPT_V8`)
5. Run it over the SAME unchanged 40-case `outputs\probes\generic_description_pilot_manifest.csv`
6. Generate the HTML report via `build_generic_description_html_report.py`
7. Report distribution stats (especially watching whether this reduces any remaining ambiguity in `coarse_texture` judgments) the same way as v1-v7

### THREAD-032 detail — VLM labeling <-> hand-labeled BEEP connection
No implementation work was done on this thread this session — the user gave feedback/thinking
on direction only. The user is weighing three possible next directions, undecided:
- **(a)** Continue small-scale (40-case) prompt iteration on the generic-description pilot (e.g. the v8 texture change above)
- **(b)** Run the current/next settled prompt version (v7 or v8) over the SAME 500 cases that already have hand-applied BEEP-vs-SMALL_PARTICLE disposition labels (separate, pre-existing tranche-based system at `outputs\beep_evidence\beep_evidence_ground_truth.csv`, tranches 1-5, 143 BEEP / 357 SMALL_PARTICLE) — would let VLM structured morphology attributes be joined against real hand-applied labels to test whether any shape/texture pattern correlates with factory misclassifications. This is the primary agent-suggested next step for connecting the two tracks, but is UNIMPLEMENTED — no join, no analysis, no code written.
- **(c)** Scale directly to the full ~6,487-defect SMALL_PARTICLE population without further small-scale iteration

A future agent should ask the user which direction to pursue before starting new pilot-scale
or scale-up work. If direction (b) is chosen: the two datasets join on `wafer_key`+`defect_id`
(present in both `generic_description_pilot_manifest.csv`-style manifests and in
`outputs\beep_evidence\tranche_000N_cases.csv`/`beep_evidence_ground_truth.csv`), but the
40-case pilot manifest and the 500-case hand-labeled tranche population are currently two
DISJOINT/unrelated samples — no overlap is guaranteed or expected. Direction (b) would likely
require either resampling the VLM pilot over the hand-labeled 500 cases specifically, or a
fresh join/overlap check first.

## Key Decisions Made
- Phase 1 scope locked to open-ended description + exploratory structured attributes only; clustering method and Phase 3 "decided labels" prompt explicitly deferred, not attempted
- BEEP explicitly excluded from this VLM pilot's scope — separate, pre-existing manual disposition effort
- The 40-case pilot manifest was deliberately reused unchanged across all 7 prompt versions for direct apples-to-apples comparison — rejected resampling between versions
- v4's loosened circle-calibration guidance ("at most one subtle facet") was a considered experiment, later explicitly REVERTED in v5 back to strict "no facet or notch anywhere on the boundary" — do not re-loosen without explicit user sign-off
- `comparator_fit` and `texture_porous` fields removed in v4 (zero discriminating value — 100% "yes" / never fired across repeated runs) — rejected keeping them
- `flat` removed from `coarse_texture` in v6 (never fired 0/40 across v2-v5) — rejected keeping it
- v7's comparator-edge-following trigger for `texture_interior_layer` (renamed from `texture_layered`) was deliberately DROPPED, keeping only the defect's-own-outline-following trigger — a deliberate scope reduction confirmed by the user
- v7 prompt (3272 chars) exceeds the project's ~3000-char soft cap by ~9%, EXPLICITLY APPROVED by the user given the added precision
- **Generalizable lesson recorded for future prompt-engineering work:** field-name collisions between a coarse single-select's valid values and a fine boolean-flag's name (e.g. coarse value "shard" vs. flag `shape_shard`) cause a recurring VLM failure mode where the model echoes the flag name instead of a valid coarse enum value. Fix requires BOTH removing/renaming the colliding term AND adding an explicit "must be exactly one of these words" instruction to the coarse field. Separately, interleaving an enum list with its own explanatory prose in one block of prompt text risks the model echoing definition prose as if it were an answer — keep enum lists and their explanations structurally separate blocks in the prompt.
- Direction for connecting the VLM pilot to hand-labeled BEEP data (THREAD-032) explicitly NOT decided — agent must ask before proceeding

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\Particle_Descriptors_v7_canonical.txt` (section 2a `[CHANGE]` note — the v8 starting point)
- `images\Alloy_Class\tools\probe_generic_description_v7.py`
- `images\Alloy_Class\outputs\probes\generic_description_pilot_manifest.csv`
- `images\Alloy_Class\outputs\probes\generic_description_v7_pilot_feedback.csv` (latest reviewer feedback, in progress)
- `images\Alloy_Class\reporting\build_generic_description_html_report.py`

**Suggested starting prompt:**
> "Read the `[CHANGE]` note under section 2a of `images/Alloy_Class/Particle_Descriptors_v7_canonical.txt`. Draft `Particle_Descriptors_v8_canonical.txt` reflecting the substrate-relative texture calibration described there, confirm the spec with me, then wire it into a new `probe_generic_description_v8.py` (copied from v7.py's structure) and run it over the unchanged 40-case `generic_description_pilot_manifest.csv`. Also: before starting any new pilot-scale or scale-up work, ask me which of directions (a)/(b)/(c) in THREAD-032 I want to pursue for connecting this VLM pilot to the hand-labeled BEEP tranche data."

## Notes for Future Agent
- The 40-case manifest (`SMP_PILOT_001`-`040`) is a fixed comparison baseline across v1-v7 — do not resample it without a specific, stated reason.
- `Particle_Descriptors_v4_canonical.txt` is intentionally empty (editor undo/redo mishap; content moved forward into v5 instead of being restored). Leave it empty.
- All raw VLM image inputs are non-burned/raw images, downloaded via GAJT/SecureFTP, deleted immediately after each call — never persisted. Burned reference images shown in the HTML report are for human reviewer context only and are explicitly labeled as such.
- A pair is SKIPPED ENTIRELY (never falls back to burned images) if raw download fails — this is a deliberate divergence from `classify_phase1_batch.py`'s behavior, since raw images are required as VLM input for this track.
- `prompt_char_count=` is printed by every probe script — watch this against the ~3000-char soft cap when drafting v8.
- Read `generic_description_v7_pilot_feedback.csv` directly for the latest reviewer comments before drafting v8 — it was still being filled in at checkpoint time, don't assume it's complete.
- Do not conflate this session's content with the BEEP tranche mechanics work (lot column addition, tranche_0005 backfill, `HANDOFF_BEEP_MISCLASSIFIED_REPORT.md`) — that is real but secondary/adjacent, tracked separately, and mentioned here only as background.
- This log does not touch, reference for deletion, or otherwise modify [2026-09-02_001](2026-09-02_001_be-alloy-class-tranche-0007-misclassified-beep-checkpoint.md) — that log documents separate, legitimate tranche_0007 work and stands as-is.
