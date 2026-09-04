---
session_id: 2026-07-26_002
title: Runtime Optimization for 1-Pair Alloy Phase 1 Pipeline
date: 2026-07-26
time_start: unknown
time_end: unknown
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Measure and reduce classify-only runtime for the Alloy Phase 1 VLM pipeline using frozen pair lists and variant prompt/token-cap experiments.
retroactive: true
logged_date: 2026-08-09
---

## Original Goal
Characterize classify-only wall-clock time for the Alloy Phase 1 VLM pipeline at 1-pair and 5-pair
scales. Identify whether prompt length or token cap have meaningful impact on median runtime or
tail latency. Use frozen pair lists (via `--pair-list-csv`) to bypass manifest scan overhead (~200s)
and isolate inference timing. Save reproducible benchmark artifacts.

## Completed Tasks
- [x] Confirmed frozen pair list files exist (`smp_pairs_1.csv`, `smp_pairs_5.csv`, `smp_pairs_20.csv`
      in `images\Alloy_Class\config\frozen_pairs\`) and that orchestrator supports `--pair-list-csv`
- [x] Made `max_completion_tokens` configurable from settings JSON in `classify_phase1_batch.py` (default 500)
- [x] Added `--max-completion-tokens` CLI flag to `caption_phase1_batch.py`
- [x] Added `timing_seconds.row_total` per-image telemetry to `caption_phase1_batch.py`
- [x] Added per-image `timing_seconds` dict (`raw_download`, `inference`, `row_total`) to `classify_phase1_batch.py`
- [x] Fixed cross-mount path crash in `build_phase1_html_report.py` (UNC report dir vs. C: image files)
- [x] Ran p1 benchmark: 3 repeats × 3 variants (baseline, prompt_short, cap180) = 9 classify-only runs
- [x] Ran p5 benchmark: 8 repeats × 3 variants (5 extra repeats added to stabilize tail estimates) = 24 runs
- [x] Saved all matrix rows and aggregates as CSV and JSON artifacts
- [x] Wrote results summary section to `HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md`

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `images\Alloy_Class\pipelines\classify_phase1_batch.py` | Modified | `max_completion_tokens` now read from settings JSON (key: `max_completion_tokens`, default 500); per-image `timing_seconds` dict added (`raw_download`, `inference`, `row_total`) |
| `images\Alloy_Class\pipelines\caption_phase1_batch.py` | Modified | `--max-completion-tokens` CLI flag added; `timing_seconds.row_total` per-image telemetry added |
| `images\Alloy_Class\reporting\build_phase1_html_report.py` | Modified | BUG-001 fix: wrap `os.path.relpath()` call in try/except `ValueError`; fall back to `path.as_uri()` when paths span different drives/mounts |
| `images\Alloy_Class\docs\HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md` | Modified | "Execution Summary Update (2026-07-26)" section added: implemented changes, varied factors, measured results table, artifact paths |

## Output Artifacts Created
| File | Notes |
|------|-------|
| `images\Alloy_Class\artifacts\clean_runtime_matrix_rows_20260726.csv` | All individual p1 run rows (3 repeats × 3 variants) |
| `images\Alloy_Class\artifacts\clean_runtime_matrix_agg_20260726.csv` | p1 aggregated metrics (median, p90, per-pair avg) |
| `images\Alloy_Class\artifacts\clean_runtime_matrix_rows_20260726_p5_r8.csv` | All individual p5 run rows (8 repeats × 3 variants) |
| `images\Alloy_Class\artifacts\clean_runtime_matrix_agg_20260726_p5_r8.csv` | p5 aggregated metrics |
| `images\Alloy_Class\artifacts\clean_runtime_matrix_agg_20260726_p5_r8.json` | p5 aggregated metrics (JSON) |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `images\Alloy_Class\config\frozen_pairs\smp_pairs_1.csv` | 1-pair frozen list used for p1 benchmark runs | No |
| `images\Alloy_Class\config\frozen_pairs\smp_pairs_5.csv` | 5-pair frozen list used for p5 benchmark runs | No |
| `images\Alloy_Class\config\frozen_pairs\smp_pairs_20.csv` | 20-pair frozen list confirmed present; not used this session | No |
| `images\Alloy_Class\config\phase1_settings.json` | Extended with `max_completion_tokens`; variant settings (prompt_short, cap180) tested via this file | No |
| `images\Alloy_Class\pipelines\orchestrator.py` | `--pair-list-csv` flag confirmed functional; bypasses manifest scan (~200s overhead removed) | No |

## Bugs Encountered
### BUG-001: Cross-mount path crash in build_phase1_html_report.py
- **Status:** Resolved
- **File(s):** `images\Alloy_Class\reporting\build_phase1_html_report.py`
- **Root Cause:** `os.path.relpath()` raises `ValueError` when the report output directory is on a UNC
  path (`\\server\share\...`) and the image source files are on a local drive (`C:\...`). Python cannot
  compute a relative path between drives/mounts.
- **Fix Applied:** Wrapped the `os.path.relpath()` call in `try/except ValueError`; on exception, falls
  back to `pathlib.Path.as_uri()` to produce an absolute `file:///` URI for the `<img src>` attribute.
- **Notes:** The fallback URI will not be portable if the HTML is moved to another machine, but it
  eliminates the crash for the primary UNC-based workflow. Long-term fix is THREAD-018 (targeting
  original UNC source paths directly instead of run-folder copies).

## Key Findings
| pair_set | variant | runs | classify_median_s | classify_p90_s | per_pair_avg_s |
|----------|---------|------|-------------------|----------------|----------------|
| p1 | baseline | 3 | 11.015 | 12.016 | 12.578 |
| p1 | prompt_short | 3 | 10.478 | 11.786 | 12.467 |
| p1 | cap180 | 3 | 10.694 | 10.744 | 12.474 |
| p5 | baseline | 8 | 40.541 | 41.482 | 9.685 |
| p5 | prompt_short | 8 | 39.610 | 65.414 | 10.212 |
| p5 | cap180 | 8 | 44.221 | 61.253 | 11.265 |

- p5 baseline is ~23% faster per pair than p1 (9.685 vs 12.578 s) due to fixed overhead amortization.
- prompt_short and cap180 show no consistent improvement; both exhibit long-tail spikes in p5.
- baseline shows tightest and most stable tails; remains the recommended variant for production.
- 8 repeats at p5 are still insufficient to fully characterize the tail (p90 varies run-to-run).

## Excursions / Scope Creep Discovered
- HTML report generation against run-folder copies of images is brittle and prevents path portability;
  ideally reports would reference original UNC library paths (THREAD-018).
- `classify_phase1_batch.py` does not preserve the original UNC source path in its output records;
  this prevents HTML from targeting the library image directly (part of THREAD-018).

## Open Threads
- [ ] THREAD-018: HTML reports target run-folder image copies, not original UNC library paths; classify
      records need to retain original UNC source path so reports can reference library directly
- [ ] THREAD-019: `max_completion_tokens` and related token-cap flags not wired into orchestrator CLI;
      currently require a custom settings JSON file per run — should be first-class CLI flags

## Key Decisions Made
- baseline variant retained as production default; prompt_short and cap180 showed no reliable gain
  and both increased tail variance.
- `max_completion_tokens` default set to 500 (not reduced) pending more conclusive tail evidence.
- Frozen pair list approach (`--pair-list-csv`) adopted as standard for all benchmark runs to eliminate
  manifest scan overhead from timing measurements.
- Per-image `timing_seconds` telemetry added to both classify and caption pipelines; this is the
  canonical source for all future runtime analysis.

## Recommended Re-Entry
**Load these files for context:**
- `images\Alloy_Class\docs\HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md`
- `images\Alloy_Class\artifacts\clean_runtime_matrix_agg_20260726_p5_r8.json`
- `images\Alloy_Class\pipelines\classify_phase1_batch.py`
- `images\Alloy_Class\reporting\build_phase1_html_report.py`

**Suggested starting prompt:**
> "Read `images/Alloy_Class/docs/HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md` in full, then read
> `images/Alloy_Class/artifacts/clean_runtime_matrix_agg_20260726_p5_r8.json`.
> The next steps are: (1) patch classify output records to retain original UNC source path for HTML use
> (THREAD-018), and (2) wire `--max-completion-tokens` directly into the orchestrator CLI (THREAD-019)."

## Notes for Future Agent
- The `--skip-caption --skip-html` flags were used throughout; these benchmarks are classify-only.
  Caption timing is instrumented but not yet characterized separately.
- `smp_pairs_20.csv` exists but no p20 benchmark was run this session; the p5 tail variance suggests
  p20 runs would need even more repeats to be statistically meaningful.
- The `build_phase1_html_report.py` UNC fallback (BUG-001 fix) uses `path.as_uri()` which generates
  `file:///` URIs. These are Windows-local absolute paths and will break if the HTML is viewed from
  another machine. This is an accepted interim behavior.
- All benchmark timing measurements include Python process startup, pair loading, and Azure API round-trip.
  They do NOT include the ~200s manifest scan (eliminated via `--pair-list-csv`).
