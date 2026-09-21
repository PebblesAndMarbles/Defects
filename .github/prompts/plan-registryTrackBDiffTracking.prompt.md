## Plan: Rebuild Track B registry diffing

Recreate the Track B registry materialization layer in `BOST/adhoc_bost_gate_rollout.py` so the pipeline snapshots `definition_registry_treatment_rules.csv` as a true diff against the prior run, with preserved first-seen dates, explicit NEW/EXISTING/RETIRED status tracking, and prominent surfacing of new treatment definitions. This is a registry/audit-trail change only; the live Track B enrichment query and join behavior stay unchanged.

**Steps**
1. Reconstruct a Track B registry helper near `_run_bost_query_treatment_rules()` that reads the prior registry snapshot from the existing `TRACK_B_SCOPE_CANDIDATES` fallback list, normalizes the current query output into registry rows, and diffs on `(ALIAS, DEFINITION_NAME)` depends on 0.
2. Define the registry row shape explicitly so the new helper preserves the current CSV schema, including historical fields such as `FIRST_SEEN_RUN_DATE`, `LAST_SEEN_RUN_DATE`, `STATUS`, and compatibility columns like `RESOLVED_ALIAS` where present depends on 1. Explicitly rename `TRIGGER_OPERATION` to `RESOLVED_ALIAS` (and mirror the same value into `ALIAS`), matching the column mapping the old materialization function used, rather than leaving this rename implicit.
3. Implement diff semantics exactly as described in the handoff: current-and-previous rows become `EXISTING` with preserved first-seen date, current-only rows become `NEW` with both seen dates set to today, and previous-only rows become `RETIRED` with last-seen date left unchanged depends on 1.
4. Add review visibility for new rows by printing a concise console summary of `NEW` definitions and, if low-risk, emitting an optional `artifacts/definition_registry_new_<date>.csv` snapshot for human review parallel with 3.
5. Wire the helper into `_run_bost_query_treatment_rules()` immediately after `df_track_b` is built and before the dataframe is returned, so every pilot/full run refreshes the registry snapshot as part of the normal pipeline depends on 1-4.
6. Keep the live Track B query, output join, and value-column behavior unchanged; this work must not alter enrichment coverage, match rate, or pivot naming depends on 5.

**Relevant files**
- `BOST/adhoc_bost_gate_rollout.py` — add the registry materialization helper, wire it into the Track B query flow, and reuse the existing registry constants and output helpers.
- `BOST/registry/definition_registry_treatment_rules.csv` — frozen prior snapshot and target output for the rebuilt diffing flow.
- `BOST/docs/HANDOFF_02_REGISTRY_TRACK_B_DIFF_TRACKING.md` — implementation requirements and verification expectations.
- `BOST/docs/BOST_ENRICHMENT_REGISTRY_PLAN.md` — source of the intended registry model and review workflow.

**Verification**
1. Run the pipeline twice back-to-back and confirm rows present in both runs retain the same `FIRST_SEEN_RUN_DATE`, advance `LAST_SEEN_RUN_DATE` to the second run, and remain `EXISTING`.
2. Simulate a retired definition by seeding the registry snapshot with an extra row that the live query does not return, rerun, and confirm it is marked `RETIRED` without bumping `LAST_SEEN_RUN_DATE`.
3. Simulate a new definition by removing a known row from the registry snapshot, rerun, and confirm it is re-added as `NEW`, surfaced in console output, and stamped with today’s date in both seen-date columns.
4. Confirm the enrichment metrics and value columns are unchanged by this registry-only change, especially match rate and pivot output shape.
5. Compare the before/after `definition_registry_treatment_rules.csv` diff across two consecutive runs to validate stability and status transitions.

**Decisions**
- Do not rebuild Stage 1 alias-operation registry in this handoff; Track B registry diffing is limited to definition tracking.
- Do not gate the live Track B SQL or enrichment output on registry status; this is an audit-trail rebuild, not a production-join policy change.
- Preserve the existing CSV file as the source of truth for prior-state diffing, using the current fallback list instead of inventing a second loading convention.
- Treat `NEW` surfacing as a review aid, not an automatic approval mechanism.

**Further Considerations**
1. If the registry file schema drifts from the frozen snapshot, align the helper to the current persisted columns first, then normalize the in-memory row model to match.
2. If console output becomes too noisy on large diffs, keep the full rows in the optional artifact and print only a summary count plus top few definitions.
3. Before trusting the frozen `definition_registry_treatment_rules.csv` (rows dated 2026-09-13) as the prior-run baseline, note it predates the `FULL_FLOW_ALIASES` corruption-and-fix from `HANDOFF_01_LAYER_AGNOSTIC_COLUMN_COLLAPSE.md`. The first rebuild run may therefore show one-time spurious `NEW`/`RETIRED` transitions that reflect that gap rather than real definition churn — expected, not a bug, but worth calling out during verification rather than treating it as a surprise.
