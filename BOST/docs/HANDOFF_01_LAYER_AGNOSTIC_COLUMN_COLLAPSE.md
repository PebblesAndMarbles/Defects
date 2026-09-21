# Handoff 1 of 3: Wire in the layer-agnostic column collapse (M5/M6 → single column)

**Suggested order:** this is #1 of 3 handoffs (`HANDOFF_01_...`, `HANDOFF_02_...`,
`HANDOFF_03_...` in this folder). Do this one first — it changes the enrichment
*shape*, and handoffs 2/3 are easier to reason about once the column set is settled.

## Purpose
Collapse BOST Track B value columns that only differ by layer (`L_8M5_*` vs
`L_8M6_*`, `E_8M5_*` vs `E_8M6_*`, `W_8M5_*` vs `W_8M6_*`) into a single shared
column, instead of the current behavior of emitting two separate, mutually-exclusive
~50%-populated columns. This was already designed and pilot-validated once
(2026-09-09) but never wired into the production script.

## Context
- Design doc: `BOST\docs\BOST_ENRICHMENT_REGISTRY_PLAN.md`, section "Column naming
  decision (confirmed, implemented in Step 3)" — read this in full before starting.
- Target script: `BOST\adhoc_bost_gate_rollout.py`
- The join-key fix that made this safe to build on top of is already done and
  verified (see `BOST\docs\HANDOFF_120_GAP_LOT7_JOIN_FIX.md` — dry run is at
  `1142/1142 matched, match_rate=1.0` as of 2026-09-12). Do not touch the join key
  (`WAFER_ID` + `LAYER`) as part of this work.
- Validation reference: `BOST\WIJT BOST 3.csv` / `BOST\wijt_BOST2.csv` is a
  narrower WIJT-wide SIARC_DEP source whose BOST headers are colon-delimited and
  layer-qualified. Validate it by stacking the WIJT columns on the extracted
  layer token and comparing against the collapsed production schema on
  `WAFER_ID + LAYER`.
  - Worked example: `EQUIP:1278_AR189_1000_HVM_BATCH:L_8M5_SIARC_DEP` and
    `EQUIP:1278_AR189_1000_HVM_BATCH:L_8M6_SIARC_DEP` both map to the production
    column `SIARC_DEP_EQUIP_1278_AR189_1000_HVM_BATCH`. After stacking, the two
    WIJT source columns become wafer-layer rows with `LAYER = 8M5CL` or
    `8M6CL`, then compare against the same collapsed production column on
    `WAFER_ID + LAYER`.

## Implementation status
- `_build_bost_wide()` now normalizes Track B `DEFINITION_NAME` values with
  `_normalize_layer_agnostic_definition()` before column derivation.
- Track B columns now use step-first naming, so the canonical M5/M6 aliases
  collapse into single `STEP_{SANITIZED_DEFINITION}` columns.
- Track A policy is now explicit: only `Universal Process Label` rows are kept
  in the legacy path. Rows classified as `Other` are dropped, and rows classified
  as `Treatment Rule` are excluded from Track A and left to Track B.
- After the policy change, the only remaining legacy module-first column in the
  final output is `MX_HM_CLN`.

## Confirmed current state
- `_build_bost_wide()` (line ~698) pivots on `["LOT","WAFER","LAYER"]` and now
  normalizes the raw `DEFINITION_NAME` before calling `_definition_to_column_name()`.
  Two Track B definitions like
  `EQUIP:1278_AR189_1000_HVM_BATCH:L_8M5_CHM_DEP` and
  `EQUIP:1278_AR189_1000_HVM_BATCH:L_8M6_CHM_DEP` now produce one shared column,
  `CHM_DEP_EQUIP_1278_AR189_1000_HVM_BATCH`, populated on both layers' rows.
- The logic to fix this **already exists but is dead code** (confirmed via grep —
  zero callers):
  - `_normalize_operation_suffix()` (line 535) — regex-strips the leading
    `L_8M5_`/`L_8M6_`/`E_8M5_`/`E_8M6_`/`W_8M5_`/`W_8M6_` token from an operation
    string, e.g. `L_8M5_SIARC_DEP` → `SIARC_DEP`.
  - `_normalize_layer_agnostic_definition()` (line 565) — applies the above to
    just the **last** colon-segment of a `DEFINITION_NAME`
    (`EQUIP:BARC_TBF_LPCLEAN:L_8M6_SIARC_DEP` → `EQUIP:BARC_TBF_LPCLEAN:SIARC_DEP`),
    and correctly no-ops on module-suffixed Track A definitions
    (`EQUIP:AMECT_GF:DE-AMEct` stays unchanged, since `DE-AMEct` doesn't match the
    layer-token regex).
