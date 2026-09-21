# BOST Enrichment — Definition Registry Plan

Created: 2026-09-09
Related script: `BOST/adhoc_bost_gate_rollout.py`
Related design: `BOST/BOST_DefectQuery_Plan.md` (alias/layer reference this plan extends)
Status: **✅ PHASES 2-3 COMPLETE & PRODUCTION-READY** — Aug 28 cutoff resolved, dual-track enrichment deployed

---

## Executive Summary

On 2026-08-28 at 13:32:41, the BOST/XEUS system underwent WW35.5 2026 migration: ~20 "Treatment Rule" type definitions were reclassified and their wafer-level values moved from `B_WAFER_PROCESS_DEFN` (old system) to `B_WAFER_TREATMENT_DATA_V` (new system). The production enrichment script only queried the old system, causing silent coverage loss.

**Root Cause:** System migration, not a bug.

**Solution Deployed: Dual-track query system**
- **Track A:** `B_WAFER_PROCESS_DEFN` (Process Definitions — old system) → 24 definitions
- **Track B:** `B_WAFER_TREATMENT_DATA_V` (Treatment Rules — new system) → 55 definitions
- **Union:** 79-80 distinct definitions, 10/10 aliases covered, **~70% more coverage** than Track A alone

**Phase 2 Results (Pilot Validation - PASSED):**
- Track A: 3,905 rows, 217 wafers, 24 definitions, 10/10 aliases ✅
- Track B: 149,080 rows, 1,470 wafers, 55 definitions, 10/10 aliases ✅
- Validation Gate: PASS — all 10 aliases have coverage in Track A ∪ Track B

**Phase 3 Results (Production Integration - COMPLETE):**
- Modified `adhoc_bost_gate_rollout.py` with `_run_bost_query_dual_track()` function
- Pilot run: 219,944 rows, 79 definitions, 94% match rate
- Full production run: 1,176 wafers, 80 definitions, 88 enrichment value columns
- **Final output:** `outputs/wafer/8M5CL_8M6CL_EXTENDED_60DAY_BOST_ENRICHED.csv`
- **Status:** Production-ready, backward-compatible, no downstream changes required

**Documentation:**
- [PROJECT_COMPLETION_SUMMARY.md](PROJECT_COMPLETION_SUMMARY.md) — Full 3-phase project summary
- [PHASE2_EXECUTION_REPORT.md](PHASE2_EXECUTION_REPORT.md) — Pilot results and findings
- [PHASE3_INTEGRATION_SUMMARY.md](PHASE3_INTEGRATION_SUMMARY.md) — Implementation and integration details
- [20260827_NELSON_BOST.md](20260827_NELSON_BOST.md) — WW35.5 2026 migration context
- Track B: 149,080 rows, 1,470 wafers, 55 definitions, 10/10 aliases ✅
- **Validation Gate: PASS** — Aug 28 cutoff resolved

**Phase 3: Integration (In Progress)**
- Modified `adhoc_bost_gate_rollout.py` to use dual-track query (`_run_bost_query_dual_track()`)
- New function in place for both pilot and full dry-run phases
- Normalizes Track B schema (derives LAYER from alias, fills missing fields)
- Unions both systems and proceeds with existing pivot/wide-table logic

---

## 1. Problem statement

`BOST/adhoc_bost_gate_rollout.py` enriches defect wafers (8M5CL/8M6CL) with BOST process-family
values using a hardcoded `FULL_FLOW_ALIASES` list (10 aliases: SIARC_DEP, CHM_DEP, SED, HM_ETCH,
HM_CLN × M5/M6).

**What is static:** the aliases themselves. Each one is a fixed identifier for a specific process
step on a specific layer (e.g. `E_8M5_HM_ETCH` = hardmask etch on the M5 layer). This vocabulary
doesn't need to be discovered — it's a known, curated list we already maintain.

**What is dynamic:**

- **The alias → operation-number mapping.** `F_OPERATION_ALIAS` maps each (static) alias to the
  actual BOST operation number(s) that currently implement it. This mapping can change over time
  — new operation numbers can be added under the same alias (route changes, tool requalification,
  new chamber/PM numbering, etc.), separate from anything about the alias itself changing.
