---
session_id: 2026-08-27_001
title: BEEP Lexicon V1/V2 Rewrite, Feedback Portal Rollout, and Strategic Pivot Tooling Inventory
date: 2026-08-27
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6 / 5 (mixed across sub-sessions)
triggered_by: manual-checkpoint
status: partial
original_goal: Test-fire image viewing on BMK_0036 and work through the v13 FN-plan passdown's Step 1 (categorize 21 known v13 false positives).
retroactive: true
logged_date: 2026-08-30
---

## Original Goal
Pick up the v13 describe-then-classify FN-plan passdown (`images\Alloy_Class\docs\iGPT_v13_FN_plan_passdown.md`)
and work through its proposed fix for the 21 known v13 false positives. This expanded over four
days (2026-08-27 through 2026-08-30) into: a v14 patch of the V11-derived prompt lineage, discovery
of a fundamental FP/FN trade-off that patching could not escape, a from-scratch minimal lexicon
rewrite (v1 -> v2) with a feedback-portal-integrated HTML review loop, and finally a strategic
pivot proposal (manual disposition + decoupled fine-bin VLM tagging) with a read-only tooling
inventory to inform it.

## Completed Tasks
- [x] Diagnosed and flagged a factual error in the passdown doc's own root-cause claim (Call 1 texts do not contain negative/no-evidence language for any of the 21 FP cases)
- [x] Built `stage_ab_prompt_tests_substrate_tier1_v14.json` and `probe_describe_then_classify_v14.py` implementing the passdown's VERDICT-line + hard-gate fix, plus a trench-tone-comparison ban and sunken-residual texture-correlation requirement
- [x] Added "Pathway 5 -- Mid-Span Trench Bridging" after user-guided visual review of BMK_0029
- [x] Diagnosed the "boundary ownership" root cause (model can't distinguish a distorted etched-feature boundary from a particle's own outline) across ISL Pathway 2/4, `evidence_check_boundary_conformance`, and Pathway 5; applied user-supplied corrective language to all four locations
- [x] Fixed a self-inflicted duplicate/orphaned function body introduced during a multi-file-edit, same-turn
- [x] Ran full FN+control+FP21 regression after each patch round; confirmed a persistent FP/FN see-saw (tightening evidence criteria for one side worsens the other) across the entire V11-derived lineage
- [x] Authored `PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md` describing the missing generic scoring/HTML contract across the two existing raw-output lineages
- [x] Used the generic scorer/HTML tooling (built by a different agent session per that gap doc) end-to-end on real data
- [x] Authored the fresh, minimal `BEEP_Evidence copy.txt` plain-lexicon spec collaboratively with the user (user wrote the file; I gave iterative feedback, no edits)
- [x] Built `probe_beep_lexicon_v1.py` (single-call architecture, 6,557-char prompt vs. V11 lineage's 19,047) and validated on the 10-case set then the full 31-case set (TP 3, TN 16, FP 10, FN 2; FP rate 0.385)
- [x] Regenerated the v1 HTML report with the feedback-portal widget (built by a different specialized agent), started the backend, opened it in-browser
- [x] Read and synthesized 15 pieces of user feedback submitted through the portal on the v1 run into two focus themes (comparator/via shadow mistaken for sunken residual; boundary-conformance definition gaps)
- [x] Drafted suggested lexicon wording for both themes verbally (no file edits); user incorporated their own wording into `BEEP_Evidence copy 2.txt`
- [x] Built `probe_beep_lexicon_v2.py` (7,531-char prompt), ran on the same 31-case set, merged/scored (TP 3, TN 12, FP 14, FN 2; FP rate 0.538 -- worse than v1)
- [x] Restarted the feedback-portal backend against the v2 feedback CSV, regenerated the v2 HTML report, opened it in-browser
- [x] Validated the 08-30 strategic-pivot reasoning against session evidence; did a read-only audit of `BE_QUERY_FILES\*.py` for existing chamber/PM-counter metadata
- [x] Authored `TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` (inventory-only, no plan, per explicit user instruction)
- [ ] Diagnose why v1 -> v2 made FP rate worse (not started)
- [ ] User review of the v2 HTML report / portal feedback (not yet done as of session end)
- [ ] Decide whether to proceed with the two-track strategic pivot (explicitly deferred pending user confirmation)

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v14.json` | Created | Doc-only config for the v14 patch of the V11-derived prompt lineage |
| `images\Alloy_Class\tools\probe_describe_then_classify_v14.py` | Created, then Modified (multiple rounds) | VERDICT-line/hard-gate fix; trench-tone ban; sunken-residual texture correlation; Pathway 5 (mid-span bridging); boundary-ownership rewrites of Pathway 2/4/SOURCE DISCRIMINATION/`evidence_check_boundary_conformance`/Pathway 5/Pathway 1/Pathway 3 |
| `images\Alloy_Class\docs\PROBE_OUTPUT_SCORING_AND_HTML_REPORT_GAP.md` | Created | Documents the two raw-output lineages and proposes the generic normalized contract |
| `images\Alloy_Class\tools\normalize_probe_output.py` | Created (different agent, per my handoff spec) | Normalizes both raw-output lineages into the generic contract |
| `images\Alloy_Class\tools\score_probe_run.py` | Created (different agent) | Generic scorer for the normalized contract |
| `images\Alloy_Class\reporting\build_probe_html_report.py` | Created (different agent) | Generic HTML report builder for any probe/run output |
| `images\Alloy_Class\docs\HANDOFF_PROBE_SCORING_AND_HTML_REPORTING.md` | Created (different agent) | Documents the scoring/HTML tooling build |
| `images\Alloy_Class\tools\probe_beep_lexicon_v1.py` | Created | Fresh single-call architecture translating `BEEP_Evidence copy.txt` into `LEXICON_PROMPT_V1` (6,557 chars); imports `_pair_paths`/test-case lists from `probe_describe_then_classify_v14.py` (deliberate deviation from that script's duplicate-don't-import convention) |
| `images\Alloy_Class\tools\probe_beep_lexicon_v2.py` | Created | `LEXICON_PROMPT_V2` (7,531 chars) translating `BEEP_Evidence copy 2.txt`; same architecture as v1 for controlled comparison |
| `images\Alloy_Class\docs\HANDOFF_HTML_FEEDBACK_PORTAL_INTEGRATION.md` | Created (original spec by me), later appended (different agent) | Original handoff spec for the feedback-portal integration; different agent appended an "implemented" status section |
| `images\Alloy_Class\reporting\feedback_portal\` (backend/main.py, run_portal.cmd, run_portal.ps1, requirements.txt, README.txt, data/) | Created (different specialized agent) | Local Flask backend + per-case feedback forms embedded in the HTML report; CSV schema `case_id/reviewer/submitted_at_utc/agrees_with_vlm/corrected_class/comment/run_id` |
| `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` | Created | Read-only tooling/methods inventory to inform the 08-30 strategic pivot decision; deliberately contains no plan or recommendations |
| `images\Alloy_Class\BEEP_Evidence copy.txt` | Created (by user, not agent) | Fresh, minimal, plain-lexicon disposition spec; I gave iterative feedback on drafts only |
| `images\Alloy_Class\BEEP_Evidence copy 2.txt` | Created (by user, not agent) | v2 lexicon incorporating shadow/boundary-conformance/ISL-continuity fixes from user's own wording |
| `images\Alloy_Class\outputs\probes\*.jsonl` and `images\Alloy_Class\outputs\probes\scored\*\` (notably `beep_lexicon_v1_20260828_full31\`, `beep_lexicon_v2_20260829_full31\`) | Created | Numerous run outputs: scored CSVs/JSONL, `probe_score_summary.json`, HTML reports for every v14/v1/v2 test batch this session |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\docs\iGPT_v13_FN_plan_passdown.md` | Session starting point; Step 1 of its plan was worked through | No |
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v11.json`, `v12.json`, `v13.json` | Compared against v14 patch and lexicon rewrite | No |
| `images\Alloy_Class\tools\probe_describe_then_classify.py` | Original v13 probe script, precursor to v14 | No |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Production runner; explicitly never modified this session | No |
| `images\Alloy_Class\outputs\raw_runs\benchmark_particle25_v13_describe_then_classify_rerun2\` | Source of the 21 known-FP Call 1 texts used to diagnose the passdown doc's factual error | No |
| `images\Alloy_Class\artifacts\benchmark_candidates_14day.csv`, `benchmark_pairs_full145.csv` | GT source (`adjudicated_coarse_class`) for all scoring this session | No |
| `images\Alloy_Class\docs\v12_post_mortem.md` | Precedent for the FP/FN trade-off tension, referenced when flagging item 9's regression | Possibly -- may need a new addendum documenting this session's parallel finding |
| `images\Alloy_Class\config\inset_surface_line_modification.md` | Reviewed for ISL modification history | No |
| `images\Alloy_Class\reporting\build_stage_ab_html_report.py` | Reviewed, precursor to the new generic `build_probe_html_report.py` | No |
| `images\Alloy_Class\tools\build_benchmark_candidates.py`, `reporting\benchmark_review_14day.html` | Reviewed for context | No |
| `images\Alloy_Class\tools\score_benchmark_run.py`, `images\Alloy_Class\tools\run_benchmark_vlm.py` | Reviewed for context; not modified | No |
| `BE_QUERY_FILES\DEFECT_COORDINATES_QUERY.py`, `BE_QUERY_FILES\surf_scan_coordinates.py`, `BE_QUERY_FILES\surf_scan_elwc_pm_pilot.py`, `BE_QUERY_FILES\surf_scan_elwc_pm_stage_backfill.py` | Read-only audit for existing chamber/PM-counter metadata (08-30 pivot question) | Yes -- see THREAD-022, THREAD-023 |
| Various `images\defects\*` image pairs (e.g. BMK_0036, BMK_0029, BMK_0011) | Direct visual verification during v14 pathway design | No |

## Bugs Encountered
### BUG-001: Passdown doc factual error re: Call 1 "no blocked etch evidence" language
- **Status:** Resolved (flagged to user, not a code bug)
- **File(s):** `images\Alloy_Class\docs\iGPT_v13_FN_plan_passdown.md`
- **Root Cause:** The passdown doc's diagnosis claimed Call 1 texts for confabulation cases explicitly state "no blocked etch evidence." Actual data showed 0 of 21 FP Call 1 texts contained negative/no-evidence language; all 21 contained tonal-fill-style affirmative language.
- **Fix Applied:** Flagged to user before proceeding; documented in repo memory `alloy_class_v13_v14_fp_diagnosis.md`.
- **Notes:** This reframed the whole v14 patch approach away from what the passdown doc originally proposed.

### BUG-002: Orphaned/duplicate `_add_boundary_ownership_check` function body
- **Status:** Resolved (same turn)
- **File(s):** `images\Alloy_Class\tools\probe_describe_then_classify_v14.py`
- **Root Cause:** A multi-file-edit operation left a duplicate function body during the boundary-ownership rewrite.
- **Fix Applied:** Caught and fixed same-turn; verified via `get_errors` and an offline dry-run script.
- **Notes:** Self-inflicted, fully resolved.

### BUG-003: PowerShell UNC-path `$`-escaping garble
- **Status:** Resolved (workaround only, not a real fix)
- **File(s):** N/A (terminal commands referencing paths containing `ORAnalysis$`)
- **Root Cause:** The `$` in `ORAnalysis$` triggers PowerShell variable-expansion parsing in certain command contexts.
- **Fix Applied:** Workaround is to single-quote all such paths, or write Python to a temp `.py` file and run with `python file.py` instead of `python -c "..."`.
- **Notes:** Recurring workspace-wide gotcha; documented in `TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md`.

### BUG-004: Alloy VLM truncated/empty responses at 1800-token budget
- **Status:** Open (workaround only)
- **File(s):** `images\Alloy_Class\tools\probe_beep_lexicon_v1.py`, `probe_beep_lexicon_v2.py`
- **Root Cause:** Not diagnosed. 2 of 31 cases failed this way in the v1 run, 6 of 31 in the v2 run.
- **Fix Applied:** Manual retry of the specific failed `case_id`(s) at a higher budget (2400 worked both times).
- **Notes:** See THREAD-024.

### BUG-005: Model non-determinism on borderline/duplicate test cases
- **Status:** Open
- **File(s):** N/A (model behavior)
- **Root Cause:** Identical image pair, prompt, and model produced different verdicts across duplicate test entries within the same run batch (`BMK_0008`, `BMK_0011`).
- **Fix Applied:** None -- accepted as sampling variance.
- **Notes:** See THREAD-025.

## Excursions / Scope Creep Discovered
- Item 10 (scoring/HTML gap doc) and item 16 (feedback-portal integration) both spawned separate agent-built tooling efforts outside this session's direct edits, but this session used and validated both extensively.
- The prompt-bloat/vocabulary-over-indexing observation (V11 lineage grew from 11,252 to 19,047 chars with ~28 repeated restatements of "ownership") motivated abandoning the entire V11 lineage rather than continuing to patch it -- a significant scope pivot from the original passdown-following goal.

## Open Threads
- [ ] THREAD-018 -- Fundamental FP/FN trade-off unresolved across both prompt lineages (V11-derived and from-scratch lexicon)
- [ ] THREAD-019 -- v1 -> v2 lexicon FP-rate regression (0.385 -> 0.538) not yet case-level diagnosed
- [ ] THREAD-020 -- User has not yet reviewed the v2 HTML report or submitted portal feedback on it
- [ ] THREAD-021 -- Strategic pivot decision (manual disposition + decoupled fine-bin VLM tagging) pending user confirmation before any plan is drafted
- [ ] THREAD-022 -- Litho-scanner metadata correlation unconfirmed; no existing join found in `BE_QUERY_FILES`
- [ ] THREAD-023 -- PM-counter part-installation granularity unconfirmed (cumulative cycle counts vs. discrete part-swap events)
- [ ] THREAD-024 -- Alloy VLM truncated/empty responses at 1800-token budget (workaround, not root-caused)
- [ ] THREAD-025 -- Model non-determinism on borderline/duplicate test cases

## Key Decisions Made
- Never modify `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` (the production runner) during any of this session's experimentation -- all changes stayed in throwaway probe scripts under `tools\`.
- Ground truth is always `adjudicated_coarse_class` from `benchmark_candidates_14day.csv`, never `factory_class_label` -- reconfirmed multiple times.
- Abandoned further incremental patching of the V11-derived prompt lineage in favor of a from-scratch, minimal, user-authored plain-lexicon specification and single-call prompt architecture, after prompt bloat (19,047 chars, ~28 repeated restatements) and vocabulary over-indexing (echoing illustrative words like "parallelogram" out of context) were identified as compounding failure modes.
- The generic scorer + HTML report pipeline (`normalize_probe_output.py`, `score_probe_run.py`, `build_probe_html_report.py`) is now the one path for scoring/visualizing ANY future run or probe script's output, regardless of model-call architecture.
- Feedback submitted through the feedback portal lands in a CSV separate from the scorer's own `probe_scored_rows.csv` output (immutability convention).
- Explicitly decided NOT to draft an actual plan for the fine-bin-tagging/manual-disposition pivot yet -- only a tooling inventory document was produced, per repeated user instruction.
- Explicitly decided NOT to dig deeper into PM-counter/litho-scanner metadata beyond one read-only audit.
- Explicitly decided NOT to continue iterating on the v2 lexicon prompt (i.e., no v3 attempted) without the user reviewing the v2 regression and/or giving portal feedback first.

## Notes for Future Agent
### Things that look like bugs but are intentional -- do not "fix"
- In `probe_beep_lexicon_v1.py` and `v2.py`, `call1_observation` is always an empty string and the entire single-call response is stored under `call2_parsed`/`call2_raw_text` instead. Intentional: these are single-call architectures, and this field-reuse keeps compatibility with the existing Lineage B JSON shape expected by `normalize_probe_output.py` / `score_probe_run.py` / `build_probe_html_report.py`.
- `BMK_0008` and `BMK_0011` each appear twice in `TEST_CASES` (once under `particle_control`/`edge_case_control`, once under `fp21_case`). Intentional dual-listing for same-batch repeatability spot-checks, not a duplicate to remove.

### Suggested re-entry prompts (from the source narrative)
1. **THREAD-019 re-entry:** "We ran `tools\probe_beep_lexicon_v2.py` on the same 31-case set as v1 and got FP rate 0.538 (worse than v1's 0.385) with FN rate unchanged at 0.4. Nobody has looked into which specific cases flipped from correct to incorrect between v1 and v2, or why. Compare `outputs\probes\scored\beep_lexicon_v1_20260828_full31\` against `outputs\probes\scored\beep_lexicon_v2_20260829_full31\` case-by-case and diagnose root cause before making further lexicon changes."
2. **THREAD-020 re-entry:** "Check `outputs\probes\scored\beep_lexicon_v2_20260829_full31\probe_review_feedback.csv` for new submissions before proceeding with anything lexicon-related."
3. **THREAD-021 re-entry:** "The user was considering pivoting from binary pre/post-etch VLM disposition toward two decoupled tracks: (a) manual disposition performed by the user personally via the existing HTML+feedback-portal tooling, focused on post-etch (true particle) populations, and (b) a separate VLM fine-bin multi-label tagging effort (example labels: Occlusion, Morphology, number of continuous defects, Is a sphere) across the full ~6,487-defect SMALL_PARTICLE population, to support statistical correlation against process drivers (chamber, PM/part-installation history, litho scanner) and to build a case for ruling out certain particle morphologies from pre-etch consideration entirely. See `images\Alloy_Class\docs\TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md` for the current-state tooling inventory prepared to inform this decision. The user had NOT yet asked for an actual plan to be drafted as of this session's end -- confirm before proceeding to plan-writing or implementation."
4. **THREAD-022 re-entry:** "A quick read-only audit of `BE_QUERY_FILES\*.py` found no existing join between BE/etch-chamber defect records and litho-scanner identity. If the 'incoming litho scanner' correlation axis from the tagging plan is pursued, this will likely need new data plumbing."
5. **THREAD-023 re-entry:** "`BE_QUERY_FILES\surf_scan_elwc_pm_pilot.py` and `surf_scan_elwc_pm_stage_backfill.py` track PM mechanical-cycle counters per chamber over time, but it was not confirmed whether this data also captures discrete part-swap/installation events vs. only cumulative cycle counts. Needs closer inspection if the 'chambers with this pilot part installed' correlation axis is pursued."

### Other notes
- This log was written retroactively on 2026-08-30 from a full narrative summary (no live conversation history available); see frontmatter `retroactive`/`logged_date` fields.
- The session spanned 2026-08-27 through 2026-08-30 continuously; only one session log is being created to cover the whole span per user instruction, rather than one log per calendar day.
- `images\Alloy_Class\docs\v12_post_mortem.md` already documents an analogous historical FP/FN two-sided-effect finding for V12 -- THREAD-018 is effectively a recurrence of that same unresolved tension in a new lineage, not a new phenomenon.