- **Why this is safe:** the pivot index already includes `LAYER` per row, and each
  Track B operation maps to exactly one layer (via `_layer_from_alias()`). Two
  rows for the same wafer at different layers never collide in the pivot — they're
  already different rows. Collapsing the *column name* just lets both layers'
  values land in the same column instead of two parallel columns.
- **Known collision hazard (already solved by the existing function, don't
-  regress it):** the design doc found 61 `(LOT, WAFER, LAYER, DEFINITION_NAME)`
  groups in an earlier pilot where the **same** `DEFINITION_NAME` was shared by
  **two different STEPs** (e.g. `SIARC_DEP` vs `CHM_DEP`) with genuinely different
  values. The current implementation preserves STEP in the column name and does
  not strip/generalize it away.

## Required work
1. Completed: `_build_bost_wide()` normalizes `DEFINITION_NAME` before deriving
  value columns.
2. Completed: Track B names are now step-first, and the WIJT validation was updated
  to compare stacked wafer-layer rows against `WAFER_ID + LAYER`.
3. Completed: `EXPECTED_VALUE_COLUMNS` and `PLACEHOLDER_COLUMNS` were left aligned
  with the new output schema.
4. Completed: Track A now keeps only `Universal Process Label` rows, dropping
  `Other` and excluding `Treatment Rule` from the legacy path.

## Verification steps
1. Rerun the full pipeline (`BOST\adhoc_bost_gate_rollout.py`) end-to-end.
2. Confirm `dryrun_metrics.match_rate` is still `1.0` / `unmatched_keys: 0` in
   `artifacts\adhoc_bost_full_summary.json` — this change must not affect the
   join at all, only column naming/pivoting. Any regression here is a bug.
3. Confirm `wide_columns.value_columns` reflects the reduced legacy footprint and
  the step-first Track B naming.
4. Spot-check a known pair, e.g. `EQUIP:1278_AR189_1000_HVM_BATCH:L_8M5_CHM_DEP` /
  `:L_8M6_CHM_DEP` — confirm the output now has ONE column for this definition,
  populated on both `8M5CL` and `8M6CL` rows.
5. Validate WIJT by stacking the layer-qualified WIJT BOST headers into
  wafer-layer rows, mapping them to the collapsed production columns, and
  comparing on `WAFER_ID + LAYER`. For the SIARC_DEP scope in `wijt_BOST2.csv`,
  the mapped columns should compare cleanly once stacked.
6. Confirm no unexpected new `"|"`-joined values appear (see step 2) — if any do,
  stop and report back rather than silently accepting the collapse.
7. Report back the before/after `value_columns` count and null-rate change for
  sign-off, plus the stacked WIJT comparison summary.

## Do not
- Do not change the join key (`WAFER_ID` + `LAYER`) — that's already fixed and
  verified separately.
- Do not strip the STEP token (`SIARC_DEP`/`CHM_DEP`/`SED`/`HM_ETCH`/`HM_CLN`)
  from the normalized definition name — only the layer token. Removing STEP
  reintroduces the 61-collision bug the design doc already found and fixed once.
- Do not remove the other dead functions (`_extract_def_name_from_parameter()`,
  `_extract_module_name_from_parameter()`, `_extract_def_name_from_track_b()`) as
  part of this change — that's `HANDOFF_03_CODE_CLEANUP.md`'s job, after this
  and the registry handoff have landed.
- Do not reintroduce legacy Track A module-first names that are classified as
  `Other` or `Treatment Rule`; the current policy keeps only
  `Universal Process Label` in Track A.

## Files
- Fix target: `BOST\adhoc_bost_gate_rollout.py` (`_build_bost_wide()` line ~698,
  using the already-written `_normalize_layer_agnostic_definition()` line 565 and
  `_normalize_operation_suffix()` line 535).
- Also update: `EXPECTED_VALUE_COLUMNS` (line 61), `PLACEHOLDER_COLUMNS` (line 92).
- Reference/do not re-derive from scratch: `BOST\docs\BOST_ENRICHMENT_REGISTRY_PLAN.md`.
- Baseline/comparison artifact: `artifacts\adhoc_bost_full_summary.json`.
- WIJT comparison input: `BOST\wijt_BOST2.csv` / `BOST\WIJT BOST 3.csv`.

