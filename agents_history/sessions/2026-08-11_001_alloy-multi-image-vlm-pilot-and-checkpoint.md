---
session_id: 2026-08-11_001
title: Alloy Multi-Image VLM Pilot and Checkpoint
date: 2026-08-11
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: GPT-5.4 mini
triggered_by: manual-checkpoint
status: complete
original_goal: Validate Doruk's multi-image vision payload update by running a small Alloy benchmark pilot and record the result in the session history.
---

## Original Goal
Validate whether the Alloy vision endpoint could accept multi-image submissions using the updated `images` payload shape, then confirm the benchmark harness could exercise the path on a small BF/DF pilot pair.

---

## Completed Tasks

- [x] Reviewed the logging rules, index, template, open threads, and file map before writing the checkpoint
- [x] Confirmed the benchmark runner originally used the single-image helper path and then added a benchmark-only multi-image Stage B submission mode
- [x] Verified the installed `alloy.core.llm.image()` helper is single-image only
- [x] Probed the lower-level vision endpoint directly with `images: [b64, b64]` and confirmed the backend accepts multi-image payloads
- [x] Ran a one-pair pilot on `260530_1734_D609178_002_SMP_8M6CL_1251_2.jpg` and `_3.jpg`
- [x] Verified the pilot completed successfully and returned structured Stage A / Stage B outputs for both images
- [x] Closed THREAD-005 by confirming the multi-image Stage B path now works for the texture-reference use case

---

## Files Modified

| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Modified | Added direct multi-image Stage B submission path using `images: [b64, b64]` and kept the single-image helper path as fallback |
| `agents_history\sessions\2026-08-11_001_alloy-multi-image-vlm-pilot-and-checkpoint.md` | Created | Formal checkpoint log for the multi-image pilot |

---

## Files Affected (referenced but not modified)

| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json` | Used as the benchmark prompt/config for the pilot run | No |
| `images\Alloy_Class\artifacts\benchmark_pairs_nbc_focus52.csv` | Background benchmark context from the prior session | No |
| `images\Alloy_Class\artifacts\benchmark_v1_frozen.csv` | Referenced for the surrounding benchmark workflow | No |
| `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py` | Primary harness under test for multi-image support | Yes |

---

## Bugs Encountered

### BUG-001: SDK convenience wrapper rejected list input
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- **Root Cause:** The installed `alloy.core.llm.image()` helper accepts only a single `image: str`, so passing a list raised a `TypeError` before the request reached the backend.
- **Fix Applied:** Switched multi-image submissions to the lower-level vision request path with `images: [base64, base64]` while preserving the existing single-image helper for legacy calls.
- **Notes:** The pilot confirmed that Doruk's payload shape is supported by the backend even though the helper wrapper has not been updated.

---

## Excursions / Scope Creep Discovered

- Checked the installed Alloy package internals to verify the real helper signature before changing the harness further
- Confirmed the backend payload shape directly rather than assuming the convenience wrapper had been updated

---

## Open Threads

- [ ] **THREAD-006** — BC check detection gap: `bc` fires on only 6/32 nbc/possible_beep rows; prompt language still needs refinement
- [ ] **THREAD-007** — Stage A confounder language may suppress `isl` detection in Stage B
- [ ] **THREAD-008** — `sr` detection ceiling remains deferred
- [ ] **THREAD-009** — BMK_0037 relabeling question remains pending user review

---

## Key Decisions Made

- The benchmark harness should use the direct vision endpoint payload with `images` for multi-image experiments instead of waiting on the SDK wrapper to gain that capability.
- The first pilot should stay benchmark-only and small; the one-pair BF/DF run was sufficient to validate the endpoint shape.
- The single-image helper path should remain in place for backward compatibility and for any future fallback testing.

---

## Recommended Re-Entry

**Load these files for context:**
- `images\Alloy_Class\reporting\run_stage_ab_prompt_tests.py`
- `images\Alloy_Class\config\stage_ab_prompt_tests_substrate_tier1_v3.json`
- `agents_history\open_threads.md`

**Suggested starting prompt:**
> "Review `images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py` and extend the multi-image pilot from one BF/DF pair to a small batch of pairs, then compare the output quality and token usage against the single-image baseline."

---

## Notes for Future Agent

- The successful pilot used `C:\temp\alloy_multi_image_pilot\inputs` with one BF/DF pair copied from the benchmark inputs folder.
- The backend accepted `images: [base64, base64]` and returned a normal structured response.
- The direct payload path is the authoritative multi-image route for now; the SDK convenience wrapper is still single-image only.