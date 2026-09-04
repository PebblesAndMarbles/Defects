---
session_id: 2026-08-08_010
title: CLASS_BEEP=UNKNOWN Fix + EDI Backfill + Weekly Zero-Rate Aggregator + Workweek Columns
date: 2026-07-07
time_start: ~unknown
time_end: ~unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Fix CLASS_BEEP=UNKNOWN bug introduced by dual-metric CSV dedup; backfill missing EDI records; add workweek columns to pipeline
retroactive: true
logged_date: 2026-08-08
---

## Original Goal
Three related tasks executed across 2026-07-07 to 2026-07-09:
1. Investigate and fix the 181-row CLASS_BEEP=UNKNOWN bug in the extended pipeline output.
2. Backfill EDI records that were missing from the extended dataset (coverage was ~1%).
3. Add PERIOD_END and YYYYWW workweek columns to the pipeline to support pilot analysis filtering.
A fourth task — a weekly zero-rate aggregator — was added during the session as a related enhancement.

## Completed Tasks
- [x] Root-caused CLASS_BEEP=UNKNOWN to dual-metric dedup clobbering NCDD rows with EDI rows
- [x] Fixed `EXTEND_BENCHMARK.py` `merge_and_dedup_raw_sources()` in 3 locations (lines 185–280)
- [x] Verified fix: 0 CLASS_BEEP=UNKNOWN rows in production (was 181)
- [x] Created `EDI_BACKFILL.py` and ran it — 9,800 BEEP_EDI records backfilled; EDI coverage 90.8%
- [x] Created `WEEKLY_ZERO_RATE_AGGREGATOR.py` — Sunday-scheduled; 650-row output verified
- [x] Integrated weekly aggregator as non-fatal step 8 in `8M5CL_8M6CL_UPDATE.py` orchestrator
- [x] Created `BACKFILL_WORKWEEK_COLUMNS.py` and ran it — 100% PERIOD_END/YYYYWW coverage
- [x] Modified `defect_processor.py` to derive PERIOD_END/YYYYWW from INSPECT_TIME going forward
- [x] Updated `PIPELINE_DESIGN.md` with Phase 4 dual-metric fix, aggregator section, and operational flow
- [x] Verified NCDD raw coverage gap (9.2%) — confirmed same JMP plugin lookback limitation; not a pipeline bug

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `BE_QUERY_FILES\modular_processor\EXTEND_BENCHMARK.py` | Modified | `merge_and_dedup_raw_sources()`: dual-metric detection (L185–190), per-metric split dedup (L200–245), suffixed column consolidation with fillna() (L250–280) |
| `BE_QUERY_FILES\modular_processor\processors\defect_processor.py` | Modified | Added `_get_iso_week_info()` and `_format_yyyyww()` helpers (L26–38); PERIOD_END/YYYYWW derivation from INSPECT_TIME (L390–410); column ordering after YYMM (L806) |
| `BE_QUERY_FILES\8M5CL_8M6CL_UPDATE.py` | Modified | Non-fatal step 8 added calling `WEEKLY_ZERO_RATE_AGGREGATOR.py` |
| `PIPELINE_DESIGN.md` | Modified | Phase 4 dual-metric merge fix section added; weekly zero-rate aggregator section added; Step 3 operational flow updated |
| `BE_QUERY_FILES\EDI_BACKFILL.py` | Created | Backfill script: reads 8M5CL_EDI.csv + 8M6CL_EDI.csv, merges into extended file |
| `BE_QUERY_FILES\WEEKLY_ZERO_RATE_AGGREGATOR.py` | Created | Sunday-scheduled aggregator; groups by LAYER+DEVICE+ISO_WEEK; outputs BEEP_RATE / SMP_RATE / BEEP_ZERO_RATE / SMP_ZERO_RATE; DEVICE='ALL' fleet rollup; file-lock protected |
| `BE_QUERY_FILES\BACKFILL_WORKWEEK_COLUMNS.py` | Created | One-time backfill script for PERIOD_END/YYYYWW on existing extended CSVs; timestamped backups created |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BE_QUERY_FILES\8M5CL_NCDD_EDI.csv` | Root cause file — dual-metric rows (50% duplicates per metric) | No |
| `BE_QUERY_FILES\8M6CL_NCDD_EDI.csv` | Root cause file — dual-metric rows (50% duplicates per metric) | No |
| `BE_QUERY_FILES\8M5CL_EDI.csv` | Source for EDI backfill (4,455 rows) | No |
| `BE_QUERY_FILES\8M6CL_EDI.csv` | Source for EDI backfill (5,524 rows) | No |
| `BE_QUERY_FILES\8M5CL_NCDD.csv` | Verified raw NCDD coverage; 9.2% gap vs production confirmed as JMP lookback issue | No |
| `BE_QUERY_FILES\8M6CL_NCDD.csv` | Same as above | No |
| `outputs\8M5CL_8M6CL_EXTENDED.csv` | Primary output; verified 11,019 rows, 70 cols, 0 UNKNOWN, 100% PERIOD_END/YYYYWW | No |
| `outputs\8M5CL_8M6CL_EXTENDED_60DAY.csv` | Secondary output; verified 1,025 rows, 70 cols, 100% PERIOD_END/YYYYWW | No |
| `outputs\8M5CL_8M6CL_ZERO_RATES_CURRENT.csv` | Weekly aggregator stable output; 650 rows verified | No |

## Bugs Encountered
### BUG-001: CLASS_BEEP=UNKNOWN — 181 rows with missing metric classification
- **Status:** Resolved
- **File(s):** `BE_QUERY_FILES\modular_processor\EXTEND_BENCHMARK.py`
- **Root Cause:** `NCDD_EDI.csv` source files contain 50% duplicate wafers — one row per metric type (CLASS_NCDD and CLASS_EDI). Simple `drop_duplicates()` kept only the last row (EDI), silently discarding NCDD data. Rows missing NCDD then had no basis for CLASS_BEEP assignment, producing UNKNOWN.
- **Fix Applied:** Replaced single dedup with dual-metric detection → per-metric split → independent dedup → explicit suffixed-column consolidation using `fillna()`. All three edit regions in `merge_and_dedup_raw_sources()`.
- **Notes:** Fix is safe to re-run. The pattern is specific to files where CLASS_NCDD and CLASS_EDI are separate rows for the same wafer. Any future EDI source that changes this layout would require re-inspection of this function.

## Excursions / Scope Creep Discovered
- NCDD raw source coverage gap (9.2%) investigated — turned out to be JMP plugin lookback limitation, not a pipeline defect. User contacted the JMP plugin team. No code change required.
- Weekly Zero-Rate Aggregator was added as an enhancement during the EDI backfill session; not originally scoped.

## Open Threads
- [ ] JMP plugin coverage gap (9.2% NCDD/EDI lookback limit) — user has contacted other team; no pipeline action pending
- [ ] Weekly zero-rate aggregator: confirm Sunday schedule is being respected in production; --force flag available for manual runs

## Key Decisions Made
- PERIOD_END format is YYYY-MM-DD (Sunday of the ISO week). YYYYWW format is YYWOQ (e.g., '26W27'). Format chosen for human readability and JMP filter compatibility.
- Weekly aggregator is non-fatal in the orchestrator: if it fails, the main pipeline run is not blocked.
- File-lock pattern used in aggregator to prevent concurrent writes from multiple pipeline invocations.
- EDI backfill treated as a one-time script (`EDI_BACKFILL.py`) rather than pipeline integration — EDI source is stable enough that backfill is sufficient; future runs via normal orchestrator update.
- 90.8% EDI coverage accepted as production-ready; remaining 9.2% gap is upstream and cannot be resolved in this pipeline.

## Recommended Re-Entry
**Load these files for context:**
- `BE_QUERY_FILES\modular_processor\EXTEND_BENCHMARK.py`
- `BE_QUERY_FILES\modular_processor\processors\defect_processor.py`
- `BE_QUERY_FILES\WEEKLY_ZERO_RATE_AGGREGATOR.py`
- `PIPELINE_DESIGN.md`

**Suggested starting prompt:**
> "Read PIPELINE_DESIGN.md and EXTEND_BENCHMARK.py. The dual-metric dedup fix was applied in session 2026-08-08_010. Verify BEEP_ZERO_RATE and SMP_ZERO_RATE columns are being populated correctly in the weekly aggregator output, and confirm the Sunday schedule gate is functioning as expected."

## Notes for Future Agent
- The `merge_and_dedup_raw_sources()` function in `EXTEND_BENCHMARK.py` now has three distinct edit zones for the dual-metric fix. If you need to change dedup logic, read all three sections together — they are interdependent.
- `BACKFILL_WORKWEEK_COLUMNS.py` was a one-time script. Do not re-run it unless the PERIOD_END/YYYYWW format changes and a full rebuild is needed. It creates timestamped backups automatically.
- The YYYYWW format `YYWOQ` (e.g., 26W27) is intentional — it matches the existing YYMM column's compact style and sorts correctly as a string.
- Production state at end of session: 8M5CL_8M6CL_EXTENDED.csv = 11,019 rows, 70 columns; 8M5CL_8M6CL_EXTENDED_60DAY.csv = 1,025 rows; ZERO_RATES_CURRENT.csv = 650 rows.
