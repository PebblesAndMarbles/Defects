from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from pipeline_config import PIPELINE_PATHS
from surf_scan_coordinates import _add_pilot_status as surf_add_pilot_status

PILOT_COLUMNS = ["CCMR2", "ICCR2", "CV", "GF", "SRCIP", "TS"]
INLINE_PILOT_BLOCK = ["SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS", "PILOT_STATUS"]


@dataclass
class UpdateSummary:
    name: str
    rows: int
    changed_by_column: Dict[str, int]
    output_path: Path | None


def _normalize_for_compare(series: pd.Series) -> pd.Series:
    return series.fillna("<NA>").astype(str)


def _changed_count(before: pd.Series, after: pd.Series) -> int:
    return int((_normalize_for_compare(before) != _normalize_for_compare(after)).sum())


def _create_pilot_status(df: pd.DataFrame) -> pd.Series:
    srcip_on = df["SRCIP"] == "ON"

    base = pd.Series("ERROR", index=df.index, dtype="object")
    ccmr2_on = df["CCMR2"] == "ON"
    iccr2_on = df["ICCR2"] == "ON"

    base[(~ccmr2_on) & (~iccr2_on)] = "POR"
    base[(ccmr2_on) & (~iccr2_on)] = "CCMR2"
    base[(~ccmr2_on) & (iccr2_on)] = "ICCR2"
    base[(ccmr2_on) & (iccr2_on)] = "CCMR2+ICCR2"

    suffix = pd.Series("", index=df.index, dtype="object")
    suffix = suffix.mask(df["CV"] == "ON", suffix + "+CV")
    suffix = suffix.mask(df["GF"] == "ON", suffix + "+GF")

    status = base + suffix
    status = status.mask(srcip_on, "SRCIP")
    return status


def _reorder_inline_pilot_block(df: pd.DataFrame) -> pd.DataFrame:
    present = [c for c in INLINE_PILOT_BLOCK if c in df.columns]
    if not present:
        return df

    cols = [c for c in df.columns if c not in present]
    if "P_ORDER" in cols:
        insert_at = cols.index("P_ORDER") + 1
    elif "STATUS" in cols:
        insert_at = cols.index("STATUS") + 1
    else:
        insert_at = len(cols)

    cols[insert_at:insert_at] = present
    return df[cols]


def _reorder_surf_pilot_block(df: pd.DataFrame) -> pd.DataFrame:
    present = [c for c in INLINE_PILOT_BLOCK if c in df.columns]
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


def _load_pilot_dates() -> pd.DataFrame:
    pilot_path = PIPELINE_PATHS.pilot_dates_path
    if not pilot_path.exists():
        raise FileNotFoundError(f"Pilot turn-on file missing: {pilot_path}")

    pilot_df = pd.read_csv(pilot_path, low_memory=False)
    if "SUBENTITY" not in pilot_df.columns:
        raise KeyError("Expected SUBENTITY in pilot turn-on file")

    available_cols = [c for c in PILOT_COLUMNS if c in pilot_df.columns]
    if not available_cols:
        raise KeyError("No pilot columns found in pilot turn-on file")

    pilot_map = pilot_df[["SUBENTITY", *available_cols]].copy()
    for col in available_cols:
        pilot_map[col] = pd.to_datetime(pilot_map[col], errors="coerce")
    return pilot_map


def _update_inline_wafer(df: pd.DataFrame, selected_columns: List[str], pilot_map: pd.DataFrame) -> pd.DataFrame:
    if "SUBENTITY" not in df.columns:
        raise KeyError("Expected SUBENTITY column in wafer output")

    time_col = "SUBENTITY_END_TIME" if "SUBENTITY_END_TIME" in df.columns else "INSPECT_TIME"
    if time_col not in df.columns:
        raise KeyError("Expected SUBENTITY_END_TIME or INSPECT_TIME column in wafer output")

    out = df.copy()
    out["__PILOT_KEY"] = out["SUBENTITY"].astype(str)

    available_turnon_cols = [c for c in pilot_map.columns if c != "SUBENTITY"]
    missing_selected = [c for c in selected_columns if c not in available_turnon_cols]
    if missing_selected:
        raise KeyError(
            "Selected pilot columns missing from turn-on CSV: "
            f"{missing_selected}. Available columns: {available_turnon_cols}"
        )

    turnon_rename = {c: f"__TURNON_{c}" for c in available_turnon_cols}
    pilot_keyed = pilot_map.rename(columns={"SUBENTITY": "__PILOT_KEY", **turnon_rename})
    merged = out.merge(pilot_keyed, on="__PILOT_KEY", how="left")

    data_time = pd.to_datetime(merged[time_col], errors="coerce")
    for col in selected_columns:
        col_time = pd.to_datetime(merged[f"__TURNON_{col}"], errors="coerce")
        merged[col] = (col_time.notna() & data_time.notna() & (col_time < data_time)).map({True: "ON", False: "OFF"})

    for required_col in [c for c in PILOT_COLUMNS if c != "TS"]:
        if required_col not in merged.columns:
            merged[required_col] = "OFF"

    merged["PILOT_STATUS"] = _create_pilot_status(merged)
    merged = merged.drop(
        columns=["__PILOT_KEY", *[f"__TURNON_{c}" for c in available_turnon_cols]],
        errors="ignore",
    )
    return _reorder_inline_pilot_block(merged)


