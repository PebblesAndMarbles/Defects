# SURF Scan Pipeline Design (RF-Focused)

## Purpose
This document captures the RF-focused production design for the SURF Scan pipeline and the key issues resolved during rollout.

Scope covered here:
- RF-only production counter strategy (FULLPM_RF, MINIPM_RF)
- ELWC stage/apply architecture
- Daily scheduler behavior and safety guarantees
- Root-cause issues encountered and fixes applied
- Operational validation signals

## Design Goals
- Keep `surf_scan_daily.py` as a thin scheduler launcher (no payload re-zip dependency for logic updates).
- Populate production counters from ELWC-aligned logic rather than legacy nearest-only coordinate logic.
- Restrict production counter outputs to RF columns only:
  - FULLPM_RF
  - MINIPM_RF
- Prevent regression in scheduled incremental runs.
- Preserve previously populated RF values outside current incremental lookback.

## Runtime Topology

### 1) Daily entrypoint
- `BE_QUERY_FILES/surf_scan_daily.py`
- Behavior: wraps and calls update orchestrator in incremental mode with images enabled.

### 2) Orchestrator
- `BE_QUERY_FILES/surf_scan_update.py`
- Step flow (relevant parts):
  1. coordinates
  2. elwc_rf_refresh
  3. stacked_edx
  4. zero_timebin
  5. images
  6. image_prune

Legacy nearest PM control:
- Orchestrated runs now disable legacy nearest-time PM enrichment in coordinates by default.
- Explicit diagnostic opt-in is available via:
  - `--enable-legacy-nearest-pm-enrichment`
- This control does not disable ELWC fallback behavior in stage/apply; it only gates the legacy nearest-only coordinates enrichment path.

### 3) ELWC RF refresh
- `BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py`
- Two-phase pattern:
  - `build_stage(...)`: creates stage metrics from scoped SURF rows by chunk.
  - `apply_stage_to_production(...)`: merges staged ELWC RF values into production CSVs.

Legacy utility status:
- `BE_QUERY_FILES/surf_scan_backfill_pm_counters.py` is retired and blocked for production use.
- Rationale: it used nearest-only PM mapping and could repopulate legacy non-RF columns.

### 4) ELWC attach/fallback core
- `BE_QUERY_FILES/surf_scan_elwc_pm_pilot.py`
- Responsible for ELWC event attachment and inspection-time fallback semantics.

## Core Design Choices

### A) Stage-first architecture over direct in-place updates
Rationale:
- Separates expensive ELWC/counter matching from production write operations.
- Allows diagnostics and deterministic apply behavior.
- Supports large-window backfills (`--lookback-days 270`) and small incremental windows uniformly.

### B) Chunk by unique event keys
Chunking uses unique event groups built from:
- INSPECTION_TIME
- PRIMARY_EQUIP
- ACTUAL_LOT

Rationale:
- Reduces memory pressure and SQL window size.
- Gives progress visibility and per-chunk diagnostics (`match_rows`, `fallback_rows`).

### C) RF-only production policy
Production counter contract is intentionally limited to:
- FULLPM_RF
- MINIPM_RF

Legacy counter columns are not part of production contract:
- FULLPM
- MINIPM
- CNTR_SS

### D) Preserve existing RF values outside apply scope
Apply behavior now uses staged values when present and preserves existing production RF otherwise.

Rationale:
- Incremental lookback should update targeted rows, not clear prior historical RF values.

### E) Prevention over cleanup for legacy columns
Legacy counters are prevented from being emitted in generation paths (not merely dropped later).

Rationale:
- Avoid accidental reintroduction and sparse legacy artifacts.
- Keep schema behavior explicit and stable.
- Enforce retirement of legacy nearest-only backfill tooling in production paths.

## Key Challenges and Resolutions

### 1) Scheduler crash in fallback assignment
Symptom:
- `ValueError: Must have equal len keys and value when setting with an ndarray`
- Observed in daily debug log during ELWC fallback application.

