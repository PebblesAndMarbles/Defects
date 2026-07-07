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

EXPECTED_VALUE_COLUMNS = [
    "DUV_OPC_VALUE",
    "EQUIP_AMECT_CKV_CCM_SRCIP_DE_AMECT_VALUE",
    "EQUIP_AMECT_GF_DE_AMECT_VALUE",
    "EQUIP_AMECT_LIDS_DE_AMECT_VALUE",
    "EQUIP_AMECT_LINERS_DE_AMECT_VALUE",
    "EQUIP_AMECT_TEFLON_SHIM_DE_AMECT_VALUE",
    "EQUIP_BARC_TBF_CIPAMC_8102_1100_LI_TBEBC_VALUE",
    "EQUIP_BARC_TBF_CIPAMC_9110D_1000_LI_TBEBC_VALUE",
    "EQUIP_BARC_TBF_CIPAMC_9825_280_LI_TBEBC_VALUE",
    "EQUIP_BARC_TBF_LPCLEAN_LI_TBEBC_VALUE",
    "EQUIP_HRVA3_LEOCB_WE_LEOCB_VALUE",
    "EQUIP_HRVA_LEOCB_1278_WE_LEOCB_VALUE",
    "EQUIP_KOH_TNPPFREE_DRUM_WE_LEOCB_VALUE",
    "EQUIP_LEOCB_TNPP_FREE_NH4OH_WE_LEOCB_VALUE",
    "EQUIP_LEOCB_TRC_NDTD_ER_PILOT_WE_LEOCB_VALUE",
    "EQUIP_N58_XPR5_LI_SNYLI_VALUE",
    "EQUIP_PROZ_HW_UPGRADE_LI_TBEBC_VALUE",
    "EQUIP_R3HRVA_LEOCB_1278_WE_LEOCB_VALUE",
    "EQUIP_TNPPFREEKOH_WE_LEOCB_WE_LEOCB_WE_LEOCB_WE_LEOCB_WE_LEOCB_WE_LEOCB_VALUE",
    "EQUIP_TRC_PALL_STPS1_AND_HYBRID_CONFGURATION_FILTERS_PILOT_WW0626_WE_LEOCB_VALUE",
    "MX_HME_DUV_VALUE",
    "MX_HM_CLN_VALUE",
    "PROCESS_80P_ROADRUNNER_DE_AMECT_VALUE",
    "PROCESS_80P_ROADRUNNER_W78_DE_AMECT_VALUE",
    "PROCESS_DELTRIM_WE_LEOCB_VALUE",
    "PROCESS_DE_AMECT_VALUE",
]

CD_ALIASES = ["L_8M5_DCCD", "L_8M6_DCCD"]

BOST_SQL_TEMPLATE = """
SELECT
   w.LOT
  ,w.WAFER
  ,f.PROCESS_FAMILY
  ,f.TRIGGER_OPERATION
  ,d.DEFINITION_NAME
  ,d.USAGE
  ,d.VERSION
  ,d.IS_LATEST
  ,d.IS_ACTIVE
  ,d.LAST_MODIFY_USER
  ,v.PROC_STRING_VALUE
FROM B_META_WAFER_FAB w
INNER JOIN B_WAFER_PROCESS_DEFN v
  ON  v.WAFER_KEY = w.WAFER_KEY
INNER JOIN B_CFG_PROCESS_DEFN_FAMILY f
  ON  f.PROCESS_FAMILY_ID = v.PROCESS_FAMILY_ID
INNER JOIN B_CFG_PROCESS_DEFN d
  ON  d.DEFINITION_ID = f.DEFINITION_ID
  AND d.PROCESS = '{process}'
  AND d.FAB IN ('{fab}')
  AND d.IS_LATEST = '{is_latest}'
  AND d.IS_ACTIVE = '{is_active}'
WHERE {lots_filter}
  AND {wafers_filter}
  AND (
  {trigger_filter}
  )
ORDER BY w.LOT, w.WAFER, f.PROCESS_FAMILY
"""


def _to_workspace_root() -> Path:
    # Script is in BOST/, root is parent.
    return Path(__file__).resolve().parents[1]


def _chunked_in_clause(col: str, values: list[str], chunk_size: int = 999) -> str:
    chunks = [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]
    parts = []
    for chunk in chunks:
        escaped = [str(v).replace("'", "''") for v in chunk]
        in_values = ", ".join("'" + v + "'" for v in escaped)
        parts.append(f"{col} IN ({in_values})")
    return "(" + "\n  OR ".join(parts) + ")"


def _build_trigger_filter(aliases: list[str], numeric_ops: list[str]) -> str:
    terms = [f"INSTR(f.TRIGGER_OPERATION, '{a}') > 0" for a in aliases]
    terms.extend(f"INSTR(f.TRIGGER_OPERATION, '{op}') > 0" for op in numeric_ops)
    return "\n  OR ".join(terms)


