from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS


def _wafer_60day_output_path() -> Path:
    base = PIPELINE_PATHS.extended_output_csv
    return base.with_name(f"{base.stem}_60DAY{base.suffix}")


def _apply_yymm(df: pd.DataFrame, time_candidates: tuple[str, ...]) -> pd.DataFrame:
    normalized = df.copy()
    time_col = next((col for col in time_candidates if col in normalized.columns), None)
    if time_col is None:
        raise KeyError(
            f"None of the expected time columns were found: {time_candidates}. "
            f"Found columns: {sorted(normalized.columns.tolist())}"
        )

    normalized["YYMM"] = pd.to_datetime(normalized[time_col], errors="coerce").dt.strftime("%y%m")
    ordered = ["YYMM"] + [col for col in normalized.columns if col != "YYMM"]
    return normalized[ordered]


def _backfill_csv(path: Path, time_candidates: tuple[str, ...], apply: bool) -> tuple[int, list[str]]:
    if not path.exists():
        print(f"SKIP missing: {path}")
        return 0, []

    df = pd.read_csv(path, low_memory=False)
    out = _apply_yymm(df, time_candidates)
    if apply:
        out.to_csv(path, index=False)

    print(
        f"{'UPDATED' if apply else 'DRYRUN'} {path} rows={len(out)} "
        f"time_source={next(col for col in time_candidates if col in out.columns)}"
    )
    return len(out), out.columns.tolist()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill YYMM into canonical defects pipeline CSVs")
    parser.add_argument("--apply", action="store_true", help="Write changes in place (default is dry-run)")
    args = parser.parse_args()

    targets = [
        (PIPELINE_PATHS.extended_output_csv, ("INSPECT_TIME",)),
        (_wafer_60day_output_path(), ("INSPECT_TIME", "INSPECTION_TIME")),
        (PIPELINE_PATHS.defect_coordinates_csv, ("INSPECTION_TIME", "SUBENTITY_END_TIME", "INSPECT_TIME")),
        (PIPELINE_PATHS.defect_images_manifest_csv, ("INSPECTION_TIME", "SUBENTITY_END_TIME", "INSPECT_TIME")),
    ]

    for path, time_candidates in targets:
        _backfill_csv(path, time_candidates, apply=args.apply)


if __name__ == "__main__":
    main()