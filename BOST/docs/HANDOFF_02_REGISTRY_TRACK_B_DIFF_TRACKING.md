# Handoff 2 of 3: Fix Track B registry diffing (NEW / EXISTING / RETIRED tracking)

**STATUS: CLOSED (verified 2026-09-14).** All verification steps below passed.
Summary:
- Ran the pipeline twice back-to-back: 108 registry rows stayed `EXISTING`,
  `FIRST_SEEN_RUN_DATE` stayed pinned at `2026-09-13`, `LAST_SEEN_RUN_DATE`
  advanced to `2026-09-14` on both runs, zero spurious churn.
- Simulated `RETIRED`: injected a fake row, reran, it correctly flipped to
  `RETIRED` with `LAST_SEEN_RUN_DATE` left unchanged (not bumped to today).
- Simulated `NEW`: removed a real definition's row, reran, it was correctly
  re-added as `NEW` with today's date on both seen-date columns, printed to
  console (`[TRACK B REGISTRY] NEW definitions: 1`), and written to
  `artifacts\definition_registry_new_2026-09-14.csv`.
- Enrichment metrics unaffected throughout: `match_rate = 1.0`,
  `unmatched_keys = 0`, `value_columns = 54` — identical to the pre-registry-
  work baseline, confirming this stayed a pure audit-trail change.
- Test artifacts (fake row, `.bak` backup, test-only NEW snapshot) cleaned up;
  registry restored to its real state and a final clean run confirmed stable.

**Suggested order:** this is #2 of 3 handoffs. Do `HANDOFF_01_LAYER_AGNOSTIC_COLUMN_COLLAPSE.md`
first. This one should land before running the pipeline against the full
production CSV (not just the 60-day extract), since it's the safety net for
"a new treatment value shows up in production and I want to notice it."

## Purpose
Build (not just fix) the Track B registry-materialization step so it actually
diffs against the prior run's registry (true NEW / EXISTING / RETIRED tracking
with a preserved first-seen date), instead of silently overwriting the
registry file from scratch every run.

**UPDATED 2026-09-14 — read this before starting:** this handoff was originally
written against functions that existed at the time
(`_materialize_track_b_registry()`, `_load_track_b_registry_scope()`). Handoff
01's Track A removal work **deleted both functions entirely** (not just left
them buggy) along with the dead `track_b_scope` variable that referenced them.
That deleted state has now been recovered in `adhoc_bost_gate_rollout.py`:
Track B registry materialization is rebuilt, wired back into
`_run_bost_query_treatment_rules()`, and once again writes the treatment-rule
registry CSV. Keep the rest of this note as the implementation record and
verification checklist.

## Context
- Design doc: `BOST\docs\BOST_ENRICHMENT_REGISTRY_PLAN.md`, sections 3.2
  ("Discovery query (two stages)") and 3.3 ("New-definition review workflow") —
  read these before starting.
- Target script: `BOST\adhoc_bost_gate_rollout.py`
- **The underlying data pull is already fine and out of scope here:** the Track B
  SQL query (`tpids` CTE, now inside `_run_bost_query_treatment_rules()` — this
  function was renamed from `_run_bost_query_dual_track()` when Track A was
  removed, see `HANDOFF_01_LAYER_AGNOSTIC_COLUMN_COLLAPSE.md`) is not gated by
  the registry at all — it pulls any `TREATMENT_PARAMETER_NAME` under the 10
  `FULL_FLOW_ALIASES` with `STATUS='ACTIVE'` directly from Oracle every run, and
  `_build_bost_wide()` auto-creates pivot columns for anything discovered.
  (`EXPECTED_VALUE_COLUMNS` is now a Track-A-only leftover per handoff 01's
  findings and is slated for removal in `HANDOFF_03_CODE_CLEANUP.md` — don't
  rely on it for anything in this handoff.) **New treatment values will already
  show up in the output** on a full-production run without any change here.
  This handoff is about the *audit trail* (knowing something is new and
  reviewing it), not about data completeness.

