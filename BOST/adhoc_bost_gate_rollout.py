"""
Adhoc BOST rollout for defect wafers (8M5CL/8M6CL) with validation gates.

Gate flow:
  0) Freeze inputs and constants
  1) Schema and layer mapping validation
  2) Pilot manifest creation
  3) Pilot BOST query validation
  4) Pilot join-back validation metrics
  5) Full dry run
  6) Final production outputs
"""

from __future__ import annotations

import json
import random
import re
import time
import warnings
from datetime import datetime
from pathlib import Path
import pandas as pd
import PyUber

warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")


# Constants
DSN = "D1D_PROD_XEUS_GAJT"
PROCESS = "1278"
FAB = "D1D"
IS_LATEST = "Y"
IS_ACTIVE = "Y"

SEED = 1278
PILOT_TARGET_TOTAL = 100
PILOT_TARGET_PER_LAYER = 50
ALLOWED_LAYERS = {"8M5CL", "8M6CL"}

REGISTRY_DIR = Path(__file__).resolve().parent / "registry"
TRACK_B_SCOPE_CANDIDATES = [
    REGISTRY_DIR / "definition_registry_treatment_rules.csv",
    REGISTRY_DIR / "step2_definition_registry_seed_20260909.csv",
    REGISTRY_DIR / "step1_definition_registry_seed_20260909.csv",
]

TRACK_B_REGISTRY_COLUMNS = [
    "PROCESS",
    "FAB",
    "ALIAS",
    "OPERATION",
    "DEFINITION_ID",
    "DEFINITION_NAME",
    "TREATMENT_TYPE",
    "BACKLOAD_START_DATE",
    "VERSION",
    "IS_LATEST",
    "IS_ACTIVE",
    "FIRST_SEEN_RUN_DATE",
    "LAST_SEEN_RUN_DATE",
    "STATUS",
    "RESOLVED_ALIAS",
    "PROCESS_FAMILY",
]

FULL_FLOW_ALIASES = [
    "L_8M5_SIARC_DEP",
    "L_8M5_CHM_DEP",
    "L_8M5_SED",
    "E_8M5_HM_ETCH",
    "W_8M5_HM_CLN",
    "L_8M6_SIARC_DEP",
    "L_8M6_CHM_DEP",
    "L_8M6_SED",
    "E_8M6_HM_ETCH",
    "W_8M6_HM_CLN",
]

def _to_workspace_root() -> Path:
    # Script is in BOST/, root is parent.
    return Path(__file__).resolve().parents[1]


def _lot_to_lot7(lot: str) -> str:
    lot = str(lot).strip()
    return lot[:7] if len(lot) >= 7 else lot


