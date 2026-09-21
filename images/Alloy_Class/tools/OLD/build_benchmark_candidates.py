from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


SOURCE_ORDER = {
    "factory_beep": 0,
    "non_beep_control": 1,
    "ambiguous": 2,
    "other": 3,
}

POOL_COLORS = {
    "factory_beep": "#3a84d8",
    "non_beep_control": "#2c9f62",
    "ambiguous": "#c9912a",
    "other": "#6d7680",
}


@dataclass
class RunStats:
    rows_manifest_total: int = 0
    rows_manifest_recent: int = 0
    rows_manifest_after_inventory_filter: int = 0
    rows_missing_local_path: int = 0
    rows_dropped_unknown_subentity: int = 0
    rows_pairs_total: int = 0
    rows_pairs_complete: int = 0
    rows_pairs_unpaired: int = 0
    rows_written: int = 0
    fallback_join_rows: int = 0
    fallback_join_groups: int = 0
    fallback_join_rate: float = 0.0
    factory_beep_share: float = 0.0
    factory_beep_below_target: bool = False


def normalize_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_filename_parts(path_text: str) -> tuple[str, str, str, str]:
    name = os.path.basename(path_text)
    stem = os.path.splitext(name)[0]
    parts = stem.split("_")
    lot7 = parts[2].strip() if len(parts) >= 3 else ""
    recipe = parts[4].strip().upper() if len(parts) >= 5 else ""
    image_suffix = parts[-1].strip() if parts else ""
    return name, lot7, recipe, image_suffix


def infer_subentity(path_text: str) -> str:
    parent = os.path.basename(os.path.dirname(path_text))
    value = parent.strip()
    if value.lower() in {"nan", "none", "null", "unknown"}:
        return ""
    return value


def to_iso_week_batch(inspection_max: pd.Timestamp, lookback_days: int) -> str:
    year, week, _ = inspection_max.isocalendar()
    yyww = f"{year % 100:02d}{week:02d}"
    return f"{lookback_days}day_{yyww}"


def source_pool_for_row(row: pd.Series) -> str:
    class_label = str(row.get("CLASS", "")).strip().upper()
    finebin = str(row.get("FINEBIN", "")).strip().upper()

    if class_label == "BEEP":
        if finebin == "LOWCONF":
            return "ambiguous"
        return "factory_beep"
    if class_label == "SMALL_PARTICLE":
        return "non_beep_control"
    if not class_label:
        return "other"
    return "other"


def pair_sort_tuple(record: dict[str, Any]) -> tuple[int, pd.Timestamp, str, str]:
    source_rank = SOURCE_ORDER.get(record.get("source_pool", "other"), 3)
    ts = record.get("inspection_time_parsed")
    if not isinstance(ts, pd.Timestamp):
        ts = pd.Timestamp.min
    chamber = str(record.get("chamber", ""))
    defect = str(record.get("defect_id", ""))
    return source_rank, -int(ts.value), chamber, defect


def csv_header_from_template(template_csv: Path) -> list[str]:
    template_df = pd.read_csv(template_csv, nrows=1)
    return list(template_df.columns)


