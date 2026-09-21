# Handoff: Fix confirmed LOT7-vs-LOT join bug behind the 120-key BOST coverage gap

## Purpose
Apply the confirmed fix for the BOST dry-run gate's 120-key coverage gap, then rerun the gate
and verify the gap closes. Root cause has already been diagnosed and confirmed live with query
evidence — this handoff is implementation + verification only, not further investigation.

## Context
- Full session history: `agents_history\sessions\2026-09-12_002_bost-query-core-baseline-rollback.md`
- Open thread: THREAD-037 in `agents_history\open_threads.md` (🔴 Blocking)
- Full root-cause writeup: repo memory note titled "BOST 120-key coverage gap — CONFIRMED root
  cause (2026-09-12)" (if you have access to this agent's memory system) — otherwise this document
  is self-contained.
- Target script: `BOST\adhoc_bost_gate_rollout.py`
- Baseline artifact to compare against: `artifacts\adhoc_bost_full_summary.json` ->
  `dryrun_metrics` currently shows `matched_keys: 1022`, `unmatched_keys: 120`,
  `match_rate: 0.894921` (out of 1142 unique input keys).

## Confirmed root cause
In `_run_bost_query_dual_track()` (`BOST\adhoc_bost_gate_rollout.py`, ~line 447-465), the Track B
`wkeys` CTE aliases the truncated 7-character lot as `"LOT"`:

```sql
WITH wkeys AS (
SELECT /*+ MATERIALIZE INDEX(m X3B_META_WAFER_FAB) parallel(m,16) */
   m.LOT7 "LOT"          -- <-- BUG: this is LOT7 (7-char truncated), not the full LOT
  ,m.WAFER
  ,m.WAFER_KEY
FROM B_META_WAFER_FAB m
WHERE m.LOT7 IN ({lot_sql})
)
```

That `"LOT"` alias flows through unchanged to the final `SELECT w.LOT, w.WAFER, ...` in the same
function, becomes `df_track_b["LOT"]`, and is unioned into the dataframe returned by
`_run_bost_query_dual_track()`. Meanwhile:
- Track A (`BOST_SQL_TEMPLATE`, same function) selects `w.LOT` directly off `B_META_WAFER_FAB` —
  the **full, untruncated** LOT.
- The pipeline's join keys (`df_input`, `keys` from `_build_keys()`) also use the **full** LOT.
- `_build_bost_wide()` -> `_join_and_metrics()` merge everything on `["LOT","WAFER_ID","LAYER"]`.

Result: any wafer whose *only* enrichment source is Track B (i.e. definitions that migrated to
`B_WAFER_TREATMENT_RULES` in the Aug-28 split) silently fails to join whenever its LOT has a
sublot/split suffix beyond 7 characters (`LOT != LOT7`). Lots that happen to be exactly 7
characters are unaffected (LOT == LOT7 is a no-op), which is why the gap shows a two-tier
pattern: some lots are 8/8 fully orphaned, others only partially miss (they still get Track-A
coverage for non-migrated definitions).

## Live confirmation already performed (do not redo this)
Two diagnostic scripts were built and run to confirm this before handoff — reuse them for
before/after verification, do not recreate them:
- `BOST\registry\diag_extract_unmatched_120_keys.py` — reruns the pipeline's own dry-run functions
  (`_build_keys` -> `_run_bost_query_dual_track` -> `_build_bost_wide` -> `_join_and_metrics`) and
  dumps the full row-level unmatched key list (not just the top-20-lot aggregate in the summary
  JSON). Reproduced `1022 matched / 120 unmatched` exactly, matching production. Output:
  `BOST\registry\diag_unmatched_120_keys.csv`.
- `BOST\registry\diag_unmatched_gap_query_probe.py` — queries Track A and Track B directly
  against Oracle per selected key, bypassing the pivot/join layer entirely, and explicitly
  captures Track B's raw returned LOT value. Output:
  `BOST\registry\diag_unmatched_gap_query_probe_results.csv`.

Result on a 10-key sample (5 lots: D6141770AF, D6164630V, D6165070W, D6171140Z, D5311930J):
- 10/10 keys had real Track B data (97-103 rows each) — not a data-absence issue.
- 10/10 keys had Track A = 0 rows (fully migrated to Track B for these wafers).
- 10/10 keys: Track B's raw returned LOT was the LOT7-truncated value, confirmed mismatched
  against the full LOT used for joining.
- Zero "true absence" cases in the sample.

## Implementation results and updated findings
The first code change applied during this session only fixed the obvious Track B projection bug.
That improved the dry-run gate from `1022 matched / 120 unmatched` to `1082 matched / 60 unmatched`
(`match_rate=0.947461`), but it also showed the remaining gap was not fully explained by the
original LOT7-vs-LOT alias hypothesis.

