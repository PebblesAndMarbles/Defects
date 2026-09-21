# APEX@ENTITY Enrichment — Handoff

Created: 2026-09-10
Related design: `BOST/BOST_ENRICHMENT_REGISTRY_PLAN.md` (process-definition registry — separate
scope, referenced here only for the "static alias, dynamic mapping" pattern that also applies below)
Related schema reference: `WDS/FULL_FLOW_ALIASES_SCHEMA.md` (section 3 of each alias entry, "ENTITY")
Related probes: `WDS/wds_columns_probe_<ALIAS>.txt` (raw column dumps this handoff is grounded in)
Status: **Design only — implementation deferred to a future session.**

---

## 1. What `APEX@ENTITY` is

`APEX@ENTITY` is one of the four dataset families that shows up for every `FULL_FLOW_ALIASES`
alias when probing WDS (alongside `FDC`, `LITHOSCANVIEW`, and the `WDT@*_MODELING` bookkeeping
noise — see `WDS/FULL_FLOW_ALIASES_SCHEMA.md`). It captures **tool/chamber assignment metadata**:
which physical tool and chamber (PM slot) processed a wafer at a given operation, plus which other
chambers were *candidates* and their state at the time.

Confirmed fully-qualified column shape (6 segments, dataset version `V6` as of this probe —
verify against `wds_active_versions.py`'s `get_current_wds()` rather than hardcoding):

```
APEX@ENTITY@<ALIAS>@V6@<FIELD>
APEX@ENTITY@<ALIAS>@V6@<FIELD>@<SUBFIELD>
```

Real columns observed for `E_8M5_HM_ETCH` (single-wafer probe, `WDS/wds_columns_probe_E_8M5_HM_ETCH.txt`):

```
APEX@ENTITY@E_8M5_HM_ETCH@V6@ENTITY
APEX@ENTITY@E_8M5_HM_ETCH@V6@ENTITY@BATCH_IDLE
APEX@ENTITY@E_8M5_HM_ETCH@V6@ENTITY@PRIOR_ALIAS
APEX@ENTITY@E_8M5_HM_ETCH@V6@ENTITY@PROCESS_ORDER
APEX@ENTITY@E_8M5_HM_ETCH@V6@ENTITY@SEQUENCE
APEX@ENTITY@E_8M5_HM_ETCH@V6@ENTITY@UTILIZATION
APEX@ENTITY@E_8M5_HM_ETCH@V6@OPERATION
APEX@ENTITY@E_8M5_HM_ETCH@V6@PRODUCT
APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0
APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@BATCH_IDLE
APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@PRIOR_ALIAS
APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@PROCESS_ORDER
APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@SEQUENCE
APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@UTILIZATION
APEX@ENTITY@E_8M5_HM_ETCH@V6@WAFER_ENTITY_END_TIME
```

A broader probe (`L_8M5_SED`, `WDS/wds_columns_probe_L_8M5_SED.txt`) shows the full slot range:
**`SUBENTITY_0` through `SUBENTITY_14`** (15 candidate chamber slots), each carrying the same
5 subfields as the top-level `ENTITY` field.

### Field meanings (inferred from names + cross-checked against our own production CSV columns)

| Field | Meaning |
|---|---|
| `ENTITY` (value) | The tool ID that actually processed the wafer at this alias (e.g. `AME403`) — matches the `ENTITY` column already in `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv` |
| `SUBENTITY_N` (value) | Candidate chamber/PM ID for slot `N` (e.g. `AME403_PM3`, `AME403_PM4`) — one of these should match the `SUBENTITY` column already in our production CSV; `N` itself is just a slot index, not a stable chamber identifier |
| `...@BATCH_IDLE` | Whether the chamber was batch-idle (no work queued) around this wafer's run |
| `...@PRIOR_ALIAS` | The alias of the previous operation run in that chamber before this wafer — potential contamination/carryover signal |
| `...@PROCESS_ORDER` | Wafer's position within its chamber run/batch |
| `...@SEQUENCE` | Chamber's rank/order among candidates for this dispatch decision |
| `...@UTILIZATION` | Chamber utilization metric around the time of this wafer |
| `OPERATION` | BOST operation number for this alias (parallels `F_OPERATION_ALIAS` resolution — see BOST registry plan) |
| `PRODUCT` | Product code |
| `WAFER_ENTITY_END_TIME` | Timestamp the wafer completed at this entity — parallels `SUBENTITY_END_TIME` already in our production CSV |

**Not useful for joins** (same as documented in `WDS/FULL_FLOW_ALIASES_SCHEMA.md`):
`WDT@APEX_V6_STATE_V1_MODELING@ENTITY@D1D@<ALIAS>@V6@*` columns (`STATUS`, `RETRY_COUNT`,
`DISCOVERED_AT`, `COMPLETED_AT`, `EXTRACTION_COMPLETED_AT`, `UPLOAD_COMPLETED_AT`) are ETL
pipeline bookkeeping only.

---

## 2. Why this is interesting: what we already have vs. what WDS adds

Our production CSV (`outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`) already carries `ENTITY`,
`SUBENTITY`, `SUBENTITY_END_TIME` per wafer/operation row — i.e. we already know *which* chamber
ran a wafer. What `APEX@ENTITY` adds on top of that:

1. **Chamber history/context at dispatch time** — `BATCH_IDLE`, `PRIOR_ALIAS`, `PROCESS_ORDER`,
   `UTILIZATION` for the chamber that was actually used are not in our production CSV today. These
   are plausible defect-correlation signals (e.g. "was the chamber idle before this run", "what
   ran through it immediately before" — relevant for particle/contamination carryover theories).
2. **The full candidate set, not just the chosen chamber** — `SUBENTITY_0..14` gives every chamber
   that was a dispatch candidate (with its own `SEQUENCE`/`UTILIZATION`/etc.), not only the one
   selected. This could support "what was the loading/availability across the fleet at dispatch
   time" questions, not just "which single chamber ran this wafer."
3. **A cross-check/validation source** for our own `ENTITY`/`SUBENTITY` fields — since both are
   fed by APEX pipelines, comparing them is a low-cost sanity check before trusting either as the
   join key for FDC/LITHOSCANVIEW enrichment (both of which are alias-scoped to the *same*
   chamber assignment).

---

## 3. Proposed enrichment plan

### 3.1 Resolve version dynamically

Don't hardcode `V6` — look it up per dataset the same way `wds_active_versions.get_current_wds()`
does in Dave's IdealAPEX repo (`dev/idealapex/core_support/wds_active_versions.py`), or re-probe
live. Treat the probed `V6` as a snapshot fact, not a constant.

### 3.2 Per-wafer, per-alias pull

Same pattern already proven for FDC (`WDS_client_setup.md` memory notes): scope the pull with
`include_patterns=[f"^APEX@ENTITY@{alias}@V6@"]` per wafer, one alias at a time (batching
multiple aliases in one `include_patterns` list was confirmed dramatically slower / got
interrupted during the FDC probing work — always loop one alias per call).

### 3.3 Resolve "which slot was actually used"

The tricky part: `SUBENTITY_0..14` are positional slots, not stable chamber identifiers. To
extract the metadata for the chamber that *actually ran the wafer* (as opposed to every
candidate), match on **value**, not column name:

1. Pull the top-level `ENTITY` value and all `SUBENTITY_N` values for the wafer.
2. Compare each `SUBENTITY_N` value against our own production CSV's `SUBENTITY` column
   (e.g. `AME403_PM4`) for that same wafer/operation row.
3. The matching `N` identifies which slot's `BATCH_IDLE`/`PRIOR_ALIAS`/`PROCESS_ORDER`/
   `SEQUENCE`/`UTILIZATION` subfields correspond to the chamber that was actually used — pull only
   those 5 fields (plus the top-level `ENTITY@*` fields, which describe the tool-level dispatch,
   distinct from the chamber-level one) into the enriched row.
4. If no `SUBENTITY_N` value matches our own `SUBENTITY` column, that's a discrepancy worth
   flagging (see 3.4), not silently dropping.

### 3.4 Validation pass before trusting as a join key

Before building the full enrichment, run a validation pass on a pilot wafer set (reuse the same
pilot-manifest pattern from `BOST/adhoc_bost_gate_rollout.py` / `BOST/registry/`): pull
`APEX@ENTITY` for each pilot wafer, compare `ENTITY`/matched-`SUBENTITY_N` against our production
CSV's own `ENTITY`/`SUBENTITY` values, and report a match-rate metric. Only proceed to full
enrichment once match rate is confirmed high; investigate mismatches first (could be alias
scoping error, could be a real APEX pipeline discrepancy worth knowing about independent of this
enrichment effort).

### 3.5 Output shape

Flatten the matched-slot fields into wide columns per wafer/alias, prefixed by alias to avoid
collisions across the 10 `FULL_FLOW_ALIASES` (e.g.
`WDS_ENTITY_{ALIAS}_BATCH_IDLE`, `WDS_ENTITY_{ALIAS}_PRIOR_ALIAS`,
`WDS_ENTITY_{ALIAS}_PROCESS_ORDER`, `WDS_ENTITY_{ALIAS}_SEQUENCE`,
`WDS_ENTITY_{ALIAS}_UTILIZATION`, `WDS_ENTITY_{ALIAS}_WAFER_ENTITY_END_TIME`), merged into the
production CSV on `WAFER_ID`/`LOT7` the same way FDC/BOST enrichment already does.

---

## 4. Open questions for implementation session

- Confirm exact semantics of `BATCH_IDLE`, `PROCESS_ORDER`, `SEQUENCE`, `UTILIZATION` with
  Kahtan/Dave — names are inferred from context, not confirmed against WDS API docs.
- Confirm whether `PRIOR_ALIAS` refers to the immediately-prior operation in the *same chamber*
  (contamination/carryover signal) or something else (e.g. prior alias in the wafer's own flow).
- Decide whether the "full candidate set" (`SUBENTITY_0..14`, not just the used chamber) has
  independent analytical value worth capturing (e.g. fleet loading context), or whether only the
  matched/used slot is worth carrying into production CSVs.
- Decide validation match-rate threshold and what to do with mismatches (investigate vs. accept a
  known small discrepancy rate).
- Confirm this reuses the same `wds_client` install/CA-bundle/diagnostics setup already proven in
  `dev/wds-clients` (per `wds_client_setup.md` memory notes) rather than needing anything new.