def load_manifest(manifest_csv: Path, lookback_days: int, stats: RunStats) -> pd.DataFrame:
    mdf = pd.read_csv(manifest_csv, dtype=str)
    stats.rows_manifest_total = len(mdf)

    mdf["INSPECTION_TIME_PARSED"] = pd.to_datetime(mdf.get("INSPECTION_TIME"), errors="coerce")
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    mdf = mdf[mdf["INSPECTION_TIME_PARSED"] >= cutoff].copy()
    stats.rows_manifest_recent = len(mdf)

    inv = pd.to_numeric(mdf.get("INVENTORY_ONLY"), errors="coerce").fillna(0)
    mdf = mdf[inv != 1].copy()
    stats.rows_manifest_after_inventory_filter = len(mdf)

    mdf["LOCAL_IMAGE_FILE"] = mdf.get("LOCAL_IMAGE_FILE", "").fillna("").astype(str).str.strip()
    mdf.loc[mdf["LOCAL_IMAGE_FILE"].str.lower().isin({"nan", "none", "null"}), "LOCAL_IMAGE_FILE"] = ""
    stats.rows_missing_local_path = int((mdf["LOCAL_IMAGE_FILE"] == "").sum())
    mdf = mdf[mdf["LOCAL_IMAGE_FILE"] != ""].copy()

    mdf["SUBENTITY_INFERRED"] = mdf["LOCAL_IMAGE_FILE"].map(infer_subentity)
    mdf["IMAGE_NAME"], mdf["LOT7_INFERRED"], mdf["RECIPE_INFERRED"], mdf["IMAGE_SUFFIX"] = zip(
        *mdf["LOCAL_IMAGE_FILE"].map(parse_filename_parts)
    )

    bad_subentity = (
        mdf["SUBENTITY_INFERRED"]
        .fillna("")
        .str.strip()
        .str.lower()
        .isin({"", "unknown", "nan", "none", "null"})
    )
    stats.rows_dropped_unknown_subentity = int(bad_subentity.sum())
    mdf = mdf[~bad_subentity].copy()

    mdf["WAFER_KEY_N"] = mdf.get("WAFER_KEY", "").map(normalize_key)
    mdf["DEFECT_ID_N"] = mdf.get("DEFECT_ID", "").map(normalize_key)
    mdf["INSPECTION_TIME_N"] = mdf["INSPECTION_TIME_PARSED"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    mdf["IMAGE_ID_N"] = mdf.get("IMAGE_ID", "").map(normalize_key)

    mdf["source_pool"] = mdf.apply(source_pool_for_row, axis=1)
    return mdf


def load_coords(coords_csv: Path) -> pd.DataFrame:
    cols_needed = [
        "WAFER_KEY",
        "INSPECTION_TIME",
        "DEFECT_ID",
        "SUBENTITY",
        "LOT7",
        "ACTUAL_LOT",
        "WAFER_X_MM",
        "WAFER_Y_MM",
        "LAYER",
        "INSPECT_TOOL",
        "CLASS",
        "FINEBIN",
    ]
    cdf = pd.read_csv(coords_csv, usecols=lambda c: c in cols_needed, dtype=str)
    cdf["WAFER_KEY_N"] = cdf.get("WAFER_KEY", "").map(normalize_key)
    cdf["DEFECT_ID_N"] = cdf.get("DEFECT_ID", "").map(normalize_key)
    cdf["INSPECTION_TIME_PARSED"] = pd.to_datetime(cdf.get("INSPECTION_TIME"), errors="coerce")
    cdf["INSPECTION_TIME_N"] = cdf["INSPECTION_TIME_PARSED"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    cdf["SUBENTITY_N"] = cdf.get("SUBENTITY", "").fillna("").astype(str).str.strip()
    cdf["LOT7_N"] = cdf.get("LOT7", "").fillna("").astype(str).str.strip()
    return cdf


def _first_non_empty(values: pd.Series) -> str:
    for value in values:
        text = "" if pd.isna(value) else str(value).strip()
        if text and text.lower() not in {"nan", "none", "null"}:
            return text
    return ""


def enrich_pairs(
    pair_df: pd.DataFrame,
    coords_df: pd.DataFrame,
    stats: RunStats,
) -> pd.DataFrame:
    primary_map: dict[tuple[str, str, str], dict[str, str]] = {}
    for _, row in coords_df.iterrows():
        key = (row.get("WAFER_KEY_N", ""), row.get("INSPECTION_TIME_N", ""), row.get("DEFECT_ID_N", ""))
        if key in primary_map:
            continue
        primary_map[key] = {
            "INSPECT_TOOL": str(row.get("INSPECT_TOOL", "") or ""),
            "ACTUAL_LOT": str(row.get("ACTUAL_LOT", "") or ""),
            "LAYER": str(row.get("LAYER", "") or ""),
            "WAFER_X_MM": str(row.get("WAFER_X_MM", "") or ""),
            "WAFER_Y_MM": str(row.get("WAFER_Y_MM", "") or ""),
            "COORDS_CLASS": str(row.get("CLASS", "") or ""),
            "COORDS_FINEBIN": str(row.get("FINEBIN", "") or ""),
        }

    fallback_map: dict[tuple[str, str], dict[str, str]] = {}
    fallback_groups: set[tuple[str, str]] = set()
    for _, row in coords_df.iterrows():
        fkey = (str(row.get("SUBENTITY_N", "") or ""), str(row.get("LOT7_N", "") or ""))
        if fkey in fallback_map:
            continue
        fallback_map[fkey] = {
            "INSPECT_TOOL": str(row.get("INSPECT_TOOL", "") or ""),
            "ACTUAL_LOT": str(row.get("ACTUAL_LOT", "") or ""),
            "LAYER": str(row.get("LAYER", "") or ""),
            "WAFER_X_MM": str(row.get("WAFER_X_MM", "") or ""),
            "WAFER_Y_MM": str(row.get("WAFER_Y_MM", "") or ""),
            "COORDS_CLASS": str(row.get("CLASS", "") or ""),
            "COORDS_FINEBIN": str(row.get("FINEBIN", "") or ""),
        }

    enrich_rows: list[dict[str, str]] = []
    for _, row in pair_df.iterrows():
        key = (row["wafer_key_n"], row["inspection_time_n"], row["defect_id_n"])
        mapped = primary_map.get(key)
        if mapped is None:
            fkey = (str(row.get("chamber", "")), str(row.get("lot7_inferred", "")))
            mapped = fallback_map.get(fkey)
            if mapped is not None:
                stats.fallback_join_rows += 1
                fallback_groups.add(fkey)
        if mapped is None:
            mapped = {
                "INSPECT_TOOL": "",
                "ACTUAL_LOT": "",
                "LAYER": "",
                "WAFER_X_MM": "",
                "WAFER_Y_MM": "",
                "COORDS_CLASS": "",
                "COORDS_FINEBIN": "",
            }
        enrich_rows.append(mapped)

    stats.fallback_join_groups = len(fallback_groups)
    if len(pair_df) > 0:
        stats.fallback_join_rate = stats.fallback_join_rows / len(pair_df)

    out_df = pair_df.copy()
    enrich_df = pd.DataFrame(enrich_rows)
    for col in enrich_df.columns:
        out_df[col] = enrich_df[col]
    return out_df


def build_pairs(mdf: pd.DataFrame, stats: RunStats) -> pd.DataFrame:
    key_cols = ["WAFER_KEY_N", "INSPECTION_TIME_N", "DEFECT_ID_N"]
    pairs: list[dict[str, Any]] = []
    unpaired = 0

    grouped = mdf.groupby(key_cols, dropna=False)
    stats.rows_pairs_total = grouped.ngroups

    for _, group in grouped:
        image2 = group[group["IMAGE_ID_N"] == "2"]
        image3 = group[group["IMAGE_ID_N"] == "3"]

        if image2.empty or image3.empty:
            unpaired += 1
            continue

        bright_row = image2.iloc[0]
        dark_row = image3.iloc[0]
        bright_path = str(bright_row["LOCAL_IMAGE_FILE"]).strip()
        dark_path = str(dark_row["LOCAL_IMAGE_FILE"]).strip()

        if not os.path.exists(bright_path) or not os.path.exists(dark_path):
            unpaired += 1
            continue

        inspection_time_parsed = pd.to_datetime(bright_row["INSPECTION_TIME_PARSED"], errors="coerce")
        inspection_time_txt = (
            inspection_time_parsed.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(inspection_time_parsed) else ""
        )
        pair_key = (
            f"{normalize_key(bright_row.get('WAFER_KEY', ''))}_"
            f"{inspection_time_txt.replace('-', '').replace(':', '').replace(' ', '_')}_"
            f"{normalize_key(bright_row.get('DEFECT_ID', ''))}"
        )

        class_label = _first_non_empty(group.get("CLASS", pd.Series(dtype=str)))
        finebin = _first_non_empty(group.get("FINEBIN", pd.Series(dtype=str)))
        source_pool = source_pool_for_row(pd.Series({"CLASS": class_label, "FINEBIN": finebin}))

        pairs.append(
            {
                "wafer_key": normalize_key(bright_row.get("WAFER_KEY", "")),
                "wafer_key_n": normalize_key(bright_row.get("WAFER_KEY", "")),
                "inspection_time": inspection_time_txt,
                "inspection_time_n": inspection_time_txt,
                "inspection_time_parsed": inspection_time_parsed,
                "defect_id": normalize_key(bright_row.get("DEFECT_ID", "")),
                "defect_id_n": normalize_key(bright_row.get("DEFECT_ID", "")),
                "pair_key": pair_key,
                "bright_image_name": os.path.basename(bright_path),
                "dark_image_name": os.path.basename(dark_path),
                "bright_image_path": bright_path,
                "dark_image_path": dark_path,
                "query_site": _first_non_empty(group.get("SITE", pd.Series(dtype=str))),
                "tool_name": _first_non_empty(group.get("INSPECT_TOOL", pd.Series(dtype=str))),
                "chamber": _first_non_empty(group.get("SUBENTITY_INFERRED", pd.Series(dtype=str))),
                "factory_class_label": class_label,
                "manual_optical_class": _first_non_empty(
                    group.get("MANUAL_OPTICAL_CLASS", pd.Series(dtype=str))
                ),
                "source_pool": source_pool,
                "lot7_inferred": _first_non_empty(group.get("LOT7_INFERRED", pd.Series(dtype=str))),
            }
        )

    stats.rows_pairs_unpaired = unpaired
    stats.rows_pairs_complete = len(pairs)

    return pd.DataFrame(pairs)


def blank_columns(record: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    output = {col: "" for col in columns}
    output.update(record)
    return output


def build_output_rows(pair_df: pd.DataFrame, header: list[str], lookback_days: int, stats: RunStats) -> list[dict[str, Any]]:
    if pair_df.empty:
        return []

    max_ts = pair_df["inspection_time_parsed"].dropna().max()
    if pd.isna(max_ts):
        max_ts = pd.Timestamp.now()
    selection_batch = to_iso_week_batch(max_ts, lookback_days)

    sorted_records = pair_df.to_dict(orient="records")
    sorted_records.sort(
        key=lambda rec: (
            -int(rec["inspection_time_parsed"].value) if isinstance(rec.get("inspection_time_parsed"), pd.Timestamp) else 0,
            str(rec.get("chamber", "")),
            str(rec.get("defect_id", "")),
        )
    )

    out_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for idx, rec in enumerate(sorted_records, start=1):
        # backfill factory_class_label from coords when manifest left it blank
        factory_class = str(rec.get("factory_class_label", "") or rec.get("COORDS_CLASS", "")).strip()
        coords_finebin = str(rec.get("COORDS_FINEBIN", "")).strip()
        # re-derive source_pool using the backfilled class
        manifest_class = str(rec.get("factory_class_label", "")).strip()
        if manifest_class:
            source_pool = str(rec.get("source_pool", "other"))
        else:
            source_pool = source_pool_for_row(pd.Series({"CLASS": factory_class, "FINEBIN": coords_finebin}))
        source_counts[source_pool] += 1
        row = {
            "benchmark_id": f"BMK_{idx:04d}",
            "split": "",
            "source_pool": source_pool,
            "selection_batch": selection_batch,
            "wafer_key": rec.get("wafer_key", ""),
            "inspection_time": rec.get("inspection_time", ""),
            "defect_id": rec.get("defect_id", ""),
            "pair_key": rec.get("pair_key", ""),
            "bright_image_name": rec.get("bright_image_name", ""),
            "dark_image_name": rec.get("dark_image_name", ""),
            "bright_image_path": rec.get("bright_image_path", ""),
            "dark_image_path": rec.get("dark_image_path", ""),
            "query_site": rec.get("query_site", ""),
            "tool_name": rec.get("INSPECT_TOOL", "") or rec.get("tool_name", ""),
            "chamber": rec.get("chamber", ""),
            "factory_class_label": factory_class,
            "manual_optical_class": rec.get("manual_optical_class", ""),
        }
        out_rows.append(blank_columns(row, header))

    stats.rows_written = len(out_rows)
    factory_count = source_counts.get("factory_beep", 0)
    stats.factory_beep_share = (factory_count / len(out_rows)) if out_rows else 0.0
    stats.factory_beep_below_target = stats.factory_beep_share < 0.30
    return out_rows


def build_summary(rows: list[dict[str, Any]], stats: RunStats, class_counts: dict[str, int]) -> dict[str, Any]:
    pool_counts = Counter(row.get("source_pool", "other") for row in rows)
    chamber_counts = Counter(row.get("chamber", "") for row in rows)
    matrix: dict[str, dict[str, int]] = {}
    for row in rows:
        pool = row.get("source_pool", "other")
        chamber = row.get("chamber", "")
        matrix.setdefault(pool, {})
        matrix[pool][chamber] = matrix[pool].get(chamber, 0) + 1

    return {
        "stats": {
            "rows_manifest_total": stats.rows_manifest_total,
            "rows_manifest_recent": stats.rows_manifest_recent,
            "rows_manifest_after_inventory_filter": stats.rows_manifest_after_inventory_filter,
            "rows_missing_local_path": stats.rows_missing_local_path,
            "rows_dropped_unknown_subentity": stats.rows_dropped_unknown_subentity,
            "rows_pairs_total": stats.rows_pairs_total,
            "rows_pairs_complete": stats.rows_pairs_complete,
            "rows_pairs_unpaired": stats.rows_pairs_unpaired,
            "rows_written": stats.rows_written,
            "fallback_join_rows": stats.fallback_join_rows,
            "fallback_join_groups": stats.fallback_join_groups,
            "fallback_join_rate": round(stats.fallback_join_rate, 4),
            "factory_beep_share": round(stats.factory_beep_share, 4),
            "factory_beep_below_target": stats.factory_beep_below_target,
        },
        "class_value_counts": class_counts,
        "source_pool_counts": dict(pool_counts),
        "chamber_counts": dict(chamber_counts),
        "pool_by_chamber": matrix,
    }


def render_html(rows: list[dict[str, Any]], summary: dict[str, Any], output_html: Path, lookback_days: int) -> None:
    run_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    pool_counts = summary.get("source_pool_counts", {})

    cards: list[str] = []
    for row in rows:
        pool = str(row.get("source_pool", "other"))
        color = POOL_COLORS.get(pool, POOL_COLORS["other"])
        bright_path = str(row.get("bright_image_path", ""))
        dark_path = str(row.get("dark_image_path", ""))
        cards.append(
            "<section class='card'>"
            "<div class='card-head'>"
            f"<div class='meta'>{html.escape(str(row.get('benchmark_id', '')))}</div>"
            f"<div class='meta'>{html.escape(str(row.get('chamber', '')))}</div>"
            f"<div class='meta'>Defect {html.escape(str(row.get('defect_id', '')))}</div>"
            f"<div class='meta'>{html.escape(str(row.get('factory_class_label', '')))}</div>"
            f"<div class='meta'>{html.escape(str(row.get('inspection_time', '')))}</div>"
            f"<div class='pill' style='background:{color};'>{html.escape(pool)}</div>"
            "</div>"
            "<div class='pair'>"
            "<div class='imgbox'>"
            "<div class='title'>BF (image_id=2)</div>"
            f"<a href='{html.escape(bright_path)}' target='_blank' rel='noopener'>"
            f"<img src='{html.escape(bright_path)}' alt='BF image'>"
            "</a>"
            f"<div class='caption'>{html.escape(str(row.get('bright_image_name', '')))}</div>"
            "</div>"
            "<div class='imgbox'>"
            "<div class='title'>DF (image_id=3)</div>"
            f"<a href='{html.escape(dark_path)}' target='_blank' rel='noopener'>"
            f"<img src='{html.escape(dark_path)}' alt='DF image'>"
            "</a>"
            f"<div class='caption'>{html.escape(str(row.get('dark_image_name', '')))}</div>"
            "</div>"
            "</div>"
            "</section>"
        )

    chambers = sorted(summary.get("chamber_counts", {}).keys())
    pools = ["factory_beep", "non_beep_control", "ambiguous", "other"]
    table_head = "".join(f"<th>{html.escape(ch)}</th>" for ch in chambers)
    matrix = summary.get("pool_by_chamber", {})
    table_rows = []
    for pool in pools:
        cells = []
        for chamber in chambers:
            val = matrix.get(pool, {}).get(chamber, 0)
            cells.append(f"<td>{val}</td>")
        table_rows.append(f"<tr><th>{pool}</th>{''.join(cells)}</tr>")

    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Benchmark Candidates Review ({lookback_days}-Day)</title>
  <style>
    body {{ margin: 0; background: #0f151c; color: #e6edf3; font-family: Segoe UI, Arial, sans-serif; }}
    .sticky {{ background: #13202b; border-bottom: 1px solid #25384a; padding: 14px 18px; }}
    .h1 {{ font-size: 20px; font-weight: 700; margin: 0 0 8px 0; }}
    .sub {{ font-size: 12px; color: #9fb2c5; }}
    .stats {{ display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }}
    .stat {{ background: #1a2632; border: 1px solid #2a3a4b; border-radius: 999px; padding: 6px 10px; font-size: 12px; }}
    .main {{ padding: 16px; }}
    .summary {{ background: #121a23; border: 1px solid #283544; border-radius: 10px; padding: 12px; margin-bottom: 14px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 700px; }}
    th, td {{ border: 1px solid #2a3a4b; padding: 6px 8px; text-align: center; font-size: 12px; }}
    th {{ background: #1a2632; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(540px, 1fr)); gap: 12px; }}
    .card {{ background: #121a23; border: 1px solid #283544; border-radius: 12px; padding: 12px; }}
    .card-head {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }}
    .meta {{ background: #1a2632; border: 1px solid #2a3a4b; border-radius: 8px; padding: 4px 8px; font-size: 12px; }}
    .pill {{ border-radius: 999px; padding: 5px 10px; color: #fff; font-size: 12px; font-weight: 700; }}
    .pair {{ display: grid; grid-template-columns: repeat(2, minmax(0, max-content)); gap: 10px; justify-content: start; align-items: start; }}
    .imgbox {{ background: #0d131a; border: 1px solid #263646; border-radius: 8px; padding: 8px; width: fit-content; max-width: 100%; }}
    .title {{ font-size: 12px; color: #9fb2c5; margin-bottom: 6px; }}
    img {{ width: 240px; max-width: min(240px, 100%); max-height: 240px; object-fit: contain; border: 1px solid #314557; background: #000; display: block; }}
    .caption {{ margin-top: 6px; font-size: 11px; color: #9fb2c5; word-break: break-all; }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .pair {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class=\"sticky\">
    <h1 class=\"h1\">Benchmark Candidates - {lookback_days}-Day Pool</h1>
    <div class=\"sub\">{len(rows)} pairs · {run_date}</div>
    <div class=\"stats\">
      <div class=\"stat\">factory_beep: {pool_counts.get('factory_beep', 0)}</div>
      <div class=\"stat\">non_beep_control: {pool_counts.get('non_beep_control', 0)}</div>
      <div class=\"stat\">ambiguous: {pool_counts.get('ambiguous', 0)}</div>
      <div class=\"stat\">other: {pool_counts.get('other', 0)}</div>
    </div>
  </header>
  <main class=\"main\">
    <section class=\"summary\">
      <h2>source_pool x chamber</h2>
      <table>
        <thead>
          <tr><th>source_pool</th>{table_head}</tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </section>
    <section class=\"grid\">{''.join(cards)}</section>
  </main>
</body>
</html>
"""
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark candidates CSV and HTML review report")
    parser.add_argument(
        "--manifest-csv",
        default="outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv",
        help="Path to manifest CSV",
    )
    parser.add_argument(
        "--coords-csv",
        default="outputs/defects/DEFECT_COORDINATES_EXTENDED.csv",
        help="Path to coordinate enrichment CSV",
    )
    parser.add_argument(
        "--template-csv",
        default="images/Alloy_Class/artifacts/benchmark_slice_v1_template.csv",
        help="Path to template CSV defining output header",
    )
    parser.add_argument(
        "--out-csv",
        default="images/Alloy_Class/artifacts/benchmark_candidates_14day.csv",
        help="Path to candidate CSV output",
    )
    parser.add_argument(
        "--out-html",
        default="images/Alloy_Class/reporting/benchmark_review_14day.html",
        help="Path to review HTML output",
    )
    parser.add_argument(
        "--summary-json",
        default="images/Alloy_Class/artifacts/benchmark_candidates_14day_summary.json",
        help="Path to run summary JSON output",
    )
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--fallback-warn-threshold", type=float, default=0.20)
    args = parser.parse_args()

    manifest_csv = Path(args.manifest_csv)
    coords_csv = Path(args.coords_csv)
    template_csv = Path(args.template_csv)
    out_csv = Path(args.out_csv)
    out_html = Path(args.out_html)
    summary_json = Path(args.summary_json)

    # adjudication columns that must survive a regeneration
    ADJUDICATION_COLS = [
        "split", "adjudicated_by", "adjudicated_at_utc", "adjudication_status",
        "adjudicated_coarse_class", "adjudicated_blocked_etch_evidence",
        "adjudicated_confidence", "comparator_visible", "occlusion_present",
        "offset_surface_lines_present", "review_required_expected",
        "failure_mode_primary", "failure_mode_secondary", "notes_short",
    ]

    # load any previously adjudicated work keyed by stable pair_key
    prior_adjudication: dict[str, dict] = {}
    if out_csv.exists():
        prior_df = pd.read_csv(out_csv, dtype=str).fillna("")
        if "pair_key" in prior_df.columns:
            for _, row in prior_df.iterrows():
                pk = str(row.get("pair_key", "")).strip()
                if not pk:
                    continue
                work = {col: str(row.get(col, "")) for col in ADJUDICATION_COLS if col in prior_df.columns}
                if any(v.strip() for v in work.values()):
                    prior_adjudication[pk] = work
            print(f"preserved_adjudication_rows={len(prior_adjudication)}")

    stats = RunStats()
    mdf = load_manifest(manifest_csv, args.lookback_days, stats)
    class_counts_series = mdf.get("CLASS", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    class_counts = class_counts_series.value_counts(dropna=False).to_dict()

    pair_df = build_pairs(mdf, stats)
    coords_df = load_coords(coords_csv)
    pair_df = enrich_pairs(pair_df, coords_df, stats)

    header = csv_header_from_template(template_csv)
    rows = build_output_rows(pair_df, header, args.lookback_days, stats)

    # re-merge any prior adjudication work back in by pair_key
    restored = 0
    for row in rows:
        pk = str(row.get("pair_key", "")).strip()
        if pk in prior_adjudication:
            row.update(prior_adjudication[pk])
            restored += 1
    if prior_adjudication:
        print(f"restored_adjudication_rows={restored}")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=header).to_csv(out_csv, index=False)

    summary = build_summary(rows, stats, class_counts)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    render_html(rows, summary, out_html, args.lookback_days)

    print(f"wrote_csv={out_csv.resolve()}")
    print(f"wrote_html={out_html.resolve()}")
    print(f"wrote_summary={summary_json.resolve()}")
    print(f"rows_written={stats.rows_written}")
    print(f"fallback_join_rate={stats.fallback_join_rate:.4f}")
    print(f"factory_beep_share={stats.factory_beep_share:.4f}")
    if stats.fallback_join_rate > args.fallback_warn_threshold:
        print(
            f"warning=fallback_join_rate_above_threshold ({stats.fallback_join_rate:.4f} > {args.fallback_warn_threshold:.4f})"
        )
    if stats.factory_beep_below_target:
        print("warning=factory_beep_share_below_target (target >= 0.3000)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())