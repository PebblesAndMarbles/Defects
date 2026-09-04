from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS


LONG_KEY_COLUMNS = ["ACTUAL_LOT@DEFECT", "WAFER_ID", "LAYER", "INSPECTION_TIME@DEFECT"]
PRODUCTION_KEY_COLUMNS = ["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME"]

LONG_NCDD_COLUMNS = [
    "DEFECT@WAFER@CLASS_NCDD@BEEP",
    "DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE",
]
LONG_EDI_COLUMNS = [
    "DEFECT@WAFER@CLASS_EDI@BEEP",
    "DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE",
]

REQUIRED_LONG_COLUMNS = LONG_KEY_COLUMNS + LONG_NCDD_COLUMNS + LONG_EDI_COLUMNS
REQUIRED_PRODUCTION_COLUMNS = [
    "LOT",
    "WAFER_ID",
    "LAYER",
    "INSPECT_TIME",
    "BEEP_NCDD",
    "SMP_NCDD",
    "BEEP_EDI",
    "SMP_EDI",
]

RECLASS_RELATIVE_DIFF_THRESHOLD = 0.01


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Source CSV not found: {path}")
    return pd.read_csv(path, low_memory=False)


def _safe_time(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", format="mixed")


def _validate_columns(df: pd.DataFrame, required: list[str], *, label: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"{label} missing required columns: {missing}")


def _row_type_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    ncdd_cols = [column for column in df.columns if "CLASS_NCDD" in column]
    edi_cols = [column for column in df.columns if "CLASS_EDI" in column]
    ncdd_mask = df[ncdd_cols].notna().any(axis=1) if ncdd_cols else pd.Series(False, index=df.index)
    edi_mask = df[edi_cols].notna().any(axis=1) if edi_cols else pd.Series(False, index=df.index)
    return ncdd_mask, edi_mask


def _dedup_rows(df: pd.DataFrame, key_columns: list[str], *, time_column: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    work[time_column] = _safe_time(work[time_column])
    return work.sort_values(key_columns).drop_duplicates(subset=key_columns, keep="last").reset_index(drop=True)


def _build_long_metric_frame(path: Path) -> pd.DataFrame:
    df = _read_csv(path)
    _validate_columns(df, REQUIRED_LONG_COLUMNS, label=str(path))

    ncdd_mask, edi_mask = _row_type_masks(df)
    ncdd_rows = df.loc[ncdd_mask, LONG_KEY_COLUMNS + LONG_NCDD_COLUMNS].copy()
    edi_rows = df.loc[edi_mask, LONG_KEY_COLUMNS + LONG_EDI_COLUMNS].copy()

    ncdd_rows = _dedup_rows(ncdd_rows, LONG_KEY_COLUMNS, time_column="INSPECTION_TIME@DEFECT")
    edi_rows = _dedup_rows(edi_rows, LONG_KEY_COLUMNS, time_column="INSPECTION_TIME@DEFECT")

    ncdd_rows = ncdd_rows.rename(
        columns={
            "DEFECT@WAFER@CLASS_NCDD@BEEP": "LONG_BEEP_NCDD",
            "DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE": "LONG_SMP_NCDD",
        }
    )
    edi_rows = edi_rows.rename(
        columns={
            "DEFECT@WAFER@CLASS_EDI@BEEP": "LONG_BEEP_EDI",
            "DEFECT@WAFER@CLASS_EDI@SMALL_PARTICLE": "LONG_SMP_EDI",
        }
    )

    for frame in (ncdd_rows, edi_rows):
        frame["INSPECTION_TIME@DEFECT"] = _safe_time(frame["INSPECTION_TIME@DEFECT"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    return ncdd_rows.merge(edi_rows, on=LONG_KEY_COLUMNS, how="outer")


def _load_long_sources() -> pd.DataFrame:
    frames = []
    for source_layer, path in [("M5", PIPELINE_PATHS.m5_ncdd_edi_long_csv), ("M6", PIPELINE_PATHS.m6_ncdd_edi_long_csv)]:
        frame = _build_long_metric_frame(path)
        frame = frame.copy()
        frame["SOURCE_LAYER"] = source_layer
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def _load_production_frame() -> pd.DataFrame:
    production = _read_csv(PIPELINE_PATHS.extended_output_csv)
    _validate_columns(production, REQUIRED_PRODUCTION_COLUMNS, label="production CSV")
    production = production.copy()
    production["INSPECT_TIME"] = _safe_time(production["INSPECT_TIME"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    production = production.sort_values(PRODUCTION_KEY_COLUMNS).drop_duplicates(subset=PRODUCTION_KEY_COLUMNS, keep="last")
    return production.reset_index(drop=True)


def _value_changed(left: pd.Series, right: pd.Series) -> pd.Series:
    left_num = pd.to_numeric(left, errors="coerce")
    right_num = pd.to_numeric(right, errors="coerce")
    both_null = left_num.isna() & right_num.isna()
    numeric_mask = ~(left_num.isna() | right_num.isna())

    denominator = left_num.abs().where(left_num.abs() >= right_num.abs(), right_num.abs())
    denominator = denominator.where(denominator > 0, 1.0)
    relative_diff = (left_num - right_num).abs() / denominator

    significant_numeric_change = numeric_mask & (relative_diff > RECLASS_RELATIVE_DIFF_THRESHOLD)
    non_numeric_change = (~numeric_mask) & ((left.isna() != right.isna()) | (left.astype(str) != right.astype(str)))
    return (~both_null) & (significant_numeric_change | non_numeric_change)


def _build_change_log(compare: pd.DataFrame) -> pd.DataFrame:
    rows = []
    valid_source = compare["SOURCE_LAYER"].notna() if "SOURCE_LAYER" in compare.columns else pd.Series(True, index=compare.index)
    for long_column, prod_column, component in [
        ("LONG_BEEP_NCDD", "BEEP_NCDD", "BEEP"),
        ("LONG_SMP_NCDD", "SMP_NCDD", "SMALL_PARTICLE"),
        ("LONG_BEEP_EDI", "BEEP_EDI", "BEEP"),
        ("LONG_SMP_EDI", "SMP_EDI", "SMALL_PARTICLE"),
    ]:
        if long_column not in compare.columns:
            continue
        source_and_value_mask = valid_source & compare[long_column].notna()
        changed = compare.loc[source_and_value_mask].copy()
        if changed.empty:
            continue
        changed_mask = _value_changed(changed[long_column], changed[prod_column])
        changed = changed.loc[changed_mask].copy()
        if changed.empty:
            continue
        changed["METRIC_TYPE"] = "EDI" if "EDI" in long_column else "NCDD"
        changed["COMPONENT"] = component
        changed["OLD_VALUE"] = changed[prod_column]
        changed["NEW_VALUE"] = changed[long_column]
        changed["LONG_NCDD_BEEP"] = changed.get("LONG_BEEP_NCDD")
        changed["LONG_NCDD_SMP"] = changed.get("LONG_SMP_NCDD")
        changed["LONG_EDI_BEEP"] = changed.get("LONG_BEEP_EDI")
        changed["LONG_EDI_SMP"] = changed.get("LONG_SMP_EDI")
        rows.append(changed)

    if not rows:
        return compare.iloc[0:0].copy()

    result = pd.concat(rows, ignore_index=True, sort=False)
    result["LOGGED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return result


def _append_reclass_log(changes: pd.DataFrame) -> Path:
    target = PIPELINE_PATHS.ncdd_edi_reclass_log_csv
    target.parent.mkdir(parents=True, exist_ok=True)

    if changes.empty:
        if not target.exists():
            target.write_text(
                "SOURCE_LAYER,LOT,WAFER_ID,LAYER,INSPECT_TIME,METRIC_TYPE,COMPONENT,OLD_VALUE,NEW_VALUE,LONG_NCDD_BEEP,LONG_NCDD_SMP,LONG_EDI_BEEP,LONG_EDI_SMP,LOGGED_AT\n",
                encoding="utf-8",
            )
        return target

    output = changes.copy()
    output = output[
        [
            "SOURCE_LAYER",
            "LOT",
            "WAFER_ID",
            "LAYER",
            "INSPECT_TIME",
            "METRIC_TYPE",
            "COMPONENT",
            "OLD_VALUE",
            "NEW_VALUE",
            "LONG_NCDD_BEEP",
            "LONG_NCDD_SMP",
            "LONG_EDI_BEEP",
            "LONG_EDI_SMP",
            "LOGGED_AT",
        ]
    ]

    if target.exists():
        existing = pd.read_csv(target, low_memory=False)
        combined = pd.concat([existing, output], ignore_index=True, sort=False)
    else:
        combined = output

    combined = combined.drop_duplicates(
        subset=[
            "SOURCE_LAYER",
            "LOT",
            "WAFER_ID",
            "LAYER",
            "INSPECT_TIME",
            "METRIC_TYPE",
            "COMPONENT",
            "OLD_VALUE",
            "NEW_VALUE",
            "LONG_NCDD_BEEP",
            "LONG_NCDD_SMP",
            "LONG_EDI_BEEP",
            "LONG_EDI_SMP",
        ],
        keep="last",
    ).reset_index(drop=True)

    temp_target = target.with_name(f"{target.stem}.tmp{target.suffix}")
    combined.to_csv(temp_target, index=False)

    try:
        os.replace(temp_target, target)
        return target
    except PermissionError:
        # Fall back to a sidecar log so the audit still completes on locked shares.
        sidecar = target.with_name(f"{target.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{target.suffix}")
        os.replace(temp_target, sidecar)
        return sidecar

    return target


def _overlay_long_metrics(production: pd.DataFrame, long_frame: pd.DataFrame) -> pd.DataFrame:
    compare = production.merge(
        long_frame,
        left_on=PRODUCTION_KEY_COLUMNS,
        right_on=LONG_KEY_COLUMNS,
        how="left",
        suffixes=("_PROD", "_LONG"),
    )

    compare["LOT"] = compare["LOT"].fillna(compare["ACTUAL_LOT@DEFECT"])
    compare["INSPECT_TIME"] = compare["INSPECT_TIME"].fillna(_safe_time(compare["INSPECTION_TIME@DEFECT"]).dt.strftime("%Y-%m-%d %H:%M:%S"))

    for prod_col, long_col in [("BEEP_NCDD", "LONG_BEEP_NCDD"), ("SMP_NCDD", "LONG_SMP_NCDD")]:
        if long_col in compare.columns:
            compare[prod_col] = compare[long_col].combine_first(compare[prod_col])

    for prod_col, long_col in [("BEEP_EDI", "LONG_BEEP_EDI"), ("SMP_EDI", "LONG_SMP_EDI")]:
        if long_col in compare.columns:
            compare[prod_col] = compare[long_col].combine_first(compare[prod_col])

    return compare[production.columns]


def _refresh_derived_outputs(updated_extended: pd.DataFrame) -> Path:
    updated_extended.to_csv(PIPELINE_PATHS.extended_output_csv, index=False)
    sixty_day_path = PIPELINE_PATHS.extended_output_csv.with_name(
        f"{PIPELINE_PATHS.extended_output_csv.stem}_60DAY{PIPELINE_PATHS.extended_output_csv.suffix}"
    )
    time_col = "INSPECT_TIME" if "INSPECT_TIME" in updated_extended.columns else "INSPECTION_TIME"
    work = updated_extended.copy()
    work[time_col] = _safe_time(work[time_col])
    newest = work[time_col].max()
    if pd.isna(newest):
        subset = work.iloc[0:0].copy()
    else:
        cutoff = newest - pd.Timedelta(days=60)
        subset = work[work[time_col] >= cutoff].copy()
    subset.to_csv(sixty_day_path, index=False)
    return sixty_day_path


def run_long_reclass_audit() -> Path:
    long_frame = _load_long_sources()
    production = _load_production_frame()
    compare = production.merge(
        long_frame,
        left_on=PRODUCTION_KEY_COLUMNS,
        right_on=LONG_KEY_COLUMNS,
        how="left",
        suffixes=("_PROD", "_LONG"),
    )
    changes = _build_change_log(compare)
    updated = _overlay_long_metrics(production, long_frame)
    _append_reclass_log(changes)
    _refresh_derived_outputs(updated)
    return PIPELINE_PATHS.ncdd_edi_reclass_log_csv