## Confirmed current state (implemented 2026-09-14)
- `_materialize_track_b_registry()` has been rebuilt in
  `adhoc_bost_gate_rollout.py` and is called immediately after the Track B
  query dataframe is created, before the dataframe is returned.
- `TRACK_B_SCOPE_CANDIDATES` remains the single previous-snapshot lookup path;
  the first entry, `BOST\registry\definition_registry_treatment_rules.csv`, is
  now read before each materialization pass and rewritten after diffing.
- The registry CSV is no longer frozen. The new implementation writes the full
  diffed snapshot on each run and also emits an optional
  `artifacts\definition_registry_new_<date>.csv` file for NEW rows.
- The current row shape mirrors the existing CSV schema, with `TRIGGER_OPERATION`
  mirrored into both `RESOLVED_ALIAS` and `ALIAS` so the natural key remains
  `(ALIAS, DEFINITION_NAME)` as described below.
- The first rebuild run may still show one-time churn if the frozen pre-change
  registry snapshot is stale relative to the current live query. That is an
  expected verification caveat, not a materialization bug.
- `BOST\alias_operation_registry.csv` (Table A — alias→operation-number mapping,
  Stage 1 of the design doc) is still header-only, never populated. **This
  handoff still does not build Stage 1** — see "Do not" below.
