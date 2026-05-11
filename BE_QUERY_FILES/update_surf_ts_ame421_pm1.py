from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS
from surf_scan_coordinates import _add_pilot_status

TARGET_CHAMBER = "AME421_PM1"


def _summarize_ts_transitions(before: pd.Series, after: pd.Series, top_n: int = 10) -> dict[str, int]:
    b = before.reset_index(drop=True).fillna("<NA>").astype(str)
    a = after.reset_index(drop=True).fillna("<NA>").astype(str)
    transitions = (b + " -> " + a).value_counts().head(top_n)
    return transitions.to_dict()


def _backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".ts_ame421_pm1.bak")


def _process_file(path: Path, chamber: str, apply: bool, write_backup: bool) -> None:
    if not path.exists():
        print(f"SKIP missing: {path}")
        return

    df = pd.read_csv(path, low_memory=False)
    original_columns = list(df.columns)
    original_rows = len(df)

    required = ["PRIMARY_EQUIP", "INSPECTION_TIME", "TS"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"{path} missing required columns: {missing}")

    target_mask = df["PRIMARY_EQUIP"].astype(str) == chamber
    target_rows = int(target_mask.sum())

    if target_rows == 0:
        print(f"NOOP {path} chamber={chamber} target_rows=0")
        return

    subset = df.loc[target_mask].copy()
    subset_recomputed = _add_pilot_status(subset, time_col="INSPECTION_TIME")

    if "TS" not in subset_recomputed.columns:
        raise KeyError(f"Recomputed subset missing TS column for {path}")

    old_ts = df.loc[target_mask, "TS"].reset_index(drop=True)
    new_ts = subset_recomputed["TS"].reset_index(drop=True)

    changed_mask = old_ts.fillna("<NA>").astype(str) != new_ts.fillna("<NA>").astype(str)
    changed_rows = int(changed_mask.sum())

    if apply and changed_rows > 0:
        if write_backup:
            bak = _backup_path(path)
            if not bak.exists():
                df.to_csv(bak, index=False)
                print(f"BACKUP created: {bak}")
            else:
                print(f"BACKUP exists: {bak}")

        df.loc[target_mask, "TS"] = new_ts.values
        df.to_csv(path, index=False)

        verify = pd.read_csv(path, low_memory=False)
        if len(verify) != original_rows:
            raise RuntimeError(f"Row count changed unexpectedly for {path}: {original_rows} -> {len(verify)}")
        if list(verify.columns) != original_columns:
            raise RuntimeError(f"Column order changed unexpectedly for {path}")

    print(f"{'UPDATED' if apply else 'DRYRUN'} {path}")
    print(f"  chamber={chamber}")
    print(f"  total_rows={original_rows}")
    print(f"  target_rows={target_rows}")
    print(f"  ts_changed_rows={changed_rows}")
    print(f"  ts_top_transitions={_summarize_ts_transitions(old_ts, new_ts)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update TS only for AME421_PM1 in SURF metrics and coordinates CSVs"
    )
    parser.add_argument("--apply", action="store_true", help="Write changes in place")
    parser.add_argument("--chamber", default=TARGET_CHAMBER, help="PRIMARY_EQUIP chamber to target")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak backup files when applying",
    )
    args = parser.parse_args()

    targets = [
        PIPELINE_PATHS.surf_metrics_csv,
        PIPELINE_PATHS.surf_coordinates_csv,
    ]

    for target in targets:
        _process_file(target, chamber=args.chamber, apply=args.apply, write_backup=not args.no_backup)


if __name__ == "__main__":
    main()