## Track A Decision
Track A has been removed from the implementation. The pipeline now runs on the
Track B treatment-rules path only, and the earlier `Universal Process Label`
filtering policy is superseded.

The completed removal means the remaining work in this handoff is limited to any
optional Track B naming cleanup you still want to pursue. The previous Track A
specific scope, validation, and follow-up notes are retained below only as
history.

---

## VALIDATION FINDINGS (2026-09-13): post Track-A-removal run, re-verified

Ran the pipeline end-to-end to independently validate the shape after this
removal.

### Critical bug found and fixed: `FULL_FLOW_ALIASES` was corrupted
The refactor left `FULL_FLOW_ALIASES` (line ~48) with only `SIARC_DEP`/`CHM_DEP`
permuted across all three prefix letters (`L`/`E`/`W`), producing 4 nonexistent
alias combinations (e.g. `E_8M5_SIARC_DEP`, `W_8M6_CHM_DEP`) and **dropping
`SED`, `HM_ETCH`, and `HM_CLN` entirely** — 3 of 5 real process steps missing.
Still exactly 10 entries, so the `len(FULL_FLOW_ALIASES) != 10` guard didn't
catch it. This is the same failure mode already documented in repo history
(`step4_treatment_rules_pilot.py` made this identical mistake once before).
Cross-checked against `BOST\docs\BOST_DefectQuery_Plan.md` (authoritative
source) and restored the correct list:
```
L_8M5_SIARC_DEP, L_8M5_CHM_DEP, L_8M5_SED, E_8M5_HM_ETCH, W_8M5_HM_CLN,
L_8M6_SIARC_DEP, L_8M6_CHM_DEP, L_8M6_SED, E_8M6_HM_ETCH, W_8M6_HM_CLN
```
**Always diff this constant against `BOST_DefectQuery_Plan.md` after any future
edit near it — don't retype it from memory.**

### Post-fix results (confirmed good)
- `match_rate = 1.0`, `unmatched_keys = 0` (join unaffected, as expected).
- `value_columns = 54`, all 5 STEP tokens represented as column prefixes:
  `SIARC_DEP` (7), `CHM_DEP` (8), `SED` (9), `HM_ETCH` (12), `HM_CLN` (18).
- Null rate on value columns dropped to **0.071** (was 0.138 with the corrupted
  alias list, 0.495 before the original layer collapse) — recovering
  `SED`/`HM_ETCH`/`HM_CLN` is the main driver.
- STEP-prefix-first naming (item C below) confirmed live:
  `CHM_DEP_EQUIP_1278_AR189_1000_HVM_BATCH`, `HM_ETCH_EQUIP_AMECT_GF`, etc.
- Zero columns with pipe-joined (`"|"`) collision values — the
  `EQUIP:BARC_TBF_LPCLEAN:LI-TBEbc` collision (item A below) disappeared on its
  own since it was Track-A-sourced, exactly as predicted. No separate fix needed.

### Side effects found during this refactor — reconcile before handoffs 02/03
1. **`artifacts\adhoc_bost_definition_columns.csv` is now always empty.**
   `_build_bost_wide()` hardcodes its `prefix_map` return value as `{}` instead
   of calling `_definition_prefix_map()` (which still exists but is now never
   called). This is a real loss of an audit-trail artifact — it was used
   directly to diagnose the LI-TBEbc collision earlier in this handoff.
   Recommend restoring the call so this CSV is populated again.
2. **The Track B registry-materialization functions were deleted, not just
   left unused.** `_materialize_track_b_registry()` and
   `_load_track_b_registry_scope()` are gone entirely —
   `BOST\registry\definition_registry_treatment_rules.csv` no longer gets
   refreshed by production runs at all. This overlaps directly with
   `HANDOFF_02_REGISTRY_TRACK_B_DIFF_TRACKING.md`'s scope (which assumed these
   functions still existed and needed fixing, not re-creating). Whoever picks
   up handoff 02 needs to know these functions must be **rebuilt**, not just
   fixed.
3. Minor/cosmetic, safe to leave for `HANDOFF_03_CODE_CLEANUP.md`:
   `_trig_to_defect_layer()` (line ~119) and `TRACK_B_SCOPE_CANDIDATES`
   (line ~42) are now dead code (zero callers). `EXPECTED_VALUE_COLUMNS` /
   `PLACEHOLDER_COLUMNS` still list only Track-A module names that will never
   populate again — safe to delete now that Track A is confirmed gone.

## ADDITIONAL SCOPE (2026-09-13): three more column-naming/cleanup items

