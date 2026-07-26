"""
INLINE_PRODUCTION_SUBENTITY_REPORTS.py

Batch generator for the full inline defect image fleet.
Reads chamber list from docs/FLEET.txt and produces one stable HTML report
per chamber in html/Inline_Subentity_Reports/.

Output layout:
    html/Inline_Subentity_Reports/<CHAMBER>.html          (overwritten each run)
    html/Inline_Subentity_Reports/wafermaps/<CHAMBER>_*_wafermap.png
    html/Inline_Subentity_Reports/<CHAMBER>_completeness.log

Usage:
    python html/INLINE_PRODUCTION_SUBENTITY_REPORTS.py
    python html/INLINE_PRODUCTION_SUBENTITY_REPORTS.py --dry-run
    python html/INLINE_PRODUCTION_SUBENTITY_REPORTS.py --chamber AME409_PM6
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
    "_inline_report",
    os.path.join(_HERE, "INLINE_CHAMBER_EVENT_REPORT.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
run_for_chamber = _mod.run_for_chamber


# ─── Paths ───────────────────────────────────────────────────────────────────
OUT_DIR = os.path.join(_HERE, "Inline_Subentity_Reports")
DASHBOARD_DEFECTS_MAIN = (
    Path(__file__).resolve().parents[3]
    / "AME_Dash"
    / "Inline Defects"
    / "defects_report_main.py"
)


def _refresh_dashboard_defects_page() -> Path:
    spec = importlib.util.spec_from_file_location(
        "_dashboard_defects_report",
        DASHBOARD_DEFECTS_MAIN,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load dashboard report module: {DASHBOARD_DEFECTS_MAIN}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "build_report"):
        raise AttributeError("Dashboard defects module does not expose build_report()")

    return Path(module.build_report())


# ─── Fleet (hard-coded) ────────────────────────────────────────────────
FLEET: list[str] = [
    "AME401_PM1", "AME401_PM2", "AME401_PM3",
    "AME403_PM1", "AME403_PM2", "AME403_PM3", "AME403_PM4", "AME403_PM5", "AME403_PM6",
    "AME409_PM1", "AME409_PM2", "AME409_PM3", "AME409_PM4", "AME409_PM5", "AME409_PM6",
    "AME411_PM1", "AME411_PM2", "AME411_PM3", "AME411_PM4",
    "AME417_PM1", "AME417_PM2", "AME417_PM3", "AME417_PM4", "AME417_PM5", "AME417_PM6",
    "AME419_PM3", "AME419_PM4", "AME419_PM5", "AME419_PM6",
    "AME421_PM1", "AME421_PM2", "AME421_PM3", "AME421_PM4", "AME421_PM5", "AME421_PM6",
    "AME423_PM1", "AME423_PM2", "AME423_PM3", "AME423_PM4", "AME423_PM5", "AME423_PM6",
    "AME425_PM1", "AME425_PM2", "AME425_PM4", "AME425_PM5", "AME425_PM6",
    "AME427_PM2", "AME427_PM3", "AME427_PM4", "AME427_PM5", "AME427_PM6",
]


# ─── Entry point ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate inline defect HTML reports for the full fleet."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the chamber list without generating any reports.",
    )
    parser.add_argument(
        "--chamber", default=None,
        help="Run for a single chamber only (overrides the built-in fleet list).",
    )
    args = parser.parse_args()

    chambers = [args.chamber] if args.chamber else list(FLEET)

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Fleet        : {len(chambers)} chamber(s)")
    print(f"Output dir   : {OUT_DIR}")

    if args.dry_run:
        print("\nDry run \u2014 chambers that would be processed:")
        for c in chambers:
            img_dir = os.path.join(_WORKSPACE, "images", "defects", c)
            status = "ok" if os.path.isdir(img_dir) else "NO IMAGE DIR"
            print(f"  {c:<20}  [{status}]")
        return

    start    = datetime.now()
    n_ok     = 0
    n_skip   = 0
    errors:  list[tuple[str, str]] = []

    for i, chamber in enumerate(chambers, 1):
        print(f"\n[{i}/{len(chambers)}] {chamber}")
        try:
            result = run_for_chamber(chamber, OUT_DIR)
            if result == "skipped":
                n_skip += 1
            else:
                n_ok += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            errors.append((chamber, str(exc)))

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n{'─' * 52}")
    print(
        f"Done  {n_ok} ok  |  {n_skip} skipped  |  "
        f"{len(errors)} error(s)  ({elapsed:.1f}s)"
    )

    dashboard_report = _refresh_dashboard_defects_page()
    print(f"Dashboard   : refreshed {dashboard_report}")

    if errors:
        print("Errors:")
        for ch, msg in errors:
            print(f"  {ch}: {msg}")


if __name__ == "__main__":
    main()
