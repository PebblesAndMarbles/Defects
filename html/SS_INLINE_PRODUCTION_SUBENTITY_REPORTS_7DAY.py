"""
SS_INLINE_PRODUCTION_SUBENTITY_REPORTS_7DAY.py

Thin wrapper that regenerates a single fleet-wide SurfScan 7-day report.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_CHAMBER_SCRIPT = _HERE / "SS_INLINE_CHAMBER_REPORT.py"
_FLEET_SCRIPT = _HERE / "SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py"
_OUT_DIR = _HERE / "SS_Subentity_Reports_7day"


def main(argv: list[str] | None = None) -> None:
    chamber_spec = importlib.util.spec_from_file_location("_ss_inline_chamber_report", _CHAMBER_SCRIPT)
    if chamber_spec is None or chamber_spec.loader is None:
        raise RuntimeError(f"Unable to load chamber report generator from {_CHAMBER_SCRIPT}")

    chamber_module = importlib.util.module_from_spec(chamber_spec)
    chamber_spec.loader.exec_module(chamber_module)

    fleet_spec = importlib.util.spec_from_file_location("_ss_inline_reports_fleet", _FLEET_SCRIPT)
    if fleet_spec is None or fleet_spec.loader is None:
        raise RuntimeError(f"Unable to load fleet report generator from {_FLEET_SCRIPT}")

    fleet_module = importlib.util.module_from_spec(fleet_spec)
    fleet_spec.loader.exec_module(fleet_module)

    if not hasattr(chamber_module, "run_recent_lots_report"):
        raise AttributeError("SS_INLINE_CHAMBER_REPORT.py does not expose run_recent_lots_report()")

    chamber_module.run_recent_lots_report(str(_OUT_DIR), fleet=list(fleet_module.FLEET), lookback_days=14)


if __name__ == "__main__":
    main()