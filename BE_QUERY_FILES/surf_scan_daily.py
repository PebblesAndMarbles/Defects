from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from surf_scan_update import main

_SS_REPORTS_SCRIPT = Path(__file__).resolve().parent.parent / "html" / "SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py"


def _run_ss_reports() -> None:
    """Regenerate the per-chamber SS HTML fleet reports after a successful pipeline run."""
    spec = importlib.util.spec_from_file_location("_ss_inline_reports_fleet", _SS_REPORTS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main([])


if __name__ == "__main__":
    exit_code = main(["--mode", "incremental", "--run-images", *sys.argv[1:]])
    if exit_code == 0:
        _run_ss_reports()
    raise SystemExit(exit_code)