- **The process definitions attached to those operations.** `B_CFG_PROCESS_DEFN` /
  `B_CFG_PROCESS_DEFN_FAMILY` rows that get matched to wafers passing through an alias's
  operation(s) are what actually grows over time — a new `DEFINITION_NAME` / `PROCESS_FAMILY` can
  be added for an alias/operation we already track, sometimes with a retroactive/historical
  backfill applied to a set of already-processed wafers (and it also applies going forward).
- Separately, `F_INTEGRATION_LAYER_DEFINITION` (sequence/ordering of layers in the flow) can also
  gain new entries or renumber existing ones over time.

Today, nothing in this workspace or in BOST/WDS tells us **when** a new operation mapping or a
new process definition shows up for one of our known aliases. We only see it if someone manually
re-checks and notices a diff.

Goal of this plan: for the static alias list, use `F_OPERATION_ALIAS` to resolve current operation
numbers, then detect new process definitions (and new operation-number mappings) as they appear,
recording when they were first seen. This becomes the authoritative "scope" that
`adhoc_bost_gate_rollout.py` (and any future BOST enrichment script) queries against — replacing
today's implicit assumption that the operation/definition mapping behind each alias is fixed.

---

## 2. Why WDS does not solve this (summary)

Investigated whether routing through the WDS (Wide Data Store) client/framework instead of BOST
directly would help with this problem. Conclusion: **no** — WDS is not a fit for the
new-definition-detection problem, though it remains useful for other data (chamber FDC traces,
LITHOSCANVIEW, ENTITY metadata) that BOST doesn't have at all.

