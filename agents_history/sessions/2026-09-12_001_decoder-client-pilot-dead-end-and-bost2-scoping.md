---
session_id: 2026-09-12_001
title: decoder_client (wds-decoder-cache) Pilot Investigation — Dead End Confirmed, BOST2 Scoped
date: 2026-09-12
time_start: 11:00
time_end: 13:45
agent: GitHub Copilot
model: Claude Sonnet 4.6
triggered_by: manual-checkpoint
status: complete
original_goal: Scope out `BOST\get_generic_decoder_client.md` (an unexplored decoder_client/wds-decoder-cache path) as a possible alternative for closing the ~87.6% BOST enrichment coverage gap, entirely isolated in a new BOST2 workspace subfolder, and empirically test it against known-problem wafers.
---

## Original Goal
The user has spent multiple prior sessions (2026-09-10/11) trying to close a persistent ~87.6%
BOST enrichment coverage gap via a hand-rolled dual-track (Process Definition + Treatment Rule)
pipeline in `BOST\adhoc_bost_gate_rollout.py`, with a known but unfixed data-loss bug still
suspected. `BOST\get_generic_decoder_client.md` references an internal package
(`decoder_client`, repo `wds-decoder-cache`) that had never been explored. Goal: scope it,
document install, and empirically determine whether it can close the gap — entirely inside a new
`BOST2\` folder, since prior BOST sessions left undocumented files scattered in the workspace
root.

## Completed Tasks
- [x] Read `BOST\get_generic_decoder_client.md`, `dev\idealapex\core_support\decoder_utilities_rev1.py`
      (already-vendored wrapper), and prior BOST session logs/memory to build context
- [x] Wrote initial exploration plan (session memory `/memories/session/plan.md`), refined via
      user clarifying answers (vendor location, ground truth source, pilot-only scope)
- [x] User supplied 4 concrete known-bad wafers (missing specifically on M6-layer aliases) —
      folded into plan as primary pilot targets
- [x] Cloned `wds-decoder-cache` repo (sparse checkout: `decoder_client`, `loader`,
      `design-history`, `diagnostics`, `incidents`, `tests`) to `dev\wds-decoder-cache\`
- [x] Read `loader\ingest.py` — confirmed its ingest SQL only ever queries
      `B_WAFER_PROCESS_DEFN` (old system), never Treatment Rule tables
- [x] Reviewed `WDS\decoder_client_comms\DG_email.txt` / `DG_Teams.txt` (Dave Gaibler
      correspondence) — confirmed decoder_client is about VALUES (not just definition types),
      and is still being actively finalized ("we are just finalizing that utility")
- [x] Re-read `dev\idealapex\core_support\decoder_utilities_rev1.py` in full — found Dave's own
      `__main__` test harness compares decoder_client output directly against the OLD raw BOST
      query (`get_generic_decoder()`), reinforcing it's old-system-scoped
- [x] Built an isolated venv (`WDS\venv_decoder_client\`) specifically to avoid perturbing the
      shared interpreter's pinned `numpy<2`/`pandas<3` environment (decoder-client requires
      `pandas>=2.3`)
- [x] Installed `decoder-client`, `wds-client` (from local `dev\wds-clients` sparse checkout),
      copied `PyUber` from the shared interpreter, and installed `pywin32` into the venv
- [x] Wrote and ran `BOST2\pilot_decoder_client_coverage.py` — live query against 5 known-problem
      wafers via `get_decoder_data()`
- [x] Empirically confirmed decoder_client's cache contains zero data for the migrated Treatment
      Rule definitions (`AMECT_LINERS`, `AMECT_LIDS`, `HRVA_LEOCB_1278`, `80P_ROADRUNNER`, etc.) —
      triple-confirmed via source code, Dave's own harness, and this live query
- [x] Reviewed `BOST\20260827_NELSON_BOST.md` and discussed whether this is a "transition period"
      vs. permanent design; compared BOST's dense per-wafer value storage against the user's own
      `BE_AME_PILOT_TURN_ON_DATES.csv` date-range tracker pattern — captured to repo memory
- [x] Wrote `BOST2\DECODER_CLIENT_STATUS.md` documenting the verdict, evidence, and environment
      notes for a future re-test
- [x] Restored the shared interpreter to its original state after an accidental
      numpy/pandas upgrade (see BUG-001)

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `BOST2\pilot_decoder_client_coverage.py` | Created | Pilot script; queries `decoder_client.get_decoder_data()` for 5 known-problem wafers |
| `BOST2\pilot_decoder_client_raw_output.csv` | Created | Raw output of the pilot query (2,621 columns x 5 wafers) |
| `BOST2\DECODER_CLIENT_STATUS.md` | Created | Status doc: verdict, evidence, environment/install notes for future re-test |
| `dev\wds-decoder-cache\` | Created (vendored clone) | Sparse checkout of `decoder_client`, `loader`, `design-history`, `diagnostics`, `incidents`, `tests` — gitignored, Intel Confidential, matches existing `dev\` vendoring convention |
| `WDS\venv_decoder_client\` | Created | Isolated venv for `decoder-client` (kept separate from shared interpreter's pinned numpy/pandas); includes `decoder-client`, `wds-client`, copied `PyUber`, `pywin32` |
| `/memories/session/plan.md` (session memory) | Created/updated iteratively | Full investigation plan, findings, and evidence log for this exploration |
| `/memories/repo/bost_treatment_rule_migration.md` | Modified | Appended: transition-period vs. permanent-design analysis of Nelson's 2026-08-27 email; per-wafer-value-storage vs. date-range-tracker architecture comparison |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `BOST\get_generic_decoder_client.md` | Entry point for this whole investigation | No |
| `dev\idealapex\core_support\decoder_utilities_rev1.py` | Existing `get_generic_decoder_client()` wrapper; read in full twice | No |
| `BOST\adhoc_bost_gate_rollout.py` | Current production dual-track pipeline; read for comparison, NOT modified this session | Yes — see Open Threads (known collision bug still unfixed) |
| `BOST\wijt_BOST.csv`, `BOST\wijt_BOST2.csv` | Ground-truth company-plugin exports used to validate pilot findings | No |
| `EVIDENCE_REVIEW_WIJT_vs_OURS.md`, `ROOT_CAUSE_ANALYSIS_20260910.md` | Prior root-cause docs describing the known `_extract_def_name_from_track_b()` collision bug | No |
| `WDS\decoder_client_comms\DG_email.txt`, `WDS\decoder_client_comms\DG_Teams.txt` | User-supplied Dave Gaibler correspondence; reviewed for scope/status clues | No |
| `BOST\20260827_NELSON_BOST.md` | Nelson D'Amour's original BOST/XEUS Treatment Rule migration announcement | No |
| `..\BE_AME_PILOT_TURN_ON_DATES.csv` (external, one level above workspace root at `tbatson\`) | User's own date-range pilot tracker, used as an architecture comparison point | No |
| `dev\wds-decoder-cache\loader\ingest.py`, `ARCHITECTURE.md`, `design-history\decoder.py` | Source-code confirmation that decoder_client's cache never queries Treatment Rule tables | No |
| `/memories/repo/wds_client_setup.md` | Reference for the established vendoring/venv/install pattern this session replicated | No |

## Bugs Encountered
### BUG-001: Accidental shared-interpreter numpy/pandas upgrade
- **Status:** Resolved
- **File(s):** Shared interpreter (`c:\users\tbatson\My Programs\SQLPathFinder3\Python3\`)
- **Root Cause:** First install attempt ran `pip install -e dev\wds-decoder-cache` directly
  against the shared interpreter (before the isolated venv was built). `decoder-client` requires
  `pandas>=2.3`/`numpy>=1.21`, which pip silently upgraded to numpy 2.4.6 / pandas 3.0.5,
  breaking pins for scipy, matplotlib, mlflow, modin, numba, scikit-learn, streamlit, and others.
- **Fix Applied:** Reinstalled `numpy==1.24.4 pandas==2.2.0` on the shared interpreter, uninstalled
  `decoder-client` from it, confirmed `pip check` reports no broken requirements. All subsequent
  work moved to the new isolated venv `WDS\venv_decoder_client\` at the user's explicit direction.
- **Notes:** User's stated preference (recorded in user memory) — never touch the shared
  interpreter's package versions for exploratory work again; always use an isolated venv.

### BUG-002: git "dubious ownership" error on UNC clone
- **Status:** Resolved
- **File(s):** `dev\wds-decoder-cache\.git`
- **Root Cause:** UNC path ownership SID doesn't match the current user (same known issue as
  documented in `/memories/repo/wds_client_setup.md` for other vendored repos).
- **Fix Applied:** `git config --global --add safe.directory '%(prefix)///<path>'`.

### BUG-003: venv's own pip corrupted (stale/mismatched bytecode cache)
- **Status:** Resolved
- **File(s):** `WDS\venv_decoder_client\Lib\site-packages\pip\`
- **Root Cause:** `python -m venv` over the UNC share left `.pyc` files in `pip`'s vendored
  `__pycache__` folders that didn't match their `.py` sources — SMB's coarse mtime resolution
  breaks Python's normal cache-invalidation check. Manifested as two different
  `ModuleNotFoundError`s (`pip._internal.operations`, then `pip._vendor.platformdirs.api`) on
  successive pip invocations.
- **Fix Applied:** Deleted all `__pycache__` folders under the venv's `pip` package; pip then
  worked normally.

### BUG-004: pip install AssertionError during bytecode pre-compilation
- **Status:** Resolved
- **File(s):** `WDS\venv_decoder_client\Lib\site-packages\pip\_internal\operations\install\wheel.py`
- **Root Cause:** `assert os.path.exists(pyc_path)` fails right after `compileall.compile_file()`
  reports success — the same UNC-share write-visibility lag as BUG-003, this time during a live
  install rather than pip's own bootstrap.
- **Fix Applied:** Added `--no-compile` to the `pip install` command (skips bytecode
  pre-compilation; Python compiles `.pyc` lazily on first import instead).

### BUG-005: PyUber "No valid backend available" in the venv
- **Status:** Resolved
- **File(s):** `WDS\venv_decoder_client\`
- **Root Cause:** `PyUber` was copied file-for-file from the shared interpreter's site-packages,
  but its Windows COM backend requires `pywin32`, which was never installed in the new venv.
- **Fix Applied:** `pip install pywin32` into the venv.
- **Notes:** PyUber's own error message says "installed from the company portal" — this is just
  PyUber's generic Windows-app-installer phrasing (Intel's self-service app portal), unrelated to
  any BOST/WIJT data portal. Resolves an earlier back-and-forth about what "company portal" meant.

### BUG-006: Pilot query looked hung for several minutes
- **Status:** Resolved (diagnostic, not a real bug)
- **File(s):** `BOST2\pilot_decoder_client_coverage.py`
- **Root Cause:** `get_decoder_data()`'s default worker-pool sizes (`max_workers=40`,
  `resolve_workers=32`) are tuned for 50k+-wafer production sweeps, not a 5-wafer ad-hoc pull;
  combined with Python's fully-buffered stdout when not attached to a TTY, a legitimate ~4-minute
  run looked identical to a hang.
- **Fix Applied:** Reran with `python -u`, explicit smaller `max_workers=4`/`resolve_workers=2`,
  and `progress=True`/`timings={}` for visibility.

## Excursions / Scope Creep Discovered
- User asked a broader architecture question mid-session (is BOST's Treatment Rule migration a
  "transition period," and is dense per-wafer value storage the right design vs. a compact
  date-range cross-reference table like the user's own `BE_AME_PILOT_TURN_ON_DATES.csv`?). This
  was answered in-conversation and captured to `/memories/repo/bost_treatment_rule_migration.md`
  rather than being out of scope — directly informs why the registry/dual-track approach remains
  the right investment.

## Open Threads
- [ ] **Fix the known `_extract_def_name_from_track_b()` / layer-agnostic-normalization data-loss
      bug in `BOST\adhoc_bost_gate_rollout.py`.** This is the actual, concrete, fixable root cause
      of the remaining coverage gap (per `EVIDENCE_REVIEW_WIJT_vs_OURS.md` /
      `ROOT_CAUSE_ANALYSIS_20260910.md`), as opposed to the decoder_client path explored this
      session, which is architecturally closed off. Not started this session.
- [ ] Ask Dave Gaibler / Kahtan Al Jewary directly whether decoder_client's `loader` will ever
      ingest `B_WAFER_TREATMENT_DATA_V`/`B_WAFER_TREATMENT_RULES` — faster than re-deriving this
      from source again later. Deferred (correspondence happened over a weekend).
- [ ] Decide whether `dev\wds-decoder-cache\` and `WDS\venv_decoder_client\` should be kept
      indefinitely (cheap, isolated, gitignored) or cleaned up if decoder_client is permanently
      abandoned. No action needed unless disk space or clutter becomes a concern.
- [ ] User has not yet decided whether the collision-bug fix (see first item) should happen
      in-place in `BOST\adhoc_bost_gate_rollout.py`, or as fresh work organized under `BOST2\`
      (or another new subfolder) given the stated preference to keep new work from spilling into
      the workspace root. Needs explicit confirmation before starting that fix.

## Key Decisions Made
- **Scope for this session: pilot/evaluation only.** `BOST\adhoc_bost_gate_rollout.py` was
  explicitly left untouched — no production migration decision was in scope.
- **Vendored `wds-decoder-cache` clone location: top-level `dev\` (existing convention)**, NOT
  inside `BOST2\` — only new analysis/scripts/docs from this exploration went in `BOST2\`.
- **Ground truth for coverage comparison: existing WIJT plugin exports** (`BOST\wijt_BOST.csv`/
  `wijt_BOST2.csv`) already in the workspace — user was not certain "company portal" referred to
  a different source; BUG-005's error message coincidentally clarified that phrase (PyUber's
  generic Windows app-installer wording), separate from any WIJT/data-portal meaning.
- **Isolated venv over shared interpreter, located in `WDS\`** specifically because it's
  UNC-accessible for future scheduled Scripthost execution — an explicit user requirement after
  BUG-001.
- **decoder_client is parked, not deleted, given Dave's email says the tool is still being
  actively finalized** ("we are just finalizing that utility"). If the loader is ever extended to
  cover Treatment Rules, the existing venv/pilot script can be reused directly.
- **Explicitly rejected:** treating decoder_client as a viable replacement/cross-check path for
  the current coverage-gap problem. Triple-confirmed (source code, Dave's own comparison harness,
  live query) that its cache is old-system-only and cannot recover Treatment-Rule-migrated data.

## Recommended Re-Entry
**Load these files for context:**
- `BOST2\DECODER_CLIENT_STATUS.md` — full verdict and evidence from this session
- `BOST\adhoc_bost_gate_rollout.py` — the `_extract_def_name_from_track_b()` /
  `_normalize_layer_agnostic_definition()` functions (the real, unfixed bug)
- `EVIDENCE_REVIEW_WIJT_vs_OURS.md` — documents the collision mechanism in detail
- `/memories/repo/bost_treatment_rule_migration.md` — full migration background + this session's
  architecture analysis

**Suggested starting prompt:**
> "decoder_client is a confirmed dead end for the BOST coverage gap (see
> `BOST2\DECODER_CLIENT_STATUS.md`). The real fix is the known data-loss bug in
> `BOST\adhoc_bost_gate_rollout.py`'s Track B layer-agnostic normalization
> (`_extract_def_name_from_track_b()`), documented in `EVIDENCE_REVIEW_WIJT_vs_OURS.md`. Review
> that bug, confirm whether to fix it in place or as a fresh implementation under a new/BOST2
> subfolder, and implement the fix."

## Notes for Future Agent
1. **decoder_client's WDS cache is fed exclusively by `B_WAFER_PROCESS_DEFN`** (old system) — this
   is a structural, source-code-verified fact as of the `main` branch commit `faa8a41`
   (2026-09-08). Don't re-investigate this from scratch; `BOST2\DECODER_CLIENT_STATUS.md` has the
   full evidence trail.
2. **The isolated venv pattern (`WDS\venv_decoder_client\`) is reusable** for any future package
   that needs `pandas>=2.3`/`numpy>=2` without disturbing the shared interpreter's pins. The
   UNC-share gotchas (stale pip bytecode cache, `--no-compile` for wheel installs, `pywin32` for
   PyUber) are documented in `BOST2\DECODER_CLIENT_STATUS.md` and apply to any similar venv setup.
3. **"Company portal" is NOT a data source** — it's Intel's generic Windows-app-install portal,
   referenced in PyUber's own error message. Don't chase this phrase as a lead again.
4. **The user's `BE_AME_PILOT_TURN_ON_DATES.csv` tracker pattern (date-range cross-reference per
   physical chamber) is architecturally distinct from what BOST needs** (retroactive backload +
   reactivation semantics) — this comparison was discussed and resolved this session; don't
   re-open it as if it's an unresolved design question.