def _normalize_key(df: pd.DataFrame, time_col: str) -> pd.Series:
    time_norm = pd.to_datetime(df[time_col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    return (
        df["LOT7"].astype(str).str.strip()
        + "|"
        + df["WAFER_ID"].astype(str).str.strip()
        + "|"
        + df["LAYER"].astype(str).str.strip()
        + "|"
        + time_norm.fillna("")
    )


def _pick_time_col(df: pd.DataFrame) -> str:
    if "INSPECT_TIME" in df.columns:
        return "INSPECT_TIME"
    if "INSPECTION_TIME" in df.columns:
        return "INSPECTION_TIME"
    raise KeyError("Expected INSPECT_TIME or INSPECTION_TIME")


def _sync_inline_coords_from_wafer(coords_df: pd.DataFrame, wafer_df: pd.DataFrame, selected_columns: List[str]) -> pd.DataFrame:
    required = {"LOT7", "WAFER_ID", "LAYER"}
    if not required.issubset(coords_df.columns):
        missing = sorted(required - set(coords_df.columns))
        raise KeyError(f"Inline coords missing key columns: {missing}")
    if not required.issubset(wafer_df.columns):
        missing = sorted(required - set(wafer_df.columns))
        raise KeyError(f"Inline wafer missing key columns: {missing}")

    coords_time_col = _pick_time_col(coords_df)
    wafer_time_col = _pick_time_col(wafer_df)

    cols_to_sync = [*selected_columns, "PILOT_STATUS"]
    for col in cols_to_sync:
        if col not in wafer_df.columns:
            raise KeyError(f"Inline wafer output missing expected column: {col}")

    wafer = wafer_df[["LOT7", "WAFER_ID", "LAYER", wafer_time_col, *cols_to_sync]].copy()
    wafer["__SYNC_KEY"] = _normalize_key(wafer, wafer_time_col)
    wafer = wafer.drop_duplicates(subset=["__SYNC_KEY"], keep="last")
    wafer = wafer.rename(columns={col: f"{col}__SRC" for col in cols_to_sync})

    out = coords_df.copy()
    out["__SYNC_KEY"] = _normalize_key(out, coords_time_col)
    merged = out.merge(wafer[["__SYNC_KEY", *[f"{c}__SRC" for c in cols_to_sync]]], on="__SYNC_KEY", how="left")

    for col in cols_to_sync:
        src_col = f"{col}__SRC"
        if col in merged.columns:
            merged[col] = merged[src_col].where(merged[src_col].notna(), merged[col])
        else:
            merged[col] = merged[src_col]

    merged = merged.drop(columns=["__SYNC_KEY", *[f"{c}__SRC" for c in cols_to_sync]], errors="ignore")
    return _reorder_inline_pilot_block(merged)


def _update_surf_file(df: pd.DataFrame, selected_columns: List[str], time_col: str) -> pd.DataFrame:
    recomputed = surf_add_pilot_status(df.copy(), time_col=time_col)
    out = df.copy()

    for col in [*selected_columns, "PILOT_STATUS"]:
        if col in recomputed.columns:
            out[col] = recomputed[col]

    return _reorder_surf_pilot_block(out)


def _validate_selected_columns(columns: Iterable[str]) -> List[str]:
    normalized = []
    for col in columns:
        upper = col.upper()
        if upper not in PILOT_COLUMNS:
            raise ValueError(f"Unsupported pilot column: {col}. Allowed: {', '.join(PILOT_COLUMNS)}")
        if upper not in normalized:
            normalized.append(upper)
    return normalized


def _write_output(df: pd.DataFrame, source_path: Path, write_mode: str, suffix: str) -> Path | None:
    if write_mode == "dry-run":
        return None

    if write_mode == "apply":
        destination = source_path
    else:
        destination = source_path.with_name(f"{source_path.stem}{suffix}{source_path.suffix}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destination, index=False)
    return destination


def _summarize_changes(name: str, before: pd.DataFrame, after: pd.DataFrame, tracked_cols: List[str], output_path: Path | None) -> UpdateSummary:
    changed_by_column: Dict[str, int] = {}
    for col in tracked_cols:
        if col in before.columns or col in after.columns:
            before_col = before[col] if col in before.columns else pd.Series([pd.NA] * len(before))
            after_col = after[col] if col in after.columns else pd.Series([pd.NA] * len(after))
            changed_by_column[col] = _changed_count(before_col, after_col)

    return UpdateSummary(
        name=name,
        rows=len(after),
        changed_by_column=changed_by_column,
        output_path=output_path,
    )


def _process_inline(selected_columns: List[str], write_mode: str, suffix: str) -> List[UpdateSummary]:
    summaries: List[UpdateSummary] = []

    wafer_path = PIPELINE_PATHS.extended_output_csv
    coords_path = PIPELINE_PATHS.defect_coordinates_csv

    if not wafer_path.exists():
        raise FileNotFoundError(f"Inline wafer file missing: {wafer_path}")
    if not coords_path.exists():
        raise FileNotFoundError(f"Inline coordinates file missing: {coords_path}")

    pilot_map = _load_pilot_dates()

    wafer_before = pd.read_csv(wafer_path, low_memory=False)
    wafer_after = _update_inline_wafer(wafer_before, selected_columns, pilot_map)
    wafer_out = _write_output(wafer_after, wafer_path, write_mode, suffix)
    summaries.append(
        _summarize_changes(
            "inline_wafer",
            wafer_before,
            wafer_after,
            [*selected_columns, "PILOT_STATUS"],
            wafer_out,
        )
    )

    coords_before = pd.read_csv(coords_path, low_memory=False)
    coords_after = _sync_inline_coords_from_wafer(coords_before, wafer_after, selected_columns)
    coords_out = _write_output(coords_after, coords_path, write_mode, suffix)
    summaries.append(
        _summarize_changes(
            "inline_coordinates",
            coords_before,
            coords_after,
            [*selected_columns, "PILOT_STATUS"],
            coords_out,
        )
    )

    return summaries


def _process_surf(selected_columns: List[str], write_mode: str, suffix: str) -> List[UpdateSummary]:
    summaries: List[UpdateSummary] = []
    targets: List[Tuple[str, Path, str]] = [
        ("surf_metrics", PIPELINE_PATHS.surf_metrics_csv, "INSPECTION_TIME"),
        ("surf_coordinates", PIPELINE_PATHS.surf_coordinates_csv, "INSPECTION_TIME"),
    ]

    for name, path, time_col in targets:
        if not path.exists():
            raise FileNotFoundError(f"SURF output file missing: {path}")

        before = pd.read_csv(path, low_memory=False)
        after = _update_surf_file(before, selected_columns, time_col=time_col)
        out = _write_output(after, path, write_mode, suffix)
        summaries.append(_summarize_changes(name, before, after, [*selected_columns, "PILOT_STATUS"], out))

    return summaries


def _print_summary(write_mode: str, summaries: List[UpdateSummary]) -> None:
    print(f"write_mode={write_mode}")
    for summary in summaries:
        print(f"{summary.name}: rows={summary.rows}")
        for col, count in summary.changed_by_column.items():
            print(f"  {col}: changed_rows={count}")
        if summary.output_path:
            print(f"  output={summary.output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reparse pilot columns from turn-on-date CSV into inline/surf production outputs. "
            "Supports selective columns (default TS) and inline coordinates pilot-field sync."
        )
    )
    parser.add_argument(
        "--pipeline",
        choices=["inline", "surf", "both"],
        default="both",
        help="Pipeline scope to process",
    )
    parser.add_argument(
        "--columns",
        nargs="+",
        default=["TS"],
        help="Pilot columns to refresh (default: TS)",
    )
    parser.add_argument(
        "--write-mode",
        choices=["dry-run", "sidecar", "apply"],
        default="dry-run",
        help="dry-run: no write, sidecar: write *_reparsed.csv, apply: overwrite originals",
    )
    parser.add_argument(
        "--sidecar-suffix",
        default="_reparsed",
        help="Suffix for sidecar outputs when --write-mode sidecar",
    )
    args = parser.parse_args()

    selected_columns = _validate_selected_columns(args.columns)

    summaries: List[UpdateSummary] = []
    if args.pipeline in {"inline", "both"}:
        summaries.extend(_process_inline(selected_columns, write_mode=args.write_mode, suffix=args.sidecar_suffix))
    if args.pipeline in {"surf", "both"}:
        summaries.extend(_process_surf(selected_columns, write_mode=args.write_mode, suffix=args.sidecar_suffix))

    _print_summary(args.write_mode, summaries)


if __name__ == "__main__":
    main()