The layer collapse above is confirmed working (verified 2026-09-13: full pipeline
run held `match_rate=1.0`/`0 unmatched`, `value_columns` dropped to 55 with the
Track A policy applied, and the WIJT stacked comparison matched the SIARC_DEP
scope cleanly). Three more items belong in this same handoff before it's
considered finalized:

### A. Fix the `EQUIP:BARC_TBF_LPCLEAN:LI-TBEbc` collision (found during verification)
Verification of the collapse (per step 2/6 above) found **one** column with
genuinely colliding (pipe-joined) values: `EQUIP_BARC_TBF_LPCLEAN_LI_TBEBC`
(271 rows in the dry run, checked via `_unique_join()`'s `"|"` separator).
- **Root cause (confirmed, not caused by the layer collapse):** the raw
  `DEFINITION_NAME` is `EQUIP:BARC_TBF_LPCLEAN:LI-TBEbc` (mixed case). The
  `module_suffixes` dict in `_definition_to_column_name()` (line ~641) has the
  key `"LI-TBEBC"` (all caps) — a case-sensitive `.endswith()` check against
  `"LI-TBEbc"` fails, so module-suffix stripping silently doesn't fire, and the
  whole string gets sanitized as one flat token. This definition is recorded
  under two different process steps (SIARC_DEP and CHM_DEP) with genuinely
  different values — exactly the STEP-collision class the original design doc
  (`BOST_ENRICHMENT_REGISTRY_PLAN.md`) already found once — but because this is
  a Track A module-suffixed name (no per-step suffix in the `DEFINITION_NAME`
  itself, unlike Track B), there's no STEP token available to disambiguate it
  from the name alone.
- **Required fix:** make the `module_suffixes` matching in
  `_definition_to_column_name()` case-insensitive (e.g. compare against
  `definition_name.upper()` or use `str.casefold()`), AND confirm from the raw
  Track A rows whether this specific `DEFINITION_NAME` needs a STEP-derived
  disambiguator too (check `TRIGGER_OPERATION` for the colliding rows — if it
  really does span two different steps for the same wafer/layer, the column
  key needs a STEP component here as well, not just the module fix).
- **Verification:** rerun the full pipeline, confirm the `"|"` pipe-joined
  value check (from the main collapse verification steps) now reports **zero**
  affected columns, and confirm `match_rate` is still `1.0`.

### B. A priori detection of Track A "migrated to Treatment Rule" definitions
**Superseded by "Track A Decision UPDATE" above** — that investigation (using
the query below) is what led to the decision to remove Track A entirely rather
than just filter it. Kept here for the reasoning trail; implement the removal
above, not a filter-only version of this item.

User's original ask was whether module-prefixed columns (`{AREA}_{CEID}`, e.g.
`DE_AMECT_*`, `WE_LEOCB_*`) can be identified and skipped from Track A querying
ahead of time, since Nelson's Aug-28 migration (see `BOST\20260827_NELSON_BOST.md`)
moved some of them to Treatment Rules (Track B only, going forward).
- **Important correction to validate before implementing:** the module-suffix
  naming pattern is **not** a reliable migrated/not-migrated signal by itself.
  Already-confirmed evidence (see repo memory / prior session investigation):
  `EQUIP:AMECT_LINERS:DE-AMEct` and `EQUIP:AMECT_LIDS:DE-AMEct` migrated to
  Treatment Rule, but `EQUIP:AMECT_GF:DE-AMEct` — same `DE-AMEct` module suffix —
  did **not** migrate and is still served correctly by Track A. A naming-pattern
  rule would incorrectly exclude `AMECT_GF`.
- **The reliable, queryable signal** is
  `B_CFG_PROCESS_DEFN_FAMILY_ATTR.DEFINITION_TYPE`, joined via
  `B_CFG_PROCESS_DEFN_FAMILY.PROCESS_FAMILY_ID`:
  ```sql
  SELECT DISTINCT d.DEFINITION_NAME, attr.DEFINITION_TYPE
  FROM B_CFG_PROCESS_DEFN d
  INNER JOIN B_CFG_PROCESS_DEFN_FAMILY f ON f.DEFINITION_ID = d.DEFINITION_ID
  INNER JOIN B_CFG_PROCESS_DEFN_FAMILY_ATTR attr ON attr.PROCESS_FAMILY_ID = f.PROCESS_FAMILY_ID
  WHERE d.PROCESS = '{PROCESS}' AND d.FAB = '{FAB}'
  ```
  `DEFINITION_TYPE = 'Treatment Rule'` → migrated (Track B only). `'Universal
  Process Label'` / `'Other'` → still valid via Track A. `DUV_OPC`/`MX_HM_CLN`
  are expected to classify as universal/other, confirming the user's instinct
  for those two specifically.