- WDS's `DECODER` dataset (`APEX@DECODER@<alias>@<ver>@<col>`) is itself just a periodic ETL
  snapshot of the *same* BOST decoder query (`decoder_utilities_rev1.py`'s `get_generic_decoder()`,
  from Dave Gaibler's IdealAPEX repo) that pulls `B_WAFER_PROCESS_DEFN` → `B_CFG_PROCESS_DEFN_FAMILY`
  → `B_CFG_PROCESS_DEFN`. Going through WDS for process-definition data would give **less**
  currency than querying BOST directly, since we'd be bound to an external, unknown refresh
  cadence with zero visibility into whether a new definition has been captured yet.
- The one piece of "handle retroactive/new definitions" logic that exists (in Dave's `decoder_sql`)
  only smooths over a definition BOST **already knows about** whose historical backfill is still
  in progress (`initial_run_completed IN ('N','P')` falls back to a prior completed version). It
  does not discover or flag brand-new operation mappings, process definitions, or
  integration-layer entries for our (static) aliases.
- `wds_active_versions.py` (dataset version dict) and `get_process_flow.py` /
  `upstream_alias_mappings_rev1.py` (process-flow CSV export) are both point-in-time, hand- or
  overwrite-maintained — no history, no diffing, no new-vs-existing tracking anywhere in either
  the `wds-client` package or Dave's `core_support` toolkit.

Searched both vendored repos (`dev/wds-clients`, `dev/idealapex/core_support`) for
registry/backfill/discovery/first-seen concepts — no hits. This capability does not exist
upstream and needs to be built locally.

---

## 3. Proposed registry approach

The registry tracks two distinct, layered things: (a) the current operation-number mapping for
each static alias, and (b) the process definitions that attach to wafers via those operations.
`ALIAS` is always an input (from our known, curated list — e.g. `FULL_FLOW_ALIASES`), never
something discovered.

### 3.1 Registry tables

**Table A — `BOST/alias_operation_registry.csv`** (alias → operation-number mapping, resolved from
`F_OPERATION_ALIAS`; tracks when a *new operation number* gets attached to a known alias):

| Column | Description |
|---|---|
| `PROCESS` | BOST process (e.g. `1278`) |
| `ALIAS` | Static, curated operation alias / `oper_group_name` (e.g. `E_8M5_HM_ETCH`) — an input, not discovered |
| `OPERATION` | Operation number currently mapped to `ALIAS` per `F_OPERATION_ALIAS` |
| `INTEGRATION_LAYER` | From `F_OPERATION_ALIAS` |
| `SEQUENCE_ID` | From `F_INTEGRATION_LAYER_DEFINITION` — position in process flow |
| `LAST_UPDATE_DATE` | `F_OPERATION_ALIAS.LAST_UPDATE_DATE` for this mapping row |
| `FIRST_SEEN_RUN_DATE` / `LAST_SEEN_RUN_DATE` | When this alias→operation mapping was first/most recently observed by our discovery run |
| `STATUS` | `NEW` / `EXISTING` / `RETIRED` (operation no longer returned for this alias) |

**Table B — `BOST/definition_registry.csv`** (process definitions attached to wafers via the
operations resolved in Table A; tracks when a *new definition/process family* appears):

| Column | Description |
|---|---|
| `PROCESS` | BOST process (e.g. `1278`) |
| `FAB` | BOST fab (e.g. `D1D`) |
| `ALIAS` | Static alias this definition was resolved under (join key back to Table A) |
| `OPERATION` | Operation number this definition was observed against (from Table A) |
| `DEFINITION_ID` | `B_CFG_PROCESS_DEFN.DEFINITION_ID` |
| `DEFINITION_NAME` | `B_CFG_PROCESS_DEFN.DEFINITION_NAME` |
| `PROCESS_FAMILY` | `B_CFG_PROCESS_DEFN_FAMILY.PROCESS_FAMILY` |
| `VERSION` | `B_CFG_PROCESS_DEFN.VERSION` |
| `IS_LATEST` / `IS_ACTIVE` | As of last discovery run |
| `INITIAL_RUN_COMPLETED` | `Y`/`N`/`P` — tracks retroactive-backfill-in-progress definitions |
| `FIRST_SEEN_RUN_DATE` | Date this row was first observed by the discovery query |
| `LAST_SEEN_RUN_DATE` | Date this row was most recently observed |
| `STATUS` | `NEW` (first run only, until reviewed) / `EXISTING` / `RETIRED` (previously seen, not returned by latest run) |

### 3.2 Discovery query (two stages)

**Stage 1 — resolve alias → operation(s).** For our static, curated alias list (`FULL_FLOW_ALIASES`
or a broader curated set), query `F_OPERATION_ALIAS` (joined to `F_INTEGRATION_LAYER_DEFINITION`
for sequence/layer info) for the current operation number(s) mapped to each alias — the same
pattern already used in Dave's `get_focus_team()`/`get_process_flow.py` (`rank() over (partition
by oper_group_name order by last_update_date desc)` to get the current mapping row per alias).
Diff against Table A (`alias_operation_registry.csv`) to flag newly-appeared operation numbers for
an alias we already track.

**Stage 2 — resolve operation(s) → process definitions.** Using the operation numbers resolved in
Stage 1 (in place of, or alongside, today's `INSTR(f.TRIGGER_OPERATION, '{alias}') > 0` substring
match in `_build_trigger_filter()`), query `B_WAFER_PROCESS_DEFN` → `B_CFG_PROCESS_DEFN_FAMILY` →
`B_CFG_PROCESS_DEFN` for definitions attached to wafers that ran through those operations — same
table set already used by `_run_bost_query()` / `decoder_utilities_rev1.get_generic_decoder()`.
Diff against Table B (`definition_registry.csv`) to flag newly-appeared definitions/process
families.

Each run, for both tables:
1. Execute the stage's query for the configured process/fab/alias scope.
2. Diff the result against the corresponding registry table on its key columns.
3. Rows not previously seen → appended with `FIRST_SEEN_RUN_DATE = today`, `STATUS = NEW`.
4. Rows previously seen and still returned → `LAST_SEEN_RUN_DATE` updated, `STATUS = EXISTING`
   (once reviewed/acknowledged — see 3.3).
5. Rows previously seen but NOT returned this run → `STATUS = RETIRED` (operation no longer mapped
   to the alias, or definition no longer active/latest).

### 3.3 New-definition review workflow

- Any row with `STATUS = NEW` (in either table) should be surfaced prominently (console output at
  minimum; optionally a small summary artifact like `artifacts/definition_registry_new_<date>.csv`)
  so a human reviews it before it silently starts flowing into production joins.
- Review outcome flips `STATUS` from `NEW` to `EXISTING` (acknowledged) — this is a manual or
  semi-manual step, not auto-approved, since a new `PROCESS_FAMILY`/`DEFINITION_NAME` could
  represent a real new treatment worth adding to scope, or noise (e.g. a one-off test definition).
- For definitions with `INITIAL_RUN_COMPLETED IN ('N','P')`, the existing `decoder_sql` fallback
  pattern (prior-version lookback) already avoids gaps in `adhoc_bost_gate_rollout.py`-style joins
  while backfill completes — the registry's job is only to make sure such definitions are noticed
  and tracked, not to re-implement that fallback query logic.

### 3.4 Integration with `adhoc_bost_gate_rollout.py`

- `FULL_FLOW_ALIASES` stays a static, hardcoded list (that part was never the problem) but the
  logic in `_build_trigger_filter()` that currently matches aliases via
  `INSTR(f.TRIGGER_OPERATION, '{alias}') > 0` text substring matching could be swapped for an
  explicit join through the resolved operation numbers in Table A — a more robust, relational path
  than substring matching on a text field, and one that's already diffed/tracked for drift.
- Longer-term, the set of `DEFINITION_NAME`/`PROCESS_FAMILY` values actually joined into
  production output should be filtered to Table B rows with `STATUS != RETIRED` (and possibly
  `STATUS = EXISTING` only, so brand-new unreviewed definitions don't silently join into
  production output) rather than being accepted unconditionally from a live BOST query.
- `F_INTEGRATION_LAYER_DEFINITION.SEQUENCE_ID` snapshots in Table A also give a path to
  eventually adopt Dave's `ref_alias` upstream/downstream trimming (only keep decoders from
  integration layers at or before a given operation's sequence position) with confidence that
  sequence drift over time is visible/tracked rather than assumed static.

---

## 4. Open questions for implementation session

- Where should `alias_operation_registry.csv` / `definition_registry.csv` live long-term — flat
  CSVs under `BOST/`, or promoted to SQLite/parquet once row counts grow? (Start flat CSV; revisit
  if needed.)
- Discovery run cadence — triggered manually before each `adhoc_bost_gate_rollout.py` run, or on
  a separate schedule (e.g. weekly) independent of production enrichment runs?
- Curated alias scope for Stage 1 — confirm the exact alias list to resolve operations for
  (`FULL_FLOW_ALIASES` as-is, plus `CD_ALIASES`?) and whether to scope by `PROCESS='1278'` only or
  also watch neighboring processes.
- Review/acknowledgment mechanism for `STATUS = NEW` rows — plain manual CSV edit, or a small
  helper script/flag to mark rows reviewed?
- Whether to migrate `_build_trigger_filter()` from `INSTR`-substring alias matching on
  `TRIGGER_OPERATION` to an explicit join via the operation numbers resolved in Table A — bigger
  change, worth validating on a pilot scope first.

---

## 5. 2026-09-10 update: confirmed real-world case — Treatment Rule system migration

`PHASE2_EXECUTION_REPORT.md` and `20260827_NELSON_BOST.md` document a real instance of exactly
the kind of drift this registry is meant to catch, discovered while investigating why coverage
"vanished" for some definitions around 2026-08-28: BOST/XEUS split "Treatment Rule" type
definitions out of the classic Process Definition system (WW35.5 2026) for performance reasons.
Existing definitions were backloaded and ported, but their **wafer-level values moved from
`B_WAFER_PROCESS_DEFN` to a new view, `B_WAFER_TREATMENT_DATA_V`** — the old
`YieldProcessDefinitions`-style query (what `_run_bost_query()`/Track A already does) simply
stops returning rows for any definition reclassified this way, with no error, no metadata change
visible in the normal join path — only `B_CFG_PROCESS_DEFN_FAMILY_ATTR.DEFINITION_TYPE` flips
from `'Universal Process Label'`/`'Other'` to `'Treatment Rule'`.

Implication for this plan: Table B (`definition_registry.csv`) needs a `DEFINITION_TYPE` /
`SOURCE_TABLE` column, and the diffing logic needs to detect a definition **changing type**
(migrating between source systems), not just brand-new definitions appearing. A definition that
silently stops appearing in `B_WAFER_PROCESS_DEFN` should trigger a check of
`B_CFG_PROCESS_DEFN_FAMILY_ATTR.DEFINITION_TYPE` before being marked `RETIRED` — it may simply
have moved to `B_WAFER_TREATMENT_DATA_V` and need to be re-sourced from there instead.

See `BOST/PHASE2_EXECUTION_REPORT.md` for the full working query against
`B_WAFER_TREATMENT_DATA_V` (columns: `WAFER_KEY, PROCESS, TREATMENT_NAME,
TREATMENT_PARAMETER_NAME, LABEL_NAME, LABEL_DATE_VALUE, RUNKEY, LATEST_DATA, OPER_NAME, OPER_TYPE,
TREATMENT_ID, TREATMENT_PARAMETER_ID, SYNC_DEFINITION_ID, SECURITY_CODE` — `OPER_NAME` is the
alias, `TREATMENT_NAME` is the old-system `DEFINITION_NAME` minus its `:XX-YYYct` suffix,
`LABEL_NAME` is the value).


---

## 5. Current status / handoff (as of 2026-09-10)

**Status: scoping in progress, on hold pending DB-owner response on a possible coverage drop.**
Target production input for this scoping work is `outputs/wafer/8M5CL_8M6CL_EXTENDED.csv`
(the full-history file, not the `_60DAY` variant). Enriched copies are being written under
`BOST/registry/` (a subdirectory of this working folder), not back into `outputs/wafer/`.

### Progression so far

1. **Step 1** (`BOST/step1_recent_wafer_registry_pilot.py`) — 10 most-recent wafers (5 per
   layer). Only 2 distinct `DEFINITION_NAME`s came back (`DUV_OPC`, `MX_HM_CLN`); 6 of 10
   full-flow aliases returned nothing. Initially attributed to small sample size.
2. **Step 2** (`BOST/step2_14day_lookback_pilot.py`) — scaled to a 14-day lookback (285 wafers).
   All 10 aliases returned rows; 49 distinct alias/definition combos, 25 distinct
   `DEFINITION_NAME`s (including the `EQUIP:AMECT_*` family expected under `E_8M5/6_HM_ETCH`).
3. **Step 3** (`BOST/step3_wide_table_build.py`) — built the actual wide table from the Step 2
   raw dump (see column-naming decision below). Validated 0 column-key collisions.
4. **Coverage investigation** (`BOST/registry/diag_*.py`) — see below.

### Column naming decision (confirmed, implemented in Step 3)

Wide-table columns are named **`{STEP}_{SANITIZED_DEFINITION_CORE}`**:

- `STEP` is the layer-agnostic process step (`SIARC_DEP`, `CHM_DEP`, `SED`, `HM_ETCH`, `HM_CLN`),
  derived by stripping the `8M5`/`8M6` segment out of the alias (e.g. `L_8M5_CHM_DEP` → `CHM_DEP`).
  Layer is **not** encoded in the column name — it's already carried by the row itself, because
  each raw BOST row's `LAYER` is derived per-row from its own `TRIGGER_OPERATION` and the wide
  table is joined back onto production rows on `(LOT, WAFER_ID, LAYER)`. This alone gives correct
  per-layer population (e.g. a definition only ever seen under `E_8M6_HM_ETCH` populates only the
  wafer's `8M6CL` row and is null on its `8M5CL` row) with no extra logic needed.
- `SANITIZED_DEFINITION_CORE` strips the leading `TYPE:` (`EQUIP`/`PROCESS`) and trailing
  `:MODULE` (`DE-AMEct`/`WE-LEOcb`/`LI-TBEbc`/`LI-SNYli`) segments from `DEFINITION_NAME`, e.g.
  `EQUIP:AMECT_LINERS:DE-AMEct` → `AMECT_LINERS`. Falls back to the module segment when there's
  no middle `NAME` (`PROCESS:DE-AMEct` → `DE_AMECT`).
- **Why `STEP` had to be in the key, not just `DEFINITION_NAME`:** found 61 (LOT, WAFER, LAYER,
  `DEFINITION_NAME`) groups in the 14-day data with >1 distinct `PROC_STRING_VALUE` — same
  `DEFINITION_NAME` (e.g. `EQUIP:BARC_TBF_LPCLEAN:LI-TBEbc`) shared by two different steps within
  one layer (`SIARC_DEP` vs `CHM_DEP`), with genuinely different values (`PRE_LPCLEAN` vs
  `LPCLEAN_1`). Keying on `STEP + DEFINITION_NAME` instead of `DEFINITION_NAME` alone eliminated
  all 61 collisions (verified: 0 remaining).
- `VERSION` conflicts (multiple distinct versions attached to the same key) were checked and not
  observed in the 14-day sample — the existing pipe-join aggregator (`_unique_join`) is kept as a
  safety net rather than adding a permanent `_VERSION` companion column now.
- Noted for later: tool/chamber columns (from a separate query) can be added as future companion
  columns without conflicting with this naming scheme.

### Coverage investigation — Aug 28 demarcation (escalated to DB owners)

Nearly every `EQUIP:*`/`PROCESS:*` definition in the 14-day pilot (everything except `DUV_OPC`
and `MX_HM_CLN`) stops appearing after `2026-08-28 13:32:41` — a hard, uniform cutoff across ~20
definitions spanning multiple steps (`HM_ETCH`, `HM_CLN`, `SIARC_DEP`, `CHM_DEP`) and modules
(`DE-AMEct`, `WE-LEOcb`, `LI-TBEbc`). Investigated two hypotheses, ruled out one:

- **Ruled out — query/filter bug.** Unrestricted diagnostic queries (no trigger filter, no
  `IS_LATEST`/`IS_ACTIVE` filter) against specific "missing" wafers (e.g. `HP1SJ019JKF1`,
  inspected 2026-09-07/08) confirm the definitions genuinely aren't attached in BOST for those
  wafers — not something our query is filtering out.
- **Ruled out — version/backfill lag (Dave's `initial_run_completed` lookback pattern from
  `decoder_utilities_rev1.py`).** Checked `B_CFG_PROCESS_DEFN` directly: every currently
  `IS_LATEST='Y'`/`IS_ACTIVE='Y'` version of the affected definitions already has
  `INITIAL_RUN_COMPLETED = 'Y'`. Dave's historical-version fallback only triggers when the
  *current* version is still mid-backfill, so it would not have surfaced any additional coverage
  here either.
- **Leading theory, not yet confirmed — `DEFINITION_TYPE`.** `B_CFG_PROCESS_DEFN_FAMILY_ATTR`
  shows `MX_HM_CLN` is typed `Universal Process Label` (Dave's decoder scope); the affected
  definitions are typed `Treatment Rule` or `Other`, suggesting they're
  engineering-investigation/consumable-tracking rules with a bounded active window rather than
  continuously-computed per-wafer attributes. `DUV_OPC` is typed `Other` but empirically ~100%
  populated, so type alone isn't a fully clean predictor.
- **Escalated to DB owners** (2026-09-10) to confirm/refute whether this is expected
  rule-expiration behavior or an actual coverage regression on BOST's side. Treat the Aug 28
  cutoff as **unconfirmed** until they respond — do not yet assume either explanation when
  building Table B's `STATUS`/`FIRST_SEEN`/`LAST_SEEN` logic.

### Diagnostic scripts (all in `BOST/registry/`)

- `diag_step1_hm_etch_check.py` / `diag_step1_no_filter_raw.csv` — unrestricted query proving the
  Step 1 alias filter wasn't the cause of missing HM_ETCH coverage.
- `diag_definition_date_ranges.py` — per-definition min/max `INSPECT_TIME`, first surfaced the
  uniform Aug 28 cutoff.
- `diag_dave_decoder_comparison.py` / `diag_definition_versions.csv` / `diag_definition_attrs.csv`
  — version history + `DEFINITION_TYPE`/`INTEGRATION_LAYER` lookup used to rule out backfill lag
  and surface the `DEFINITION_TYPE` lead.
- `diag_definition_last_update.py` — attempted `LAST_UPDATE_DATE`/`CREATE_DATE` lookup on
  `B_CFG_PROCESS_DEFN`; both columns don't exist on that table (`ORA-00904`), so this angle is a
  dead end unless DB owners can supply a rule-activation timestamp from elsewhere.

### Open items before finalizing the registry schema

- Add `DEFINITION_TYPE` (and its `INTEGRATION_LAYER`) as a captured column in Table B once the
  DB-owner escalation resolves — needed to distinguish "expect near-universal coverage" from
  "expect a bounded active window" per definition.
- Table A/B keying should use `(ALIAS or STEP, DEFINITION_NAME)`, not `DEFINITION_NAME` alone, per
  the collision finding above.
- Do not build `FIRST_SEEN`/`LAST_SEEN`/`STATUS = RETIRED` logic against the Aug 28 cutoff yet —
  wait for DB-owner confirmation so "retired" isn't misapplied to a normal rule-expiration case.
- Other enrichment items across these same 10 full-flow aliases are being scoped separately
  (tracked outside this document).
