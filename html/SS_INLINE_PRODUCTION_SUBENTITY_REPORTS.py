"""
SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py

Batch generator for the full SurfScan fleet.
Calls run_for_chamber() from SS_INLINE_CHAMBER_REPORT.py for each chamber in
the fleet list and writes per-chamber HTML reports to html/SS_Subentity_Reports/.

Mirrors the pattern of INLINE_PRODUCTION_SUBENTITY_REPORTS.py.

Output layout
─────────────
  html/SS_Subentity_Reports/
      AME409_PM6.html             ← stable filename, overwritten each run
      AME409_PM5.html
      ...
      logs/
          AME409_PM6_completeness.log
          ...

Usage
─────
  python html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py
  python html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py --dry-run
  python html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py --chamber AME409_PM6
  python html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py --lookback-days 30
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from datetime import datetime
from pathlib import Path


# ─── Load run_for_chamber from sibling script ────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE = os.path.dirname(_HERE)

_spec = importlib.util.spec_from_file_location(
    "_ss_inline_report",
    os.path.join(_HERE, "SS_INLINE_CHAMBER_REPORT.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
run_for_chamber = _mod.run_for_chamber


# ─── Paths ───────────────────────────────────────────────────────────────────
OUT_DIR = os.path.join(_HERE, "SS_Subentity_Reports")

# Dashboard SS report main — stub path; will be wired once ss_report_main.py exists.
# See AME_Dash/SS_Report/SS_REPORTS_INTEGRATION.md §9 for the integration plan.
DASHBOARD_SS_MAIN = (
    Path(__file__).resolve().parents[3]
    / "AME_Dash"
    / "SS_Report"
    / "ss_report_main.py"
)


def _refresh_dashboard_ss_page() -> Path | None:
    """
    Refresh the dashboard-facing SS report page after fleet generation.
    No-ops (with a warning) if ss_report_main.py does not yet exist.
    """
    if not DASHBOARD_SS_MAIN.is_file():
        print(
            f"  [INFO] Dashboard SS main not found at {DASHBOARD_SS_MAIN} — "
            f"skipping refresh.  Build ss_report_main.py to enable."
        )
        return None

    spec = importlib.util.spec_from_file_location("_ss_report_main", DASHBOARD_SS_MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load ss_report_main.py from {DASHBOARD_SS_MAIN}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "build_report"):
        raise AttributeError("ss_report_main.py does not expose build_report()")

    return Path(module.build_report())


# ─── Fleet ───────────────────────────────────────────────────────────────────
# 47 chambers that currently have images/surf_scan/<chamber>/ directories.
# Differs from the inline defect fleet (51) — AME403_PM5, AME417_PM2,
# AME421_PM5, and AME425_PM5 do not have SS image directories.
# run_for_chamber() returns "skipped" for any chamber whose image dir is absent,
# so adding future chambers here before their data arrives is safe.
FLEET: list[str] = [
    "AME401_PM1", "AME401_PM2", "AME401_PM3",
    "AME403_PM1", "AME403_PM2", "AME403_PM3", "AME403_PM4", "AME403_PM5", "AME403_PM6",
    "AME409_PM1", "AME409_PM2", "AME409_PM3", "AME409_PM4", "AME409_PM5", "AME409_PM6",
    "AME411_PM1", "AME411_PM2", "AME411_PM3", "AME411_PM4",
    "AME417_PM1", "AME417_PM2", "AME417_PM3", "AME417_PM4", "AME417_PM5", "AME417_PM6",
    "AME419_PM3", "AME419_PM4", "AME419_PM5", "AME419_PM6",
    "AME421_PM1", "AME421_PM2", "AME421_PM3", "AME421_PM4", "AME421_PM5", "AME421_PM6",
    "AME423_PM1", "AME423_PM2", "AME423_PM3", "AME423_PM4", "AME423_PM5", "AME423_PM6",
    "AME425_PM1", "AME425_PM2", "AME425_PM3", "AME425_PM4", "AME425_PM5", "AME425_PM6",
    "AME427_PM2", "AME427_PM3", "AME427_PM4", "AME427_PM5", "AME427_PM6",
]


# ─── Entry point ─────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate SS inline HTML reports for the full fleet."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the chamber list and image-dir status without generating reports.",
    )
    parser.add_argument(
        "--chamber", default=None,
        help="Run for a single chamber only (overrides the fleet list).",
    )
    parser.add_argument(
        "--lookback-days", type=int, default=60,
        help="Pass through to run_for_chamber: include only events within N days (default: 60).",
    )
    args = parser.parse_args(argv)

    chambers     = [args.chamber] if args.chamber else list(FLEET)
    lookback     = args.lookback_days

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Fleet        : {len(chambers)} chamber(s)")
    print(f"Output dir   : {OUT_DIR}")
    print(f"Lookback     : {lookback} days")

    if args.dry_run:
        print("\nDry run - chambers that would be processed:")
        for c in chambers:
            img_dir = os.path.join(_WORKSPACE, "images", "surf_scan", c)
            status  = "ok" if os.path.isdir(img_dir) else "NO IMAGE DIR"
            print(f"  {c:<20}  [{status}]")
        return

    start   = datetime.now()
    n_ok    = 0
    n_skip  = 0
    errors: list[tuple[str, str]] = []

    for i, chamber in enumerate(chambers, 1):
        print(f"\n[{i}/{len(chambers)}] {chamber}")
        try:
            result = run_for_chamber(chamber, OUT_DIR, lookback_days=lookback)
            if result == "skipped":
                n_skip += 1
            else:
                n_ok += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            errors.append((chamber, str(exc)))

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'-' * 52}")
    print(
        f"Done  {n_ok} ok  |  {n_skip} skipped  |  "
        f"{len(errors)} error(s)  ({elapsed:.1f}s)"
    )

    # Refresh the dashboard SS summary page (no-ops until ss_report_main.py is built)
    try:
        dashboard_report = _refresh_dashboard_ss_page()
        if dashboard_report:
            print(f"Dashboard    : refreshed -> {dashboard_report}")
    except Exception as exc:
        print(f"  [WARN] Dashboard refresh failed: {exc}")

    if errors:
        print("Errors:")
        for ch, msg in errors:
            print(f"  {ch}: {msg}")


if __name__ == "__main__":
    main()
