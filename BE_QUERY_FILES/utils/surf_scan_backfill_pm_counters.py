from __future__ import annotations

DEPRECATION_MESSAGE = (
    "surf_scan_backfill_pm_counters.py has been retired and is blocked for production use.\n"
    "Reason: it can repopulate legacy non-RF columns (FULLPM/MINIPM/CNTR_SS), which violates the\n"
    "current RF-only production contract.\n"
    "Use BE_QUERY_FILES/surf_scan_elwc_pm_stage_backfill.py with --apply-production instead."
)


def run(*args, **kwargs):
    raise RuntimeError(DEPRECATION_MESSAGE)


def main(argv: list[str] | None = None) -> int:
    raise RuntimeError(DEPRECATION_MESSAGE)


if __name__ == "__main__":
    raise SystemExit(main())