def _trig_to_defect_layer(trigger_operation: str) -> str | None:
    m = re.search(r"8M(\d+)", str(trigger_operation))
    if not m:
        return None
    return f"8M{int(m.group(1))}CL"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _print_gate(msg: str) -> None:
    print(f"\n[{_now()}] {msg}")


def _validate_required_columns(df: pd.DataFrame) -> None:
    required = {"LOT", "WAFER_ID", "LAYER"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


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


def _fetch_numeric_ops(conn) -> list[str]:
    aliases_sql = ", ".join(f"'{a}'" for a in CD_ALIASES)
    sql = f"""
SELECT a.OPERATION
FROM   F_OPERATION_ALIAS a
WHERE  UPPER(a.OPER_GROUP_NAME) IN ({aliases_sql})
"""
    df_ops = pd.read_sql(sql, conn)
    if df_ops.empty:
        return []
    return sorted(df_ops["OPERATION"].dropna().astype(str).unique().tolist())


def _run_bost_query(conn, keys: pd.DataFrame) -> pd.DataFrame:
    lots = sorted(keys["LOT"].dropna().astype(str).unique().tolist())
    wafers = sorted(keys["WAFER_ID"].dropna().astype(str).unique().tolist())
    numeric_ops = _fetch_numeric_ops(conn)

    query = BOST_SQL_TEMPLATE.format(
        process=PROCESS,
        fab=FAB,
        is_latest=IS_LATEST,
        is_active=IS_ACTIVE,
        lots_filter=_chunked_in_clause("w.LOT", lots),
        wafers_filter=_chunked_in_clause("w.WAFER", wafers),
        trigger_filter=_build_trigger_filter(FULL_FLOW_ALIASES, numeric_ops),
    )

    df = pd.read_sql(query, conn)
    if df.empty:
        return df
    df.insert(2, "LAYER", df["TRIGGER_OPERATION"].map(_trig_to_defect_layer))
    return df


def _sanitize_col_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        token = "UNNAMED_DEFINITION"
    if token[0].isdigit():
        token = f"D_{token}"
    return token.upper()


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


def _definition_prefix_map(definitions: list[str]) -> dict[str, str]:
    used = set()
    out: dict[str, str] = {}
    for definition in sorted(definitions):
        base = _sanitize_col_token(definition)
        candidate = base
        i = 2
        while candidate in used:
            candidate = f"{base}_{i}"
            i += 1
        used.add(candidate)
        out[definition] = candidate
    return out


def _build_bost_wide(bost_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    if bost_df.empty:
        return pd.DataFrame(columns=["LOT", "WAFER_ID", "LAYER"]), {}, []

    needed = ["LOT", "WAFER", "LAYER", "DEFINITION_NAME", "PROC_STRING_VALUE"]
    work = bost_df[needed].copy()
    work["DEFINITION_NAME"] = work["DEFINITION_NAME"].astype(str)

    prefix_map = _definition_prefix_map(sorted(work["DEFINITION_NAME"].unique().tolist()))
    work["DEF_PREFIX"] = work["DEFINITION_NAME"].map(prefix_map)
    work["VALUE_COL"] = work["DEF_PREFIX"] + "_VALUE"

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

    for col in EXPECTED_VALUE_COLUMNS:
        if col not in wide.columns:
            wide[col] = None

    discovered_value_cols = [c for c in wide.columns if c.endswith("_VALUE")]
    ordered_value_cols = [c for c in EXPECTED_VALUE_COLUMNS if c in discovered_value_cols]
    extra_value_cols = sorted([c for c in discovered_value_cols if c not in EXPECTED_VALUE_COLUMNS])
    value_cols = ordered_value_cols + extra_value_cols

    key_cols = ["LOT", "WAFER_ID", "LAYER"]
    wide = wide[key_cols + value_cols]
    return wide, prefix_map, value_cols


def _join_and_metrics(input_df: pd.DataFrame, bost_wide_df: pd.DataFrame, gate_name: str) -> tuple[pd.DataFrame, dict]:
    merged = input_df.merge(
        bost_wide_df,
        how="left",
        on=["LOT", "WAFER_ID", "LAYER"],
    )

    key_cols = ["LOT", "WAFER_ID", "LAYER"]
    input_keys = input_df[key_cols].drop_duplicates()
    value_cols = [c for c in merged.columns if c.endswith("_VALUE")]
    if value_cols:
        matched_key_df = (
            merged[key_cols + value_cols]
            .groupby(key_cols, dropna=False)[value_cols]
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
            "value_columns": int(len([c for c in merged.columns if c.endswith("_VALUE")])),
            "alias_columns": 0,
        },
        "null_rates": {
            "all_value_columns": None,
        },
        "match_rate_by_layer": {},
    }

    value_cols = [c for c in merged.columns if c.endswith("_VALUE")]
    if value_cols:
        metrics["null_rates"]["all_value_columns"] = float(
            round(float(merged[value_cols].isna().mean().mean()), 6)
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


def _write_definition_map_csv(path: Path, prefix_map: dict[str, str]) -> None:
    rows = []
    for definition_name, prefix in sorted(prefix_map.items()):
        rows.append(
            {
                "DEFINITION_NAME": definition_name,
                "COLUMN_PREFIX": prefix,
                "VALUE_COLUMN": f"{prefix}_VALUE",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    t0 = time.time()
    root = _to_workspace_root()

    input_csv = root / "outputs" / "wafer" / "8M5CL_8M6CL_EXTENDED_60DAY.csv"
    pilot_manifest_path = root / "BOST" / "adhoc_pilot_manifest_8M5CL_8M6CL.csv"
    pilot_enriched_path = root / "BOST" / "adhoc_bost_pilot_enriched_8M5CL_8M6CL.csv"
    pilot_summary_path = root / "artifacts" / "adhoc_bost_pilot_summary.json"
    dryrun_enriched_path = root / "BOST" / "adhoc_bost_enriched_dryrun_8M5CL_8M6CL.csv"
    dryrun_summary_path = root / "artifacts" / "adhoc_bost_dryrun_summary.json"
    definition_map_path = root / "artifacts" / "adhoc_bost_definition_columns.csv"
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

    _print_gate("Gate 3: Pilot BOST query")
    conn = PyUber.connect(DSN)
    try:
        pilot_bost = _run_bost_query(conn, pilot_keys)
    finally:
        conn.close()

    if pilot_bost.empty:
        raise RuntimeError("Pilot BOST query returned no rows.")

    pilot_layers = sorted(pilot_bost["LAYER"].dropna().astype(str).unique().tolist())
    print(f"Pilot BOST rows={len(pilot_bost)} mapped_layers={pilot_layers}")
    for expected in sorted(ALLOWED_LAYERS):
        if expected not in pilot_layers:
            raise RuntimeError(f"Pilot coverage missing expected layer in trigger mapping: {expected}")

    pilot_wide, pilot_prefix_map, pilot_value_cols = _build_bost_wide(pilot_bost)
    print(
        "Pilot wide columns="
        f"value:{len(pilot_value_cols)} alias:0 "
        f"definitions:{len(pilot_prefix_map)}"
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
            "definition_prefix_map": pilot_prefix_map,
            "metrics": pilot_metrics,
        },
    )
    print("Pilot metrics:")
    print(json.dumps(pilot_metrics, indent=2))

    _print_gate("Gate 5: Full-scale dry run")
    conn = PyUber.connect(DSN)
    try:
        full_bost = _run_bost_query(conn, keys)
    finally:
        conn.close()

    if full_bost.empty:
        raise RuntimeError("Full dry run returned no BOST rows.")

    full_wide, full_prefix_map, full_value_cols = _build_bost_wide(full_bost)
    print(
        "Full wide columns="
        f"value:{len(full_value_cols)} alias:0 "
        f"definitions:{len(full_prefix_map)}"
    )

    full_joined, dryrun_metrics = _join_and_metrics(df_input, full_wide, "dryrun")
    full_joined.to_csv(dryrun_enriched_path, index=False)
    _write_definition_map_csv(definition_map_path, full_prefix_map)
    _write_json(
        dryrun_summary_path,
        {
            "created_at": _now(),
            "seed": SEED,
            "dsn": DSN,
            "process": PROCESS,
            "fab": FAB,
            "alias_scope": FULL_FLOW_ALIASES,
            "definition_prefix_map": full_prefix_map,
            "metrics": dryrun_metrics,
        },
    )

    _print_gate("Gate 6: Publish final outputs")
    full_joined["BOST_QUERY_DATE"] = datetime.now().strftime("%Y-%m-%d")
    full_joined["BOST_DSN"] = DSN
    full_joined["BOST_ALIAS_SCOPE"] = ";".join(FULL_FLOW_ALIASES)
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
            "definition_prefix_map": full_prefix_map,
            "pilot_metrics": pilot_metrics,
            "dryrun_metrics": dryrun_metrics,
            "paths": {
                "input_csv": str(input_csv),
                "pilot_manifest": str(pilot_manifest_path),
                "pilot_enriched": str(pilot_enriched_path),
                "pilot_summary": str(pilot_summary_path),
                "dryrun_enriched": str(dryrun_enriched_path),
                "dryrun_summary": str(dryrun_summary_path),
                "definition_map": str(definition_map_path),
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
