from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline_config import PIPELINE_PATHS

PILOT_COLUMNS = ["CCMR2", "ICCR2", "GF", "CV", "SRCIP", "TS"]


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


def _ensure_ts_position(df: pd.DataFrame) -> pd.DataFrame:
    pilot_block = ["SRCIP", "CCMR2", "ICCR2", "CV", "GF", "TS", "PILOT_STATUS"]
    present = [c for c in pilot_block if c in df.columns]
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


def _add_pilot_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.drop(columns=PILOT_COLUMNS, errors="ignore")

    key_col = "SUBENTITY"
    if key_col not in out.columns:
        raise KeyError("Expected SUBENTITY column in wafer output")

    time_col = "SUBENTITY_END_TIME" if "SUBENTITY_END_TIME" in out.columns else "INSPECT_TIME"
    if time_col not in out.columns:
        raise KeyError("Expected SUBENTITY_END_TIME or INSPECT_TIME column in wafer output")

    pilot_path = PIPELINE_PATHS.pilot_dates_path
    if not pilot_path.exists():
        raise FileNotFoundError(f"Pilot turn-on file missing: {pilot_path}")

    pilot_df = pd.read_csv(pilot_path, low_memory=False)
    if key_col not in pilot_df.columns:
        raise KeyError(f"Expected {key_col} in pilot turn-on file")

    available_cols = [c for c in PILOT_COLUMNS if c in pilot_df.columns]
    if not available_cols:
        raise KeyError("No pilot columns found in pilot turn-on file")

    merge_cols = [key_col] + available_cols
    pilot_map = pilot_df[merge_cols].copy()
    for col in available_cols:
        pilot_map[col] = pd.to_datetime(pilot_map[col], errors="coerce")

    out["__PILOT_KEY"] = out[key_col].astype(str)
    pilot_map = pilot_map.rename(columns={key_col: "__PILOT_KEY"})
    merged = out.merge(pilot_map, on="__PILOT_KEY", how="left")

    data_time = pd.to_datetime(merged[time_col], errors="coerce")
    for col in PILOT_COLUMNS:
        if col in available_cols:
            col_time = pd.to_datetime(merged[col], errors="coerce")
            merged[col] = (col_time.notna() & data_time.notna() & (col_time < data_time)).map({True: "ON", False: "OFF"})
        else:
            merged[col] = "OFF"

    merged["PILOT_STATUS"] = _create_pilot_status(merged)
    merged = merged.drop(columns=["__PILOT_KEY"], errors="ignore")
    merged = _ensure_ts_position(merged)
    return merged


def _backfill_one(path: Path, apply: bool) -> None:
    if not path.exists():
        print(f"SKIP missing: {path}")
        return

    df = pd.read_csv(path, low_memory=False)
    out = _add_pilot_columns(df)

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
        description="Backfill pilot flags (SRCIP/CCMR2/ICCR2/CV/GF/TS) and PILOT_STATUS into wafer production CSV"
    )
    parser.add_argument("--apply", action="store_true", help="Write changes in place (default dry-run)")
    args = parser.parse_args()

    _backfill_one(PIPELINE_PATHS.extended_output_csv, apply=args.apply)


if __name__ == "__main__":
    main()