- The Track B query itself now lives in `_run_bost_query_treatment_rules()`
  (renamed from `_run_bost_query_dual_track()` — Track A no longer exists as a
  separate path at all, see `HANDOFF_01_LAYER_AGNOSTIC_COLUMN_COLLAPSE.md`).
  The materialization call needs a new home inside this function, in the same
  place the old call used to sit (right after `df_track_b`/the query result
  dataframe is built, before it's returned).

## Required work
1. Recreate a `_materialize_track_b_registry()`-equivalent function. Before
   writing, read the **existing**
   `BOST\registry\definition_registry_treatment_rules.csv` if it exists (reuse
   `TRACK_B_SCOPE_CANDIDATES`'s fallback-seed logic for this, rather than
   inventing a second file-loading convention).
2. Compute the natural key for diffing: `(ALIAS, DEFINITION_NAME)` (matching the
   `["RESOLVED_ALIAS", "DEFINITION_NAME"]` shape the old, now-deleted loader
   used).
3. Diff the newly-queried rows against the previous snapshot on that key:
   - **In both** → `STATUS = "EXISTING"`, `FIRST_SEEN_RUN_DATE` = the previous
     row's `FIRST_SEEN_RUN_DATE` (preserved, not reset), `LAST_SEEN_RUN_DATE = today`.
   - **Only in the new query result** → `STATUS = "NEW"`,
     `FIRST_SEEN_RUN_DATE = LAST_SEEN_RUN_DATE = today`.
   - **Only in the previous snapshot** (not returned this run) → `STATUS = "RETIRED"`,
     keep its previously-recorded `LAST_SEEN_RUN_DATE` as-is (don't bump it to
     today — that would misrepresent when it was actually last seen).
4. Surface `STATUS = "NEW"` rows prominently in console output at minimum
   (per the design doc's 3.3 review workflow) so a human notices new treatment
   definitions rather than them silently blending into the "already known" set.
   Writing an optional `artifacts\definition_registry_new_<date>.csv` snapshot of
   just the NEW rows (as the design doc suggests) is a nice-to-have, not required
   for this handoff to be considered done.
5. Wire the new materialization call into `_run_bost_query_treatment_rules()`
   (see "Confirmed current state" above for where) — it has no registry call
   at all right now, so there's no old call site to clean up, just one new
   call to add.

## Implementation status (2026-09-14)
- Completed: `_materialize_track_b_registry()` was rebuilt and now loads the
  prior snapshot through `TRACK_B_SCOPE_CANDIDATES`, diffs on `(ALIAS,
  DEFINITION_NAME)`, and preserves `FIRST_SEEN_RUN_DATE` for EXISTING rows.
- Completed: current Track B query rows now mirror `TRIGGER_OPERATION` into
  `RESOLVED_ALIAS` and `ALIAS`, matching the existing CSV schema while keeping
  the natural key stable.
- Completed: NEW rows are printed to console and written to
  `artifacts\definition_registry_new_<date>.csv` for review.
- Completed: the helper is wired into `_run_bost_query_treatment_rules()` right
  after the query dataframe is built, before the dataframe is returned.
- Not changed: the live Track B SQL, enrichment join, and pivot/value-column
  behavior remain outside the registry rebuild.

## Verification steps
1. Run the full pipeline twice back-to-back (no code changes between runs).
   Confirm: rows present in both runs keep the **same** `FIRST_SEEN_RUN_DATE`
   from run 1, `LAST_SEEN_RUN_DATE` updates to run 2's date, `STATUS` stays
   `EXISTING`.
2. Simulate a `RETIRED` case: temporarily point the registry read at a copy of
   the file with an extra row that won't be returned by the live query (or
   otherwise force a definition to disappear), rerun, and confirm that row flips
   to `STATUS = "RETIRED"` with its `LAST_SEEN_RUN_DATE` unchanged from before.
3. Simulate a `NEW` case: temporarily remove a known-real definition's row from
   the registry file, rerun, and confirm it's re-added with `STATUS = "NEW"` and
   today's date on both seen-date columns, and that it's printed/surfaced in the
   run's console output.
4. Confirm the pipeline's match rate / value columns are unaffected by this
   change (it only touches the registry CSV, not the join or pivot).
5. Report back with a short before/after diff of `definition_registry_treatment_rules.csv`
   across two consecutive runs for sign-off.

## Do not
- Do not build Stage 1 (`BOST\alias_operation_registry.csv`, the alias→operation
  mapping table) as part of this handoff — the design doc's own open questions
  (section 4) treat it as a separate, bigger change, and nothing today depends on
  it. Leave it empty/deferred.
- Do not gate or filter the live Track B SQL query based on registry `STATUS`
  (e.g. excluding `RETIRED` or unreviewed `NEW` rows from production joins) — the
  design doc floats that as a longer-term idea (section 3.4), but it's a
  behavioral change to production output, not an audit-trail fix, and should be
  a separate, deliberate decision later.
- Do not change anything in `BOST\definition_registry_process_defn.csv` (Track A) —
  out of scope for this handoff.

## Files
- Fix target: `BOST\adhoc_bost_gate_rollout.py` — recreate the materialization
  function and wire it into `_run_bost_query_treatment_rules()` (line ~225 as
  of 2026-09-14; re-confirm with a fresh grep, line numbers shift easily in
  this file). No existing `_materialize_track_b_registry()` /
  `_load_track_b_registry_scope()` remain to locate — search for
  `TRACK_B_SCOPE_CANDIDATES` (line ~42) instead, that's the one surviving piece
  from the old implementation.
- Registry artifact: `BOST\registry\definition_registry_treatment_rules.csv`
  (no longer frozen — refreshed on every run as of the 2026-09-14 rebuild;
  verified via two consecutive runs plus RETIRED/NEW simulations).
- Reference/do not re-derive from scratch: `BOST\docs\BOST_ENRICHMENT_REGISTRY_PLAN.md`.
- Related handoffs: `HANDOFF_01_LAYER_AGNOSTIC_COLUMN_COLLAPSE.md` (source of
  the deletion this handoff now has to recover from — see its "VALIDATION
  FINDINGS" section), `HANDOFF_03_CODE_CLEANUP.md` (will remove
  `EXPECTED_VALUE_COLUMNS`/`PLACEHOLDER_COLUMNS`, don't build new dependencies
  on those two lists here).