Root cause:
- Fallback mapping could produce non-scalar assignment behavior when row-id mapping was not strictly one-to-one.

Resolution:
- Hardened fallback map construction to ensure unique row-id mapping before assignment.
- Result: fallback assignment remains 1D and stable.

### 2) Duplicate/suffixed ELWC columns and merge collisions
Symptom:
- `_x`/`_y` style ELWC artifacts and inconsistent write behavior.

Root cause:
- Existing ELWC columns in production DataFrames collided with incoming stage columns.

Resolution:
- Drop stale ELWC columns before attach/apply.
- Namespace stage columns (`STAGE_ELWC_*`) before merge.
- Remove ELWC/STAGE_ELWC diagnostic columns from production outputs after apply.

### 3) AME427_PM6 MINIPM_RF edge case
Symptom:
- Missing MINIPM_RF in scenario with asynchronous attribute update timings.

Root cause:
- Single snapshot fallback was insufficient when attributes update at different timestamps.

Resolution:
- Multi-layer fallback logic:
  - backward snapshot
  - nearest snapshot
  - per-attribute nearest non-null fill (bounded window)

### 4) Legacy counters appearing in production outputs
Symptom:
- FULLPM/MINIPM/CNTR_SS observed in production CSV headers despite RF-only goal.

Root cause:
- Generation paths (especially coordinates output) still included full counter set.

Resolution:
- Enforced RF-only counter output in production generation path.
- Stage metrics output blocks canonical counter columns that should not be generated there.
- Removed dependency on production-side legacy-drop patch logic as primary control.

### 5) RF counters appearing recent-only after incremental runs
Symptom:
- Historical RF looked sparse after daily updates.

Root cause:
- Apply assignment previously overwrote RF columns from stage-only values, causing nulling where stage had no match.

Resolution:
- Apply now combines staged incoming RF with existing production RF, preserving historical values outside current stage scope.

## Current Operational Behavior

### Daily scheduled run
- Incremental lookback updates only the active window.
- Historical RF values outside lookback are preserved.
- ELWC stage/apply completes in-line as part of `surf_scan_update.py` workflow.

### Backfill run
- Example command used successfully:

```powershell
& 'c:\users\tbatson\My Programs\SQLPathFinder3\Python3\python.exe' 'BE_QUERY_FILES\surf_scan_elwc_pm_stage_backfill.py' --lookback-days 270 --chunk-events 100 --apply-production
```

Expected effect:
- Recomputes stage for selected horizon.
- Applies RF columns into production CSVs.
- Leaves production counter schema RF-only.

## Validation Signals To Monitor

### Log-level indicators of healthy run
- `[coordinates] finished`
- `[elwc_rf_refresh] started`
- `[apply] complete metrics_rows=... coordinates_rows=...`
- `[elwc_rf_refresh] applied RF columns: ['FULLPM_RF', 'MINIPM_RF']`
- Consolidated run summary block

### CSV schema checks
Both files should include RF counters and exclude legacy counters:
- `outputs/surf_scan/SS_METRICS.csv`
- `outputs/surf_scan/SS_COORDINATES.csv`

Expected:
- present: FULLPM_RF, MINIPM_RF
- absent: FULLPM, MINIPM, CNTR_SS

### Coverage checks
Track non-null RF counts for:
- full file
- last 7 days

This confirms both historical retention and incremental freshness.

## Why This Is Safe To Leave Scheduled
- Launcher remains stable and minimal.
- Counter enrichment logic is modular and updateable without changing scheduler wrapper.
- Known crash path in fallback assignment was fixed.
- Merge/apply behavior now preserves historical RF outside incremental scope.
- Legacy non-RF counters are prevented at generation path for production outputs.

## Out-of-Scope / Future Considerations
- If schema contracts evolve, keep RF-only policy explicit in one configuration location.
- Consider adding a lightweight post-run automatic audit job for:
  - header contract checks
  - RF non-null thresholds
  - fallback unresolved count trend tracking.
