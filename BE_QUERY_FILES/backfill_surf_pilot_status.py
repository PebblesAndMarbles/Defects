from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS
from surf_scan_coordinates import _add_pilot_status


def _reorder_pilot_block(df: pd.DataFrame) -> pd.DataFrame:
    pilot_block = ["SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS", "PILOT_STATUS"]
    present = [c for c in pilot_block if c in df.columns]
    if not present:
        return df

    cols = [c for c in df.columns if c not in present]
    if "STATUS" in cols:
        insert_at = cols.index("STATUS") + 1
    elif "MINIPM_RF" in cols:
        insert_at = cols.index("MINIPM_RF") + 1
    else:
        insert_at = len(cols)

    cols[insert_at:insert_at] = present
    return df[cols]


def _backfill_one(path: Path, apply: bool) -> None:
    if not path.exists():
        print(f"SKIP missing: {path}")
        return

    df = pd.read_csv(path, low_memory=False)
    out = _add_pilot_status(df, time_col="INSPECTION_TIME")
    out = _reorder_pilot_block(out)

    if apply:
        out.to_csv(path, index=False)

    print(f"{'UPDATED' if apply else 'DRYRUN'} {path} rows={len(out)}")
    for flag_col in ("SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS"):
        if flag_col in out.columns:
            flag_counts = out[flag_col].value_counts(dropna=False).head(3)
            print(f"  {flag_col} top values: {flag_counts.to_dict()}")
    if "PILOT_STATUS" in out.columns:
        counts = out["PILOT_STATUS"].value_counts(dropna=False).head(10)
        print(f"  PILOT_STATUS top values: {counts.to_dict()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill pilot flags (SRCIP/CCMR2/ICCR2/CV/GF/TS) and PILOT_STATUS into SURF production CSVs"
    )
    parser.add_argument("--apply", action="store_true", help="Write changes in place (default dry-run)")
    args = parser.parse_args()

    targets = [
        PIPELINE_PATHS.surf_metrics_csv,
        PIPELINE_PATHS.surf_coordinates_csv,
    ]

    for target in targets:
        _backfill_one(target, apply=args.apply)


if __name__ == "__main__":
    main()