- **Required work:**
  1. Run the classification query above (once, not per-wafer — this is
     definition-level metadata, not wafer-level data) against the current set of
     module-suffixed names tracked in `EXPECTED_VALUE_COLUMNS` /
     `artifacts\adhoc_bost_definition_columns.csv`, and confirm which are
     `'Treatment Rule'` vs not.
  2. **Verify with a LEFT JOIN before changing any production query** — confirm
     whether `DUV_OPC`/`MX_HM_CLN`-style universal definitions even have a
     `B_CFG_PROCESS_DEFN_FAMILY_ATTR` row at all. If some universal definitions
     have no attr row, an `INNER JOIN`-based exclusion filter in
     `BOST_SQL_TEMPLATE` would silently drop them — don't add the filter until
     this is confirmed safe.
  3. Once confirmed safe, either (a) add `attr.DEFINITION_TYPE != 'Treatment Rule'`
     as a filter in `BOST_SQL_TEMPLATE`'s Track A query (skip migrated defs at
     the SQL level, saving a query round-trip and making the split explicit), or
     (b) if the join proves risky/inconclusive for some definitions, keep it as
     a registry/audit classification only (per `BOST_ENRICHMENT_REGISTRY_PLAN.md`
     section 5's own note that Table B needs a `DEFINITION_TYPE` column) rather
     than gating the live query — document which approach was taken and why.
- **Verification:** rerun the full pipeline; confirm `match_rate` and
  `value_columns` are unaffected for non-migrated definitions, and that no
  currently-populated column goes empty as a result of this change.

### C. Move the STEP token to the front of Track B (operation-suffixed) column names
For Track B definitions like `EQUIP:1278_AR189_1000_HVM_BATCH:CHM_DEP` (already
layer-stripped by `_normalize_layer_agnostic_definition()`), today's
`_definition_to_column_name()` doesn't recognize `CHM_DEP` as a prefix-worthy
suffix (only the four Track A `module_suffixes` are recognized), so it falls
through to the flat-sanitize branch and produces
`EQUIP_1278_AR189_1000_HVM_BATCH_CHM_DEP` — STEP at the end. User wants this to
match the existing MODULE-prefix-first convention (e.g. `DE_AMECT_EQUIP_AMECT_GF`):
the result should be `CHM_DEP_EQUIP_1278_AR189_1000_HVM_BATCH`.
- **Required work:** extend `_definition_to_column_name()` with a second
  suffix-check, alongside the existing `module_suffixes` dict, for the 5
  canonical STEP tokens (`SIARC_DEP`, `CHM_DEP`, `SED`, `HM_ETCH`, `HM_CLN` —
  derive this list from `FULL_FLOW_ALIASES` via `_normalize_operation_suffix()`
  rather than hardcoding a second copy of it). If the last colon-segment matches
  a STEP token (checked after the existing MODULE check, since the two are
  mutually exclusive per current data shapes — Track A names end in a MODULE
  suffix, Track B names end in a STEP suffix post layer-normalization), treat it
  the same way as a module: extract it as the prefix, sanitize the remaining
  `TYPE:NAME` portion as the base, and return `f"{STEP}_{base_name}"`.
- **Verification:** rerun the full pipeline; spot-check that a known Track B
  column (e.g. the `EQUIP:1278_AR189_1000_HVM_BATCH:CHM_DEP` example above) now
  reads `CHM_DEP_EQUIP_1278_AR189_1000_HVM_BATCH`; confirm `match_rate` and
  `value_columns` count are unaffected (this is a pure renaming change, not a
  collapsing/pivoting change); update the WIJT spot-check comparison script
  (used during this handoff's original verification) to reference the new
  column names.

### Do not (additional)
- Do not apply the module-suffix case-insensitivity fix (item A) as a workaround
  for other, different definitions without checking each one individually for a
  genuine multi-step collision first — the case fix alone corrects the symptom;
  confirm whether a STEP disambiguator is also needed for this specific
  definition before considering it done.
- Do not add the Track A exclusion filter (item B) without first confirming via
  a LEFT JOIN that no currently-populated universal/other definition would be
  silently dropped.
- Do not hardcode a second copy of the STEP token list (item C) — derive it from
  `FULL_FLOW_ALIASES` via the existing `_normalize_operation_suffix()` helper so
  the two lists can't drift apart.
