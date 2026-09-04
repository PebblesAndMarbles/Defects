---
session_id: 2026-08-08_012
title: GAJT/WIJT EDI vs NCDD Metric Comparison — Forensic Analysis
date: 2026-08-08
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Forensic analysis of GAJT/WIJT EDI vs NCDD metric comparison — determine exact SQL logic, parameter keys, CLASS/VALUE formulas, and scaling dependencies for both query paths
retroactive: true
logged_date: 2026-08-08
---

## Original Goal
Determine the full execution chain and SQL logic for both the NCDD query path and the EDI
query path as implemented in WIJT/GAJT.  Goal was a reliable side-by-side comparison so
that downstream metric discrepancies between EDI and NCDD columns could be attributed to
specific formula differences rather than guessed at.

## Completed Tasks
- [x] Confirmed NCDD execution chain from `debug_logs/8M5CL_NCDD.log` (lines 1084-1108, 1601, 10489, 11057-11125)
- [x] Extracted NCDD SQL: DefectParameterQuery, PARM_KEY=20001, QUALIFIER=0; CLASS and VALUE formulas; row gate
- [x] Located and parsed EDI log from `debug_logs/ediQuery#306.log` (lines 44-90)
- [x] Extracted EDI SQL: DefectParameterQuery, PARM_KEY IN (8005, 8007), QUALIFIER=0; INTEL_EDI_SCALING join; CLASS and VALUE formulas; row gate
- [x] Produced EDI vs NCDD side-by-side comparison table covering: parameter keys, qualifier, row gate, zero-defect behavior, class special cases, value formula, scaling dependency, output shape
- [x] Clarified meaning of "downstream metric" in context of WIJT pivot
- [x] Confirmed ZERO_DEFECTS VALUE=1 as source of finite values when conceptual defect count is zero
- [x] Confirmed EDI is evaluated per-defect-mode (BEEP, SMALL_PARTICLE, etc.) via CLASS pivot
- [x] Confirmed query level: wafer-summary + classification level (NOT individual defect coordinates)

## Files Modified
*(No files were modified this session — investigative/forensic only)*

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `debug_logs\8M5CL_NCDD.log` | Primary evidence for NCDD SQL; lines 1084-1108, 1601, 10489, 11057-11125 parsed | No |
| `debug_logs\ediQuery#306.log` | Primary evidence for EDI SQL; lines 44-90 parsed | No |
| `BE_QUERY_FILES\8M5CL_NCDD_SHORT.jsl` | WIJT job spec for CLASS_NCDD (8M5CL) — confirmed CLASS_NCDD only | No |
| `BE_QUERY_FILES\8M6CL_NCDD_SHORT.jsl` | WIJT job spec for CLASS_NCDD (8M6CL) — confirmed CLASS_NCDD only | No |

## Bugs Encountered
*(None encountered — investigative session)*

## Excursions / Scope Creep Discovered
- EDI WIJT JSL config not present in local workspace; EDI job runs from `\\shuser-Prod...ScheduledGAJTvWIJTJobs\` (remote scheduler location, not cloned locally)
- Optional per-class truth table (BEEP and SMALL_PARTICLE exact expected values across all row cases) noted as useful follow-on but not built this session

## Open Threads
- [ ] THREAD-016: Build per-class truth table for BEEP and SMALL_PARTICLE showing exact expected values for: no-property row, class-missing, WAFER_TOTAL row, normal classified row (EDI and NCDD columns separately)
- [ ] THREAD-017: Locate EDI WIJT JSL config — confirm it is at `\\shuser-Prod...\ScheduledGAJTvWIJTJobs\` and identify whether a local copy should be pulled for documentation

## Key Decisions Made
- **"Downstream metric"** was clarified to mean any module calculation performed on the per-class EDI columns after WIJT pivot — not a separate database concept
- **ZERO_DEFECTS VALUE=1** confirmed as intentional encoding (not a bug); VALUE=1 represents presence of a zero-defect wafer in the reporting window
- **EDI is per-defect-mode**: BEEP, SMALL_PARTICLE, WAFER_TOTAL etc. are produced via CLASS pivot post-query, same mechanism as NCDD
- **Table level confirmed**: both EDI and NCDD operate on INSP_WAFER_SUMMARY + INSP_WAFER_PROPERTY + CLASS; individual defect coordinates are irrelevant to these queries; EDI additionally joins INTEL_EDI_SCALING

## Side-by-Side Reference (EDI vs NCDD)

| Dimension | NCDD | EDI |
|-----------|------|-----|
| **PARM_KEY** | 20001 | 8005 (WAFER_TOTAL), 8007 (per-class modes) |
| **QUALIFIER** | 0 | 0 |
| **Row gate** | `r.YVALUE IS NOT NULL OR s.ADDER_DEFECTS=0` | Same |
| **Zero-defect behavior** | CLASS=ZERO_DEFECTS, VALUE=1 when no property row and ADDER_DEFECTS=0 | Same |
| **Class special cases** | FILTER_OUT when c.NAME IS NULL | WAFER_TOTAL for PARM_KEY=8005 |
| **Value formula** | `r.YVALUE` (no scaling) | `LEAST(x.NUMBER_OF_DIE, scaled_yvalue)` when scan area below threshold; `LEAST(x.NUMBER_OF_DIE, r.YVALUE)` otherwise |
| **Scaling dependency** | None | Joins `UDB.INTEL_EDI_SCALING` on DEVICEID |
| **Output column prefix** | `DEFECT@WAFER@CLASS_NCDD@{classname}` | `DEFECT@WAFER@CLASS_EDI@{classname}` |
| **Classes produced** | Per defect class name | BEEP, SMALL_PARTICLE, WAFER_TOTAL, ZERO_DEFECTS, etc. |

## Recommended Re-Entry
**Load these files for context:**
- `debug_logs\8M5CL_NCDD.log` (lines 1057-11125 for full NCDD SQL block)
- `debug_logs\ediQuery#306.log` (lines 44-90 for full EDI SQL block)
- `agents_history\sessions\2026-08-08_012_gajt-wijt-edi-vs-ncdd-forensic-analysis.md` (this file — Side-by-Side Reference table)

**Suggested starting prompt:**
> "Read `agents_history/sessions/2026-08-08_012_gajt-wijt-edi-vs-ncdd-forensic-analysis.md`
> for the full EDI vs NCDD SQL comparison context.
> Then build the per-class truth table described in THREAD-016:
> for BEEP and SMALL_PARTICLE, list exact expected CLASS and VALUE for each row case
> (no-property row, class-missing, WAFER_TOTAL row, normal classified row),
> separately for EDI and NCDD paths."

## Notes for Future Agent
- The ZERO_DEFECTS path (VALUE=1) is shared by both EDI and NCDD.  Do not confuse this
  with the WAFER_TOTAL class which is EDI-only (PARM_KEY=8005).
- EDI area scaling via INTEL_EDI_SCALING is the primary reason EDI and NCDD values diverge
  even when the underlying inspection data is identical.
- FILTER_OUT in NCDD (when c.NAME IS NULL) causes rows to be excluded from pivot output
  entirely — this is different from a null value appearing in the output column.
- The WIJT job for EDI is NOT in the local workspace; only NCDD JSLs
  (`8M5CL_NCDD_SHORT.jsl`, `8M6CL_NCDD_SHORT.jsl`) are local.
  EDI runs from a remote scheduler path outside this repo.
