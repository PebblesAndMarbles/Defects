---
session_id: 2026-09-10_001
title: BOST Enrichment Registry Pilot (Steps 1-3) and Aug 28 Coverage Escalation Checkpoint
date: 2026-09-10
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 5
triggered_by: manual-checkpoint
status: partial
original_goal: Scope and pilot a BOST enrichment registry (one wide column per process definition) for 8M5CL/8M6CL wafers across the 10 known FULL_FLOW_ALIASES, starting from a small recent-wafer sample and scaling the lookback window, then investigate a suspicious per-wafer coverage gap that surfaced during validation.
---

## Original Goal
Continue the design work already captured in `BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md` and
`BOST\BOST_DefectQuery_Plan.md` by actually piloting the registry query against BOST: start with a
handful of recent M5/M6 wafers pulled from the production wafer CSV, confirm the registry shape
(which `DEFINITION_NAME`s come back per alias), then scale the lookback window and build a wide
per-wafer table with one column per process definition. Along the way, the user flagged a
specific wafer with suspiciously sparse coverage, which turned into a real investigation of a
hard cutoff date affecting most process definitions.

## Completed Tasks
- [x] Reviewed `BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md`, `BOST\BOST_DefectQuery_Plan.md`,
  `BOST\adhoc_bost_gate_rollout.py`, and `BOST\sDTT_bost_process_family_explore.py` and proposed a
  scoping plan (small recent sample first, then scale lookback).