Follow-up validation on a representative orphan key (`D6141770AF / MCLXR033WAF2 / 8M5CL`) showed:
- Track A and Track B both return BOST rows keyed to an 8-character lot family value.
- The input file still carries the full 10-character LOT.
- Joining the raw input LOT to the BOST wide table leaves the sample unmatched.
- Normalizing the merge boundary to the observed family key restores the match for that sample.

The durable fix therefore ended up being a join-boundary normalization in `BOST\adhoc_bost_gate_rollout.py`:
- keep the existing `WHERE m.LOT7 IN (...)` scoping predicate for retrieval,
- preserve the original LOT in the external output shape,
- but merge on a separate family-key column derived from the BOST lot value so Track A/Track B
  rows align with the input keys.

Final verification after that change:
- `diag_extract_unmatched_120_keys.py` now reports `1082 matched / 60 unmatched`.
- `artifacts\adhoc_bost_full_summary.json` equivalent dry-run match rate improved from `0.894921`
  to `0.947461`.
- The refreshed unmatched artifact is `BOST\registry\diag_unmatched_120_keys.csv`.

## Required fix
The original Track B-only fix was not sufficient on its own. The working implementation is to keep
Track B scoped by `m.LOT7`, while normalizing the merge boundary to the observed BOST family lot
key so the pipeline joins on the same lot width that BOST actually returns:

```sql
WITH wkeys AS (
SELECT /*+ MATERIALIZE INDEX(m X3B_META_WAFER_FAB) parallel(m,16) */
  m.LOT7 "LOT"
  ,m.WAFER
  ,m.WAFER_KEY
FROM B_META_WAFER_FAB m
WHERE m.LOT7 IN ({lot_sql})
)
```

The `WHERE m.LOT7 IN (...)` scoping predicate stays as-is. The key correction is at the join
boundary, where the pipeline must align the input LOT to the same family-width key used by the
returned BOST rows.

## Verification steps
1. Rerun `BOST\registry\diag_extract_unmatched_120_keys.py` after the fix. Confirm
  `unmatched_keys` drops substantially below 120.
2. Spot-check the previously-orphaned lots (including D6141770AF, D6164630V, D6165070W,
  D6171140Z, D6193580P, D6192790T, D6181710S, D5311930J) in the refreshed
  `BOST\registry\diag_unmatched_120_keys.csv`.
3. Rerun the full pipeline (`BOST\adhoc_bost_gate_rollout.py`) end-to-end (pilot -> dry run ->
  final) and confirm `artifacts\adhoc_bost_full_summary.json` -> `dryrun_metrics.match_rate`
  improves from `0.894921`.
4. Report back here (this workspace) with the new match rate and remaining unmatched-key count
  for final sign-off / THREAD-037 closure.

## Do not
- Do not reintroduce or resurrect the old WIJT-specific replay/wide-builder helpers that were
  already rolled back in session `2026-09-12_002` — this fix is narrower and self-contained.
- Do not change the `WHERE m.LOT7 IN (...)` scoping predicate — only the selected/aliased LOT
  column.
- Do not touch Track A (`BOST_SQL_TEMPLATE`) — it already uses the full LOT correctly.

## Files
- Fix target: `BOST\adhoc_bost_gate_rollout.py` (`_run_bost_query_dual_track()`, Track B `wkeys`
  CTE, ~line 447-465).
- Reuse (do not recreate): `BOST\registry\diag_extract_unmatched_120_keys.py`,
  `BOST\registry\diag_unmatched_gap_query_probe.py`.
- Baseline/comparison artifact: `artifacts\adhoc_bost_full_summary.json`.

---

## ROUND 2 (2026-09-12): WAFER_ID + LAYER is the durable fix

The interim `[:8]` join experiment was confirmed to be the wrong boundary. The
validated durable fix is to stop joining on LOT entirely and use `WAFER_ID + LAYER`
for the merge path while leaving LOT in the output for provenance/display only.

Validation results after the change:
- `BOST\registry\diag_extract_unmatched_120_keys.py` now reports `1142 matched / 0 unmatched`.
- `dryrun_metrics.match_rate` improved from `0.894921` to `1.0`.
- The refreshed artifact is `BOST\registry\diag_unmatched_120_keys.csv` and it is
  now empty.

What this confirmed:
- The remaining 60 keys were not true data absence.
- The LOT field was the unstable join dimension for the remaining gap.
- `WAFER_ID + LAYER` is sufficient for this dataset and resolves both the exact-match
  and LOT-divergence cases without normalizing LOT strings.

### Round 2 verification steps
1. The dry-run extractor now passes with zero unmatched keys.
2. The earlier Round 2 spot-check classes are subsumed by the WAFER_ID-based join and
   now match cleanly.
3. The full pipeline dry-run result is already at `1.0` match rate.
4. THREAD-037 can be closed once the remaining rollout/sign-off steps are complete.

### Do not (Round 2 additions)
- Do not reintroduce any fixed-width (`[:7]`, `[:8]`, or otherwise) LOT normalization
  as part of the join key.
- Do not key the merge on LOT again; keep the WAFER_ID + LAYER join boundary.