def _validate_required_columns(df: pd.DataFrame) -> None:
    required = {"LOT", "WAFER_ID", "LAYER"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _print_gate(msg: str) -> None:
    print(f"\n[{_now()}] {msg}")


def _validate_layers(df: pd.DataFrame) -> list[str]:
    layers = sorted(df["LAYER"].dropna().astype(str).unique().tolist())
    unexpected = sorted(set(layers) - ALLOWED_LAYERS)
    if unexpected:
        raise ValueError(f"Unexpected LAYER values for adhoc scope: {unexpected}")
    return layers


def _build_keys(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[["LOT", "WAFER_ID", "LAYER"]]
        .dropna(subset=["LOT", "WAFER_ID", "LAYER"])
        .astype({"LOT": str, "WAFER_ID": str, "LAYER": str})
        .drop_duplicates()
        .reset_index(drop=True)
    )


def _sample_layer(df_layer: pd.DataFrame, n: int, rng: random.Random) -> pd.DataFrame:
    if len(df_layer) <= n:
        return df_layer.copy()
    idx = list(df_layer.index)
    rng.shuffle(idx)
    picked = idx[:n]
    return df_layer.loc[picked].copy()


def _build_pilot_manifest(keys: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    parts = []
    for layer in sorted(ALLOWED_LAYERS):
        layer_df = keys[keys["LAYER"] == layer].copy()
        # Prefer lot diversity: one key per lot first, then top up.
        layer_df = layer_df.sort_values(["LOT", "WAFER_ID"]).reset_index(drop=True)
        one_per_lot = layer_df.drop_duplicates(subset=["LOT"], keep="first")
        picked = _sample_layer(one_per_lot, PILOT_TARGET_PER_LAYER, rng)
        if len(picked) < PILOT_TARGET_PER_LAYER:
            remaining = layer_df.merge(picked, how="left", indicator=True)
            remaining = remaining[remaining["_merge"] == "left_only"].drop(columns=["_merge"])
            top_up = _sample_layer(remaining, PILOT_TARGET_PER_LAYER - len(picked), rng)
            picked = pd.concat([picked, top_up], ignore_index=True)
        parts.append(picked)
    manifest = pd.concat(parts, ignore_index=True).drop_duplicates()
    return manifest.sort_values(["LAYER", "LOT", "WAFER_ID"]).reset_index(drop=True)


def _layer_from_alias(alias: str) -> str | None:
    """
    Derive LAYER (8M5CL or 8M6CL) from RESOLVED_ALIAS.
    Aliases have format: {prefix}_{layer}_{step}, e.g., L_8M5_SIARC_DEP -> 8M5CL
    """
    m = re.search(r"8M(\d+)", str(alias))
    if not m:
        return None
    return f"8M{int(m.group(1))}CL"


def _read_track_b_registry_snapshot() -> pd.DataFrame:
    for candidate_path in TRACK_B_SCOPE_CANDIDATES:
        if candidate_path.exists():
            try:
                return pd.read_csv(candidate_path, dtype=str).fillna("")
            except Exception:
                continue
    return pd.DataFrame(columns=TRACK_B_REGISTRY_COLUMNS)


def _materialize_track_b_registry(df_track_b: pd.DataFrame) -> pd.DataFrame:
    if df_track_b.empty:
        return df_track_b

    today = datetime.now().strftime("%Y-%m-%d")
    registry_path = TRACK_B_SCOPE_CANDIDATES[0]
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    current = df_track_b.copy()
    current["RESOLVED_ALIAS"] = current["TRIGGER_OPERATION"].astype(str).str.strip()
    current["ALIAS"] = current["RESOLVED_ALIAS"]
    current["OPERATION"] = current["RESOLVED_ALIAS"]
    current["PROCESS"] = PROCESS
    current["FAB"] = FAB
    if "DEFINITION_ID" not in current.columns:
        current["DEFINITION_ID"] = ""
    if "TREATMENT_TYPE" not in current.columns:
        current["TREATMENT_TYPE"] = ""
    if "BACKLOAD_START_DATE" not in current.columns:
        current["BACKLOAD_START_DATE"] = ""
    if "VERSION" not in current.columns:
        current["VERSION"] = ""
    if "IS_LATEST" not in current.columns:
        current["IS_LATEST"] = IS_LATEST
    if "IS_ACTIVE" not in current.columns:
        current["IS_ACTIVE"] = IS_ACTIVE
    if "PROCESS_FAMILY" not in current.columns:
        current["PROCESS_FAMILY"] = ""
    current["FIRST_SEEN_RUN_DATE"] = today
    current["LAST_SEEN_RUN_DATE"] = today
    current["STATUS"] = "NEW"

    current_rows = current.copy()
    for column in TRACK_B_REGISTRY_COLUMNS:
        if column not in current_rows.columns:
            current_rows[column] = ""
    current_rows = current_rows[TRACK_B_REGISTRY_COLUMNS].fillna("")
    current_rows = current_rows.drop_duplicates(subset=["ALIAS", "DEFINITION_NAME"], keep="first")

    previous_rows = _read_track_b_registry_snapshot()
    if not previous_rows.empty:
        previous_rows = previous_rows.copy()
        if "RESOLVED_ALIAS" not in previous_rows.columns and "TRIGGER_OPERATION" in previous_rows.columns:
            previous_rows = previous_rows.rename(columns={"TRIGGER_OPERATION": "RESOLVED_ALIAS"})
        if "ALIAS" not in previous_rows.columns and "RESOLVED_ALIAS" in previous_rows.columns:
            previous_rows["ALIAS"] = previous_rows["RESOLVED_ALIAS"]
        if "OPERATION" not in previous_rows.columns and "RESOLVED_ALIAS" in previous_rows.columns:
            previous_rows["OPERATION"] = previous_rows["RESOLVED_ALIAS"]
        for column in TRACK_B_REGISTRY_COLUMNS:
            if column not in previous_rows.columns:
                previous_rows[column] = ""
        previous_rows = previous_rows[TRACK_B_REGISTRY_COLUMNS].fillna("")
        previous_rows = previous_rows.drop_duplicates(subset=["ALIAS", "DEFINITION_NAME"], keep="last")
    else:
        previous_rows = pd.DataFrame(columns=TRACK_B_REGISTRY_COLUMNS)

    current_key = current_rows[["ALIAS", "DEFINITION_NAME"]].drop_duplicates()
    previous_key = previous_rows[["ALIAS", "DEFINITION_NAME"]].drop_duplicates()
    merged_keys = current_key.merge(previous_key, on=["ALIAS", "DEFINITION_NAME"], how="outer", indicator=True)

    current_lookup = current_rows.set_index(["ALIAS", "DEFINITION_NAME"], drop=False)
    previous_lookup = previous_rows.set_index(["ALIAS", "DEFINITION_NAME"], drop=False)

    result_rows: list[dict[str, str]] = []
    new_rows: list[dict[str, str]] = []

    for _, key_row in merged_keys.iterrows():
        key = (key_row["ALIAS"], key_row["DEFINITION_NAME"])
        merge_state = key_row["_merge"]
        if merge_state == "both":
            row = previous_lookup.loc[key].to_dict() if key in previous_lookup.index else current_lookup.loc[key].to_dict()
            row.update(current_lookup.loc[key].to_dict())
            row["FIRST_SEEN_RUN_DATE"] = previous_lookup.loc[key]["FIRST_SEEN_RUN_DATE"] if key in previous_lookup.index else today
            row["LAST_SEEN_RUN_DATE"] = today
            row["STATUS"] = "EXISTING"
            result_rows.append(row)
        elif merge_state == "left_only":
            row = current_lookup.loc[key].to_dict()
            row["FIRST_SEEN_RUN_DATE"] = today
            row["LAST_SEEN_RUN_DATE"] = today
            row["STATUS"] = "NEW"
            result_rows.append(row)
            new_rows.append(row)
        else:
            row = previous_lookup.loc[key].to_dict()
            row["STATUS"] = "RETIRED"
            result_rows.append(row)

    result_df = pd.DataFrame(result_rows, columns=TRACK_B_REGISTRY_COLUMNS).fillna("")
    result_df = result_df.sort_values(["ALIAS", "DEFINITION_NAME"]).reset_index(drop=True)
    result_df.to_csv(registry_path, index=False)

    new_df = pd.DataFrame(new_rows, columns=TRACK_B_REGISTRY_COLUMNS).fillna("")
    if not new_df.empty:
        print(f"[TRACK B REGISTRY] NEW definitions: {len(new_df)}")
        preview_cols = ["ALIAS", "DEFINITION_NAME", "STATUS", "FIRST_SEEN_RUN_DATE"]
        print(new_df[preview_cols].head(20).to_string(index=False))
        new_path = _to_workspace_root() / "artifacts" / f"definition_registry_new_{today}.csv"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_df.to_csv(new_path, index=False)
        print(f"[TRACK B REGISTRY] NEW snapshot written: {new_path}")
    else:
        print("[TRACK B REGISTRY] NEW definitions: 0")

    return df_track_b


def _run_bost_query_treatment_rules(conn, keys: pd.DataFrame) -> pd.DataFrame:
    """Treatment-rules-only BOST query used for the final enrichment output."""
    lots = sorted(keys["LOT"].dropna().astype(str).unique().tolist())
    lot7s = sorted({_lot_to_lot7(lot) for lot in lots if str(lot).strip()})
    wafers = sorted(keys["WAFER_ID"].dropna().astype(str).unique().tolist())
    lot_sql = ", ".join("'" + lot.replace("'", "''") + "'" for lot in lot7s)
    oper_sql = ", ".join("'" + op.replace("'", "''") + "'" for op in FULL_FLOW_ALIASES)

    query_track_b = f"""
WITH wkeys AS (
SELECT /*+ MATERIALIZE INDEX(m X3B_META_WAFER_FAB) parallel(m,16) */
    m.LOT
  ,m.WAFER
  ,m.WAFER_KEY
FROM B_META_WAFER_FAB m
WHERE m.LOT7 IN ({lot_sql})
)
, tpids AS (
SELECT /*+ MATERIALIZE */ DISTINCT
   p.TREATMENT_PARAMETER_ID
  ,p.TREATMENT_PARAMETER_NAME
  ,p.OPER_NAME
FROM B_CFG_TREATMENT_DEFN defn
INNER JOIN B_CFG_TREATMENT_PARAMETERS p
    ON  p.TREATMENT_ID = defn.TREATMENT_ID
  AND p.STATUS = 'ACTIVE'
  AND p.OPER_NAME IN ({oper_sql})
WHERE defn.PROCESS = '{PROCESS}'
    AND defn.IS_VALID = 'Y'
    AND defn.INITIAL_RUN_COMPLETED = 'Y'
    AND defn.IS_ACTIVE = 'Y'
)
SELECT /*+ ORDERED INDEX(d XPK_B_WAFER_TREATMENT_RULES) parallel(d,16) */
   w.LOT
  ,w.WAFER
  ,p.OPER_NAME AS TRIGGER_OPERATION
  ,p.TREATMENT_PARAMETER_NAME AS DEFINITION_NAME
  ,l.LABEL_NAME AS PROC_STRING_VALUE
FROM wkeys w
CROSS JOIN tpids p
INNER JOIN B_WAFER_TREATMENT_RULES rules
    ON  rules.WAFER_KEY = w.WAFER_KEY
    AND rules.TREATMENT_PARAMETER_ID = p.TREATMENT_PARAMETER_ID
    AND rules.LATEST_DATA = 'Y'
INNER JOIN B_STRUCT_TREATMENT_LABELS l
    ON  l.LABEL_ID = rules.LABEL_ID
"""

    df_track_b = pd.read_sql(query_track_b, conn)
    if df_track_b.empty:
        return df_track_b
    _materialize_track_b_registry(df_track_b)
    df_track_b["LAYER"] = df_track_b["TRIGGER_OPERATION"].map(_layer_from_alias)
    df_track_b["PROCESS_FAMILY"] = ""
    df_track_b["USAGE"] = "Production"
    df_track_b["VERSION"] = ""
    df_track_b["IS_LATEST"] = "Y"
    df_track_b["IS_ACTIVE"] = "Y"
    df_track_b["PROC_STRING_VALUE"] = df_track_b["PROC_STRING_VALUE"].astype(str)
    df_track_b["SOURCE_SYSTEM"] = "TREATMENT_RULES"
    df_track_b["DEFINITION_NAME"] = df_track_b["DEFINITION_NAME"].astype(str)
    df_track_b = df_track_b[[
        "LOT", "WAFER", "LAYER", "PROCESS_FAMILY", "TRIGGER_OPERATION",
        "DEFINITION_NAME", "USAGE", "VERSION", "IS_LATEST", "IS_ACTIVE",
        "PROC_STRING_VALUE", "SOURCE_SYSTEM"
    ]]
    return df_track_b


def _normalize_operation_suffix(operation: str) -> str:
    """
    Strip layer identifier from operation name.

        Removes layer prefixes (L_8M5, L_8M6, E_8M5, E_8M6, W_8M5, W_8M6) so the
        derived value columns stay layer-agnostic. The output row's LAYER column
        still records which layer each value belongs to.

        Examples:
      L_8M5_SIARC_DEP   → SIARC_DEP
      L_8M6_CHM_DEP     → CHM_DEP
      E_8M5_HM_ETCH     → HM_ETCH
      E_8M6_HM_ETCH     → HM_ETCH
      W_8M5_HM_CLN      → HM_CLN
      W_8M6_HM_CLN      → HM_CLN
    """
    if not operation:
        return operation
    
    # Strip layer prefixes: (L|E|W)_(8M5|8M6)_
    return re.sub(r'^(L|E|W)_(8M5|8M6)_', '', str(operation))


def _normalize_layer_agnostic_definition(definition_name: str) -> str:
    """
    Normalize definition name to be layer-agnostic.
    
    For Track B definitions like "EQUIP:BARC_TBF_LPCLEAN:L_8M6_SIARC_DEP",
    extract and normalize the operation suffix part (the part after the last colon).
    
    Process:
      1. Split on ':' to get [TYPE, NAME, OPERATION_SUFFIX]
      2. Normalize operation suffix with _normalize_operation_suffix()
      3. Rejoin: TYPE:NAME:NORMALIZED_OPERATION
    
    Result: "EQUIP:BARC_TBF_LPCLEAN:L_8M6_SIARC_DEP" → "EQUIP:BARC_TBF_LPCLEAN:SIARC_DEP"
    
    For definitions without layer suffixes, returns unchanged since there's no layer
    identifier to strip.
    """
    if not definition_name or pd.isna(definition_name):
        return definition_name
    
    definition_name = str(definition_name)
    
    # Split on colon to get components
    parts = definition_name.split(':')
    if len(parts) < 3:
        # Format doesn't match expected TYPE:NAME:SUFFIX pattern, return as-is
        return definition_name
    
    # Last part might contain layer identifier
    last_part = parts[-1]
    normalized_last = _normalize_operation_suffix(last_part)
    
    # Reconstruct
    parts[-1] = normalized_last
    return ':'.join(parts)


STEP_TOKENS = sorted({_normalize_operation_suffix(alias) for alias in FULL_FLOW_ALIASES})


def _sanitize_col_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        token = "UNNAMED_DEFINITION"
    if token[0].isdigit():
        token = f"D_{token}"
    return token.upper()


def _definition_to_column_name(definition_name: str) -> str:
    """
        Convert DEFINITION_NAME to new column format.

        Track B step-suffixed definitions become STEP_BASE_NAME.
    
    Examples:
      DUV_OPC                              → DUV_OPC
    EQUIP:AMECT_GF:HM_ETCH               → HM_ETCH_EQUIP_AMECT_GF
      MX_HME_DUV                           → MX_HME_DUV
    """
    if not definition_name or pd.isna(definition_name):
        return "UNKNOWN"
    
    definition_name = str(definition_name).strip()
    # Track B step suffixes (layer-agnostic definitions)
    for step_token in STEP_TOKENS:
        if definition_name.endswith(":" + step_token):
            base_name = definition_name[: -(len(step_token) + 1)]
            base_name = _sanitize_col_token(base_name)
            return f"{step_token}_{base_name}"
    
    # Sanitize the base name
    base_name = _sanitize_col_token(definition_name)
    
    # Build final column name
    return base_name


def _unique_join(series: pd.Series) -> str | None:
    vals = []
    for v in series:
        if pd.isna(v):
            continue
        s = str(v)
        if s and s not in vals:
            vals.append(s)
    if not vals:
        return None
    return "|".join(vals)


def _build_bost_wide(bost_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict]:
    if bost_df.empty:
        return pd.DataFrame(columns=["LOT", "WAFER_ID", "LAYER"]), [], {"removed_count": 0, "removed_columns": []}

    if "SYNC_DEFINITION_NAME" in bost_df.columns:
        definition_source = "SYNC_DEFINITION_NAME"
    else:
        definition_source = "DEFINITION_NAME"

    needed = ["LOT", "WAFER", "LAYER", definition_source, "PROC_STRING_VALUE"]
    work = bost_df[needed].copy()
    work["DEFINITION_NAME"] = work[definition_source].astype(str)
    work["DEFINITION_NAME"] = work["DEFINITION_NAME"].map(_normalize_layer_agnostic_definition)

    work["VALUE_COL"] = work["DEFINITION_NAME"].map(_definition_to_column_name)

    wide_val = (
        work.pivot_table(
            index=["LOT", "WAFER", "LAYER"],
            columns="VALUE_COL",
            values="PROC_STRING_VALUE",
            aggfunc=_unique_join,
        )
        .reset_index()
    )

    wide = wide_val
    wide = wide.rename(columns={"WAFER": "WAFER_ID"})

    # Filter out columns that are 100% empty (completely null)
    removed_info = {'removed_count': 0, 'removed_columns': []}
    cols_to_check = [c for c in wide.columns if c not in ["LOT", "WAFER_ID", "LAYER"]]
    for col in cols_to_check:
        if wide[col].isna().sum() == len(wide):
            wide = wide.drop(columns=[col])
            removed_info['removed_columns'].append(col)
            removed_info['removed_count'] += 1

    discovered_value_cols = [c for c in wide.columns if c not in ["LOT", "WAFER_ID", "LAYER"]]
    value_cols = discovered_value_cols

    key_cols = ["LOT", "WAFER_ID", "LAYER"]
    wide = wide[key_cols + value_cols]
    return wide, value_cols, removed_info


def _join_and_metrics(input_df: pd.DataFrame, bost_wide_df: pd.DataFrame, gate_name: str) -> tuple[pd.DataFrame, dict]:
    input_work = input_df.copy()
    bost_work = bost_wide_df.copy()

    merged = input_work.merge(
        bost_work,
        how="left",
        on=["WAFER_ID", "LAYER"],
        suffixes=("", "_BOST"),
    )

    key_cols = ["LOT", "WAFER_ID", "LAYER"]
    input_keys = input_df[key_cols].drop_duplicates()
    
    # Get BOST value columns (those in bost_wide_df but not in key_cols)
    bost_value_cols = [c for c in bost_work.columns if c not in ["LOT", "WAFER_ID", "LAYER"]]
    
    if bost_value_cols:
        matched_key_df = (
            merged[key_cols + bost_value_cols]
            .groupby(key_cols, dropna=False)[bost_value_cols]
            .apply(lambda s: s.notna().any().any())
            .reset_index(name="matched")
        )
    else:
        matched_key_df = input_keys.copy()
        matched_key_df["matched"] = False

    metrics = {
        "gate": gate_name,
        "input_rows": int(len(input_df)),
        "input_unique_keys": int(len(input_keys)),
        "joined_rows": int(len(merged)),
        "matched_keys": int(matched_key_df["matched"].sum()),
        "unmatched_keys": int((~matched_key_df["matched"]).sum()),
        "match_rate": float(round(float(matched_key_df["matched"].mean()) if len(matched_key_df) else 0.0, 6)),
        "wide_columns": {
            "value_columns": int(len(bost_value_cols)),
            "alias_columns": 0,
        },
        "null_rates": {
            "all_value_columns": None,
        },
        "match_rate_by_layer": {},
    }

    if bost_value_cols:
        metrics["null_rates"]["all_value_columns"] = float(
            round(float(merged[bost_value_cols].isna().mean().mean()), 6)
        )

    by_layer = (
        matched_key_df.groupby("LAYER")["matched"]
        .mean()
        .sort_index()
        .to_dict()
    )
    metrics["match_rate_by_layer"] = {k: float(round(v, 6)) for k, v in by_layer.items()}

    unmatched = matched_key_df[~matched_key_df["matched"]]
    if len(unmatched):
        top_unmatched = (
            unmatched.groupby("LOT").size().sort_values(ascending=False).head(20).to_dict()
        )
    else:
        top_unmatched = {}
    metrics["top_unmatched_lots"] = {str(k): int(v) for k, v in top_unmatched.items()}

    return merged, metrics


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def main() -> None:
    t0 = time.time()
    root = _to_workspace_root()

    input_csv = root / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED_60DAY.csv"
    pilot_manifest_path = root / "BOST" / "adhoc_pilot_manifest_8M5CL_8M6CL.csv"
    pilot_enriched_path = root / "BOST" / "adhoc_bost_pilot_enriched_8M5CL_8M6CL.csv"
    pilot_summary_path = root / "artifacts" / "adhoc_bost_pilot_summary.json"
    dryrun_enriched_path = root / "BOST" / "adhoc_bost_enriched_dryrun_8M5CL_8M6CL.csv"
    dryrun_summary_path = root / "artifacts" / "adhoc_bost_dryrun_summary.json"
    final_enriched_path = root / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED_60DAY_BOST_ENRICHED.csv"
    final_summary_path = root / "artifacts" / "adhoc_bost_full_summary.json"

    _print_gate("Gate 0: Freeze inputs and runtime constants")
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    _print_gate("Gate 1: Schema and layer mapping validation")
    df_input = pd.read_csv(input_csv)
    _validate_required_columns(df_input)
    layers = _validate_layers(df_input)

    keys = _build_keys(df_input)
    print(f"Input rows={len(df_input)} unique_keys={len(keys)} layers={layers}")
    if len(FULL_FLOW_ALIASES) != 10:
        raise ValueError("Alias scope is not 10 entries as expected.")

    _print_gate("Gate 2: Build pilot manifest")
    pilot_keys = _build_pilot_manifest(keys, seed=SEED)
    pilot_keys.to_csv(pilot_manifest_path, index=False)
    print(
        "Pilot keys="
        f"{len(pilot_keys)} split="
        f"{pilot_keys['LAYER'].value_counts().sort_index().to_dict()}"
    )

    _print_gate("Gate 3: Pilot BOST query (treatment rules only)")
    conn = PyUber.connect(DSN)
    try:
        pilot_bost = _run_bost_query_treatment_rules(conn, pilot_keys)
    finally:
        conn.close()

    if pilot_bost.empty:
        raise RuntimeError("Pilot BOST query returned no rows.")

    pilot_layers = sorted(pilot_bost["LAYER"].dropna().astype(str).unique().tolist())
    print(f"Pilot BOST rows={len(pilot_bost)} mapped_layers={pilot_layers}")
    for expected in sorted(ALLOWED_LAYERS):
        if expected not in pilot_layers:
            raise RuntimeError(f"Pilot coverage missing expected layer in trigger mapping: {expected}")

    pilot_wide, pilot_value_cols, pilot_removed = _build_bost_wide(pilot_bost)
    print(
        "Pilot wide columns="
        f"value:{len(pilot_value_cols)} alias:0 "
        f"filtered:{pilot_removed['removed_count']}"
    )

    _print_gate("Gate 4: Pilot join-back and validation metrics")
    pilot_input_rows = df_input.merge(
        pilot_keys,
        on=["LOT", "WAFER_ID", "LAYER"],
        how="inner",
    )
    pilot_joined, pilot_metrics = _join_and_metrics(pilot_input_rows, pilot_wide, "pilot")
    pilot_joined.to_csv(pilot_enriched_path, index=False)
    _write_json(
        pilot_summary_path,
        {
            "created_at": _now(),
            "seed": SEED,
            "dsn": DSN,
            "process": PROCESS,
            "fab": FAB,
            "alias_scope": FULL_FLOW_ALIASES,
            "metrics": pilot_metrics,
        },
    )
    print("Pilot metrics:")
    print(json.dumps(pilot_metrics, indent=2))

    _print_gate("Gate 5: Full-scale dry run (treatment rules only)")
    conn = PyUber.connect(DSN)
    try:
        full_bost = _run_bost_query_treatment_rules(conn, keys)
    finally:
        conn.close()

    if full_bost.empty:
        raise RuntimeError("Full dry run returned no BOST rows.")

    full_wide, full_value_cols, full_removed = _build_bost_wide(full_bost)
    print(
        "Full wide columns="
        f"value:{len(full_value_cols)} alias:0 "
        f"filtered:{full_removed['removed_count']}"
    )

    full_joined, dryrun_metrics = _join_and_metrics(df_input, full_wide, "dryrun")
    full_joined.to_csv(dryrun_enriched_path, index=False)
    _write_json(
        dryrun_summary_path,
        {
            "created_at": _now(),
            "seed": SEED,
            "dsn": DSN,
            "process": PROCESS,
            "fab": FAB,
            "alias_scope": FULL_FLOW_ALIASES,
            "metrics": dryrun_metrics,
        },
    )

    _print_gate("Gate 6: Publish final outputs")
    
    full_joined["BOST_QUERY_DATE"] = datetime.now().strftime("%Y-%m-%d")
    full_joined["BOST_DSN"] = DSN
    full_joined["BOST_ALIAS_SCOPE"] = ";".join(FULL_FLOW_ALIASES)
    
    # Remove any remaining completely empty columns (100% null/None/NA/"None")
    # This catches both columns that were never populated and those that became empty after merge
    key_cols_final = ["LOT", "WAFER_ID", "LAYER"]
    
    cols_to_remove = []
    for col in full_joined.columns:
        if col not in key_cols_final:
            # A column is considered empty if all its non-null values are just the string 'None', or all values are NaN
            is_empty = True
            for val in full_joined[col]:
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    continue  # Skip null values
                elif isinstance(val, str):
                    if val.strip() and val.strip() != 'None':
                        is_empty = False
                        break
                else:
                    is_empty = False
                    break
            
            if is_empty:
                cols_to_remove.append(col)
    
    if cols_to_remove:
        print(f"[INFO] Removing {len(cols_to_remove)} completely empty columns from final output:")
        for col in sorted(cols_to_remove):
            has_p2 = "_P2" in col if isinstance(col, str) else False
            marker = " [DISCOVERED EMPTY VARIANT]" if has_p2 else ""
            print(f"  - {col}{marker}")
        full_joined = full_joined.drop(columns=cols_to_remove)
    
    full_joined.to_csv(final_enriched_path, index=False)

    _write_json(
        final_summary_path,
        {
            "created_at": _now(),
            "runtime_seconds": round(time.time() - t0, 3),
            "seed": SEED,
            "dsn": DSN,
            "process": PROCESS,
            "fab": FAB,
            "alias_scope": FULL_FLOW_ALIASES,
            "pilot_metrics": pilot_metrics,
            "dryrun_metrics": dryrun_metrics,
            "paths": {
                "input_csv": str(input_csv),
                "pilot_manifest": str(pilot_manifest_path),
                "pilot_enriched": str(pilot_enriched_path),
                "pilot_summary": str(pilot_summary_path),
                "dryrun_enriched": str(dryrun_enriched_path),
                "dryrun_summary": str(dryrun_summary_path),
                "final_enriched": str(final_enriched_path),
                "final_summary": str(final_summary_path),
            },
        },
    )

    print("\nRun complete.")
    print(f"Final enriched output: {final_enriched_path}")
    print(f"Final summary: {final_summary_path}")


if __name__ == "__main__":
    main()