- [x] Confirmed production input is `outputs\wafer\8M5CL_8M6CL_EXTENDED.csv` (full history,
  12,276 rows, 2025-01-01-present) — not the `_60DAY` variant used by the earlier
  `adhoc_bost_gate_rollout.py` pilot. Enriched copies write to a new `BOST\registry\` subdirectory,
  not back into `outputs\wafer\`.
- [x] Step 1 (`BOST\step1_recent_wafer_registry_pilot.py`): pulled 10 most-recent wafers (5 per
  layer) and queried BOST for the 10 `FULL_FLOW_ALIASES`, reusing them from
  `adhoc_bost_gate_rollout.py` via import rather than redefining. Only 2 distinct
  `DEFINITION_NAME`s came back (`DUV_OPC`, `MX_HM_CLN`); 6 of 10 aliases returned nothing.
- [x] Ran an unrestricted diagnostic query (no trigger filter, no `IS_LATEST`/`IS_ACTIVE` filter)
  against the same 10 wafers and confirmed this was NOT a query bug — those wafers genuinely have
  zero rows for the missing aliases at any filter setting.
- [x] Step 2 (`BOST\step2_14day_lookback_pilot.py`): scaled to a 14-day lookback (285 unique
  wafer/layer keys). All 10 aliases returned rows; 49 distinct alias/definition combos, 25
  distinct `DEFINITION_NAME`s, confirming registry shape grows with sample size as expected.
- [x] Investigated and confirmed the existing per-row `LAYER`-derivation/pivot approach already
  handles layer-asymmetric definitions correctly (e.g. a definition present only under the M6
  alias only populates that wafer's `8M6CL` row).
- [x] Found and fixed a real wide-table design problem: 61 `(LOT, WAFER, LAYER, DEFINITION_NAME)`
  groups had more than one distinct `PROC_STRING_VALUE` because the same `DEFINITION_NAME` can be
  shared by two different steps within one layer (e.g. `EQUIP:BARC_TBF_LPCLEAN:LI-TBEbc` used by
  both `SIARC_DEP` and `CHM_DEP`). Fixed by deriving a layer-agnostic `STEP` token from each alias
  and keying wide columns on `(STEP, DEFINITION_NAME)` instead of `DEFINITION_NAME` alone —
  validated 0 collisions.
- [x] Step 3 (`BOST\step3_wide_table_build.py`): built the final wide table using the finalized
  column-naming convention `{STEP}_{SANITIZED_DEFINITION_CORE}` (strips leading `TYPE:` and
  trailing `:MODULE` from `DEFINITION_NAME`). Confirmed 0 collisions, 25 final columns at 14-day
  scope.
- [x] Investigated a specific wafer (`HP1SJ019JKF1`, 8M5CL) flagged by the user as suspiciously
  sparse (only `HM_CLN_MX_HM_CLN` and `SED_DUV_OPC` populated). Found nearly every `EQUIP:*`/
  `PROCESS:*` definition (everything except `DUV_OPC` and `MX_HM_CLN`) has a hard, uniform
  last-observed `INSPECT_TIME` cutoff of exactly `2026-08-28 13:32:41` across ~20 definitions and
  multiple steps/modules.
- [x] Compared against Dave Gaibler's `decoder_utilities_rev1.py` (vendored at
  `dev\idealapex\core_support\decoder_utilities_rev1.py`). Tested his `initial_run_completed='Y'`
  fallback-union logic and his `B_CFG_PROCESS_DEFN_FAMILY_ATTR` `definition_type='Universal Process
  Label'` filter against real BOST metadata. Ruled out the backfill-lag/version explanation
  (current versions already have `INITIAL_RUN_COMPLETED='Y'`). Found the affected definitions are
  typed `'Treatment Rule'`/`'Other'` (vs. `MX_HM_CLN`'s `'Universal Process Label'`) — a leading but
  explicitly **unconfirmed** theory that these are time-boxed engineering-investigation/
  consumable-tracking rules with a bounded active window, not a data/query defect.
- [x] User is escalating the Aug 28 coverage question to BOST DB owners rather than accepting the
  Treatment Rule theory as settled.
- [x] Updated `BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md` with a new "## 5. Current status / handoff
  (as of 2026-09-10)" section covering the pilot progression, the column-naming decision and its
  rationale (including the 61-collision finding), the Aug 28 investigation framed as
  escalated/unconfirmed, a diagnostic script inventory, and open items.
- [ ] User stated they will separately enrich other items across the same 10 full-flow aliases —
  not started in this conversation.

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `BOST\step1_recent_wafer_registry_pilot.py` | Created | Step 1: 10 most-recent wafers (5/layer), queries 10 `FULL_FLOW_ALIASES` reused from `adhoc_bost_gate_rollout.py` |
| `BOST\step2_14day_lookback_pilot.py` | Created | Step 2: 14-day lookback, 285 unique wafer/layer keys, 49 alias/definition combos, 25 distinct `DEFINITION_NAME`s |
| `BOST\step3_wide_table_build.py` | Created | Step 3: final wide table, keyed on `(STEP, DEFINITION_NAME)`, column format `{STEP}_{SANITIZED_DEFINITION_CORE}`, 25 columns, 0 collisions |
| `BOST\registry\diag_dave_decoder_comparison.py` | Created | Compares Dave Gaibler's `decoder_sql` filters (`initial_run_completed`, `definition_type`) against real BOST metadata; still present at this path |
| `BOST\archive\old_diag_scripts\diag_step1_hm_etch_check.py` | Created, later archived | Unrestricted diagnostic confirming the 6 missing aliases genuinely have zero rows for the Step 1 sample — moved here by a later parallel session (see Excursions) |
| `BOST\archive\old_diag_scripts\diag_definition_date_ranges.py` | Created, later archived | Found the uniform `2026-08-28 13:32:41` last-observed cutoff across ~20 definitions — moved here by a later parallel session |
| `BOST\archive\old_diag_scripts\diag_definition_last_update.py` | Created, later archived | Known dead end (BUG-001, ORA-00904) — moved here by a later parallel session |
| `BOST\registry\` (step1/step2/step3 output CSVs) | Created | Output artifacts from Steps 1-3; the registry folder now carries later date-stamped (`_20260909`) file names from a subsequent parallel session's reorganization — see Excursions |
| `BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md` | Modified | Added "## 5. Current status / handoff (as of 2026-09-10)" section |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BOST\BOST_DefectQuery_Plan.md` | Reviewed for alias/layer reference this plan extends | No |
| `BOST\adhoc_bost_gate_rollout.py` | Source of the 10 `FULL_FLOW_ALIASES`, reused via import | No |
| `BOST\sDTT_bost_process_family_explore.py` | Reviewed as proven tooling reference | No |
| `outputs\wafer\8M5CL_8M6CL_EXTENDED.csv` | Production input source for wafer sampling (12,276 rows) | No |
| `dev\idealapex\core_support\decoder_utilities_rev1.py` | Compared `decoder_sql` filter logic against real BOST metadata | No |
| `BOST\archive\old_diag_scripts\` | Confirmed this conversation's 3 diagnostic scripts were archived here, not lost | No — just note new location |
| `BOST\registry\` (`alias_operation_registry.csv`, `definition_registry_process_defn.csv`, `definition_registry_treatment_rules.csv`, `step4_treatment_rules_pilot.py`, `diag_track_a_vs_track_b.py`), `BOST\docs\`, `BOST\get_generic_decoder_client.md`, `BOST\20260827_NELSON_BOST.md` | Discovered in end-of-session directory listing; **not produced by this conversation** — appears to be a separate, currently un-logged parallel session ("BOST Enrichment Registry — Dual-Track Implementation", Process Defn + Treatment Rules) | Yes — needs its own session log (THREAD-034) |
| `WDS\APEX_ENTITY\` (numbered scripts `01`-`10`, `APEX_ENTITY_ENRICHMENT_HANDOFF.md`, `README.md`, `artifacts\`) | Discovered in end-of-session directory listing; **not produced by this conversation** — appears to be a separate, currently un-logged parallel session ("APEX_ENTITY Enrichment") | Yes — needs its own session log (THREAD-034) |

## Bugs Encountered
### BUG-001: `diag_definition_last_update.py` — ORA-00904 invalid identifier
- **Status:** Resolved (confirmed dead end)
- **File(s):** `BOST\archive\old_diag_scripts\diag_definition_last_update.py`
- **Root Cause:** Script queried `LAST_UPDATE_DATE`/`CREATE_DATE` columns on `B_CFG_PROCESS_DEFN`,
  which do not exist in that table's schema.
- **Fix Applied:** None — confirmed as a dead end and abandoned in favor of
  `diag_definition_date_ranges.py`, which uses `INSPECT_TIME` from the wafer-level data instead.
- **Notes:** Do not retry this column combination against `B_CFG_PROCESS_DEFN`.

### BUG-002: Wide-table column collisions from shared `DEFINITION_NAME` across steps
- **Status:** Resolved
- **File(s):** `BOST\step3_wide_table_build.py`
- **Root Cause:** The same `DEFINITION_NAME` can be attached to two different steps within the same
  layer (e.g. `EQUIP:BARC_TBF_LPCLEAN:LI-TBEbc` used by both `SIARC_DEP` and `CHM_DEP` with
  different values), causing 61 `(LOT, WAFER, LAYER, DEFINITION_NAME)` groups to have more than one
  distinct `PROC_STRING_VALUE`.
- **Fix Applied:** Derived a layer-agnostic `STEP` token from each alias (stripping the `8M5`/`8M6`
  segment) and keyed wide columns on `(STEP, DEFINITION_NAME)` instead of `DEFINITION_NAME` alone.
  Validated 0 collisions at 14-day scope.
- **Notes:** Final column-naming convention is `{STEP}_{SANITIZED_DEFINITION_CORE}`.

## Excursions / Scope Creep Discovered
- End-of-session directory listings of `BOST\` and `BOST\registry\` show files not created within
  this conversation: `BOST\20260827_NELSON_BOST.md`, `BOST\alias_operation_registry.csv`,
  `BOST\definition_registry_process_defn.csv`, `BOST\definition_registry_treatment_rules.csv`,
  `BOST\step4_treatment_rules_pilot.py`, `BOST\docs\`, `BOST\archive\`,
  `BOST\get_generic_decoder_client.md`, `BOST\registry\diag_track_a_vs_track_b.py`. Session-store
  search confirms these belong to a separate session titled roughly "BOST Enrichment Registry —
  Dual-Track Implementation (Process Defn + Treatment Rules)".
- A whole separate `WDS\APEX_ENTITY\` enrichment effort (numbered scripts `01`-`10`,
  `APEX_ENTITY_ENRICHMENT_HANDOFF.md`, `README.md`) also exists and was not touched by this
  conversation. Session-store search confirms this belongs to a separate "APEX_ENTITY Enrichment"
  scoping/build session.
- Both of the above are currently **un-logged** in `agents_history` — see THREAD-034.
- Confirmed (not a discrepancy, just reorganization): the 3 diagnostic scripts this conversation
  created directly in `BOST\registry\` were subsequently moved to
  `BOST\archive\old_diag_scripts\` by the dual-track session above; no data was lost.

## Open Threads
- [ ] THREAD-032 — Aug 28 coverage cutoff escalated to BOST DB owners; awaiting response
- [ ] THREAD-033 — Registry open items (DEFINITION_TYPE column, (STEP/ALIAS, DEFINITION_NAME) keying, hold STATUS logic)
- [ ] THREAD-034 — Reconcile/log the parallel BOST dual-track and WDS/APEX_ENTITY sessions into agents_history
- [ ] THREAD-035 — User's planned separate enrichment work across the same 10 full-flow aliases (not started)

## Key Decisions Made
- Production input for the registry pilot is `outputs\wafer\8M5CL_8M6CL_EXTENDED.csv` (full
  history), not the `_60DAY` variant used by the earlier `adhoc_bost_gate_rollout.py` pilot.
- Enriched copies are written to a new `BOST\registry\` subdirectory, not back into
  `outputs\wafer\`.
- Reused `FULL_FLOW_ALIASES` from `adhoc_bost_gate_rollout.py` via module import rather than
  redefining the list.
- Wide table is keyed on `(STEP, DEFINITION_NAME)`, not `DEFINITION_NAME` alone, to avoid
  cross-step column collisions (see BUG-002).
- Column naming convention finalized as `{STEP}_{SANITIZED_DEFINITION_CORE}` (user's requested
  format), replacing an earlier `{STEP}__{DEF}_VALUE` proposal.
- The Aug 28 coverage cutoff is explicitly **not** settled as "rules expired" — it is framed as
  escalated/unconfirmed in the handoff doc per the user's explicit direction, since they remain
  skeptical of the Treatment Rule theory.
- Rejected (for now): building `STATUS=RETIRED`/`FIRST_SEEN`/`LAST_SEEN` logic against the Aug 28
  boundary until BOST DB owners respond.

## Recommended Re-Entry
**Load these files for context:**
- `BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md` (section 5, "Current status / handoff")
- `BOST\step3_wide_table_build.py`
- `BOST\registry\diag_dave_decoder_comparison.py`
- `BOST\archive\old_diag_scripts\diag_definition_date_ranges.py`

**Suggested starting prompt:**
> "Check whether BOST DB owners have responded on the Aug 28 coverage-cutoff escalation
> (`BOST\BOST_ENRICHMENT_REGISTRY_PLAN.md` section 5). If confirmed as time-boxed Treatment
> Rules, add DEFINITION_TYPE to registry Table B and design STATUS=RETIRED/FIRST_SEEN/LAST_SEEN
> logic. If not yet confirmed, hold. Separately, reconcile the un-logged parallel BOST
> dual-track and WDS/APEX_ENTITY sessions into agents_history (THREAD-034)."

## Notes for Future Agent
This conversation's own diagnostic scripts (`diag_step1_hm_etch_check.py`,
`diag_definition_date_ranges.py`, `diag_definition_last_update.py`) were created directly under
`BOST\registry\` but a later parallel session moved them to `BOST\archive\old_diag_scripts\` as
part of a broader reorganization — this is confirmed, not a data-loss event. That same later
session also renamed/date-stamped the Step 1-3 output CSVs under `BOST\registry\` (e.g.
`step1_pilot_bost_raw_20260909.csv`), so exact original file names from this session may no
longer be present verbatim; the underlying pilot results and design decisions in
`BOST_ENRICHMENT_REGISTRY_PLAN.md` section 5 remain the source of truth. Do not assume the
Treatment Rule explanation for the Aug 28 cutoff is settled — the user is actively escalating it
and was explicit that the handoff doc should not close that question prematurely.
