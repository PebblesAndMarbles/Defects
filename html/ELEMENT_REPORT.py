"""
Element-driven adhoc report.
Wafermap rendered as inline SVG — no matplotlib/numpy dependency.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_IMAGE_IDS = [8, 2, 3, 4]

FILENAME_RE = re.compile(
    r"^(?P<event>\d{6}_\d{4})_(?P<lot>[^_]+)_(?P<wafer>\d+)_(?P<defect>\d+)_(?P<image>\d+)\.jpg$",
    re.IGNORECASE,
)

ELEMENT_SYMBOLS: dict[int, str] = {
    1: "H",   2: "He",  3: "Li",  4: "Be",  5: "B",
    6: "C",   7: "N",   8: "O",   9: "F",  10: "Ne",
    11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P",
    16: "S",  17: "Cl", 18: "Ar", 19: "K",  20: "Ca",
    21: "Sc", 22: "Ti", 23: "V",  24: "Cr", 25: "Mn",
    26: "Fe", 27: "Co", 28: "Ni", 29: "Cu", 30: "Zn",
    31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br",
    36: "Kr", 37: "Rb", 38: "Sr", 39: "Y",  40: "Zr",
    41: "Nb", 42: "Mo", 43: "Tc", 44: "Ru", 45: "Rh",
    46: "Pd", 47: "Ag", 48: "Cd", 49: "In", 50: "Sn",
    51: "Sb", 52: "Te", 53: "I",  54: "Xe", 55: "Cs",
    56: "Ba", 57: "La", 58: "Ce", 59: "Pr", 60: "Nd",
    61: "Pm", 62: "Sm", 63: "Eu", 64: "Gd", 65: "Tb",
    66: "Dy", 67: "Ho", 68: "Er", 69: "Tm", 70: "Yb",
    71: "Lu", 72: "Hf", 73: "Ta", 74: "W",  75: "Re",
    76: "Os", 77: "Ir", 78: "Pt", 79: "Au", 80: "Hg",
    81: "Tl", 82: "Pb", 83: "Bi", 84: "Po",
}

_SYMBOL_TO_Z: dict[str, int] = {v.upper(): k for k, v in ELEMENT_SYMBOLS.items()}

_CHAMBER_COLOURS = [
    "#42A5F5", "#EF5350", "#66BB6A", "#FFA726", "#AB47BC",
    "#26C6DA", "#FF7043", "#9CCC65", "#EC407A", "#7E57C2",
    "#29B6F6", "#D4E157", "#FF5722", "#26A69A", "#8D6E63",
]

LOOKBACK_DAYS = 7


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def path_to_uri(path_text: str) -> str:
    try:
        return Path(path_text).as_uri()
    except (ValueError, OSError):
        return str(path_text).replace("\\", "/")


def normalize_key(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
    except (TypeError, ValueError):
        pass
    return text


def normalize_ts(value) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text.split(".")[0]
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def defect_sort_key(value: str):
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, value)


def symbols_to_edx_cols(symbols: list[str], df_columns: list[str]) -> dict[str, str]:
    result = {}
    for sym in symbols:
        z = _SYMBOL_TO_Z.get(sym.upper())
        if z is None:
            continue
        pattern = re.compile(rf"^EDX_ELEM{z}_", re.IGNORECASE)
        for col in df_columns:
            if pattern.match(col):
                result[sym.upper()] = col
                break
    return result


def get_all_edx_columns(df_columns: list[str]) -> list[tuple[int, str]]:
    cols = []
    for col in df_columns:
        m = re.match(r"EDX_ELEM(\d+)_", col, re.IGNORECASE)
        if m:
            cols.append((int(m.group(1)), col))
    cols.sort()
    return cols


def format_edx_label(row, edx_col_pairs: list[tuple[int, str]]) -> str:
    parts = []
    for z, col in edx_col_pairs:
        val = pd.to_numeric(row.get(col), errors="coerce")
        if pd.isna(val) or val <= 0:
            continue
        symbol = ELEMENT_SYMBOLS.get(z, "??")
        parts.append((val, symbol, round(val)))
    parts.sort(reverse=True)
    if not parts:
        return ""
    return (
        "".join(p[1] for p in parts)
        + " - ("
        + ",".join(str(p[2]) for p in parts)
        + ")"
    )


def infer_offset_slot_map(actual_ids: list[str]) -> dict[str, str]:
    base_set = set(BASE_IMAGE_IDS)
    parsed = []
    for v in actual_ids:
        try:
            parsed.append(int(normalize_key(v)))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return {}
    best_offset, best_hits = 0, -1
    for offset in range(0, 65):
        hits = sum(1 for i in parsed if (i - offset) in base_set)
        if hits > best_hits:
            best_hits, best_offset = hits, offset
    if best_hits <= 0:
        return {}
    return {
        str(i): str(i - best_offset)
        for i in parsed
        if (i - best_offset) in base_set
    }


# ---------------------------------------------------------------------------
# SVG wafermap  (replaces matplotlib entirely)
# ---------------------------------------------------------------------------

def build_svg_wafermap(
    report_rows: list[dict],
    coord_meta: dict[tuple[str, str, str], dict],
    equip_colour: dict[str, str],
    size_px: int = 400,
) -> str:
    """
    Return a self-contained SVG string of the wafermap.
    Data space: -151..151 mm  →  mapped to 0..size_px pixels.
    """
    pad   = 10          # px padding inside SVG border
    inner = size_px - 2 * pad
    scale = inner / 302.0   # 302 = span of -151..151

    def to_px(mm_x: float, mm_y: float) -> tuple[float, float]:
        """Convert wafer mm coords to SVG pixel coords (y-axis flipped)."""
        px = pad + (mm_x + 151) * scale
        py = pad + (151 - mm_y) * scale   # flip Y
        return round(px, 2), round(py, 2)

    def mm_to_r(mm: float) -> float:
        return round(mm * scale, 2)

    cx, cy = to_px(0, 0)
    r150   = mm_to_r(150)

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size_px}" height="{size_px}" '
        f'style="background:#1a1a1a;display:block;">'
    )

    # ── grid lines ────────────────────────────────────────────────────────
    # minor grid every 25 mm
    for mm in range(-150, 151, 25):
        x1, y1 = to_px(mm, -151)
        x2, y2 = to_px(mm,  151)
        is_major = (mm % 50 == 0)
        colour   = "#2E2E2E" if is_major else "#1e1e1e"
        width    = "0.7"     if is_major else "0.3"
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{colour}" stroke-width="{width}"/>'
        )
        x1, y1 = to_px(-151, mm)
        x2, y2 = to_px( 151, mm)
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{colour}" stroke-width="{width}"/>'
        )

    # ── centre cross ──────────────────────────────────────────────────────
    x1, y1 = to_px(-151, 0);  x2, y2 = to_px(151, 0)
    lines.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="#3E3E3E" stroke-width="0.9"/>'
    )
    x1, y1 = to_px(0, -151);  x2, y2 = to_px(0, 151)
    lines.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="#3E3E3E" stroke-width="0.9"/>'
    )

    # ── wafer boundary circle ─────────────────────────────────────────────
    lines.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r150}" '
        f'fill="none" stroke="#90A4AE" stroke-width="2"/>'
    )

    # ── defect points ─────────────────────────────────────────────────────
    matched   = 0
    unmatched = 0
    for row in report_rows:
        key   = (row["equip"], row["wafer_id"], row["defect_id"])
        coord = coord_meta.get(key)
        if not coord:
            unmatched += 1
            continue
        matched += 1
        colour = equip_colour.get(row["equip"], "#42A5F5")
        px, py = to_px(coord["x"], coord["y"])
        lines.append(
            f'<circle cx="{px}" cy="{py}" r="4" '
            f'fill="{colour}" fill-opacity="0.85" '
            f'stroke="#ffffff" stroke-width="0.4" stroke-opacity="0.5"/>'
        )

    lines.append("</svg>")

    print(f"  SVG wafermap — matched: {matched}, unmatched: {unmatched}")
    if matched == 0 and unmatched > 0:
        print("  Sample report_row keys:")
        for row in report_rows[:3]:
            print(f"    {(row['equip'], row['wafer_id'], row['defect_id'])!r}")
        print("  Sample coord_meta keys:")
        for k in list(coord_meta.keys())[:3]:
            print(f"    {k!r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 1 — load & filter manifest
# ---------------------------------------------------------------------------

def load_element_manifest_rows(
    manifest_csv: str,
    elements_of_interest: list[str],
    lookback_days: int = LOOKBACK_DAYS,
) -> tuple[pd.DataFrame, dict[str, str], list[tuple[int, str]]]:

    df = pd.read_csv(manifest_csv)

    for col in ("PRIMARY_EQUIP", "WAFER_ID", "WAFER_KEY",
                "DEFECT_ID", "LOCAL_IMAGE_FILE", "INSPECTION_TIME"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df["INSPECTION_TIME"] = df["INSPECTION_TIME"].map(normalize_ts)
    df["WAFER_ID"]        = df["WAFER_ID"].astype(str).str.strip()
    df["WAFER_KEY"]       = df["WAFER_KEY"].map(normalize_key)
    df["DEFECT_ID"]       = df["DEFECT_ID"].map(normalize_key)

    print(f"Manifest rows total:        {len(df)}")

    cutoff     = datetime.now() - timedelta(days=lookback_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    before     = len(df)
    df         = df[df["INSPECTION_TIME"] >= cutoff_str].copy()
    print(f"Rows after {lookback_days}-day lookback:  {len(df)}  "
          f"(dropped {before - len(df)})")

    sym_to_col = symbols_to_edx_cols(elements_of_interest, list(df.columns))
    if not sym_to_col:
        raise ValueError(
            f"None of the requested elements {elements_of_interest} "
            f"matched any EDX column in the manifest."
        )

    mask = pd.Series(False, index=df.index)
    for col in sym_to_col.values():
        numeric = pd.to_numeric(df[col], errors="coerce").fillna(0)
        mask |= (numeric > 0)

    filtered = df[mask].copy()
    print(f"Rows matching elements:     {len(filtered)}")

    def extract_file_wafer(img_file: str) -> str:
        m = FILENAME_RE.search(os.path.basename(str(img_file)))
        return m.group("wafer") if m else ""

    filtered["FILE_WAFER"] = filtered["LOCAL_IMAGE_FILE"].map(extract_file_wafer)

    before_dedup = len(filtered)
    filtered = (
        filtered
        .sort_values("LOCAL_IMAGE_FILE")
        .drop_duplicates(
            subset=["PRIMARY_EQUIP", "WAFER_ID", "DEFECT_ID"],
            keep="first",
        )
        .reset_index(drop=True)
    )
    print(f"Rows after dedup:           {len(filtered)}  "
          f"(dropped {before_dedup - len(filtered)} duplicate image rows)")

    all_edx_col_pairs = get_all_edx_columns(list(df.columns))
    print(f"Element columns mapped:     {sym_to_col}")

    return filtered, sym_to_col, all_edx_col_pairs


# ---------------------------------------------------------------------------
# Step 2 — resolve image paths
# ---------------------------------------------------------------------------

def resolve_image_slots(
    filtered_df: pd.DataFrame,
    image_base_dir: str,
) -> dict[tuple[str, str, str], dict[str, dict | None]]:

    event_map: dict[tuple[str, str], list[dict]] = {}

    for _, row in filtered_df.iterrows():
        equip     = str(row.get("PRIMARY_EQUIP", "")).strip()
        wafer_id  = str(row.get("WAFER_ID", "")).strip()
        defect_id = normalize_key(row.get("DEFECT_ID"))
        img_file  = str(row.get("LOCAL_IMAGE_FILE", ""))

        basename = os.path.basename(img_file)
        m = FILENAME_RE.match(basename)
        if not m:
            continue

        event_token = m.group("event")
        file_wafer  = m.group("wafer")
        file_defect = normalize_key(m.group("defect"))

        event_map.setdefault((equip, event_token), []).append({
            "manifest_key": (equip, wafer_id, defect_id),
            "file_wafer":   file_wafer,
            "file_defect":  file_defect,
        })

    result: dict[tuple[str, str, str], dict[str, dict | None]] = {}

    for (equip, event_token), entries in event_map.items():
        folder = os.path.join(image_base_dir, equip)
        if not os.path.isdir(folder):
            continue

        pair_to_manifest = {
            (e["file_wafer"], e["file_defect"]): e["manifest_key"]
            for e in entries
        }
        wanted_pairs = set(pair_to_manifest.keys())

        actual_files: dict[tuple[str, str], dict[str, str]] = {}
        try:
            for entry in os.scandir(folder):
                if not entry.is_file():
                    continue
                pm = FILENAME_RE.match(entry.name)
                if not pm or pm.group("event") != event_token:
                    continue
                fw  = pm.group("wafer")
                fd  = normalize_key(pm.group("defect"))
                iid = normalize_key(pm.group("image"))
                pair = (fw, fd)
                if pair not in wanted_pairs:
                    continue
                actual_files.setdefault(pair, {})[iid] = entry.path
        except PermissionError:
            continue

        for file_pair, img_dict in actual_files.items():
            manifest_key = pair_to_manifest[file_pair]
            offset_map   = infer_offset_slot_map(list(img_dict.keys()))
            slots: dict[str, dict | None] = {str(b): None for b in BASE_IMAGE_IDS}

            for actual_id, base_id in offset_map.items():
                if slots.get(base_id) is None and actual_id in img_dict:
                    slots[base_id] = {
                        "uri":  path_to_uri(img_dict[actual_id]),
                        "path": img_dict[actual_id],
                    }
            for b in BASE_IMAGE_IDS:
                bs = str(b)
                if slots[bs] is None and bs in img_dict:
                    slots[bs] = {
                        "uri":  path_to_uri(img_dict[bs]),
                        "path": img_dict[bs],
                    }

            result[manifest_key] = slots

    return result


# ---------------------------------------------------------------------------
# Step 3 — load coordinates (chunked)
# ---------------------------------------------------------------------------

def load_coordinates(
    coords_csv: str,
    filtered_df: pd.DataFrame,
) -> dict[tuple[str, str, str], dict]:

    if not os.path.isfile(coords_csv):
        print("  WARNING: coords CSV not found.")
        return {}

    # Build manifest lookup FIRST — we only keep rows that match
    ts_fw_did_to_manifest: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    ts_wk_did_to_manifest: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    manifest_times: set[str] = set()

    for _, row in filtered_df.iterrows():
        ts  = row["INSPECTION_TIME"]
        wid = row["WAFER_ID"]
        wk  = row["WAFER_KEY"]
        did = row["DEFECT_ID"]
        eq  = str(row.get("PRIMARY_EQUIP", "")).strip()
        fw  = str(row.get("FILE_WAFER", "")).strip()
        if not ts:
            continue
        manifest_times.add(ts)
        manifest_key = (eq, wid, did)
        if fw and did:
            ts_fw_did_to_manifest[(ts, fw, did)] = manifest_key
        if wk and did:
            ts_wk_did_to_manifest[(ts, wk, did)] = manifest_key

    print(f"  Manifest unique timestamps:     {len(manifest_times)}")
    print(f"  Manifest file_wafer keys:       {len(ts_fw_did_to_manifest)}")

    # Column indices we need — discovered from header row
    NEEDED = {
        "INSPECTION_TIME", "WAFER_ID", "WAFER_KEY",
        "DEFECT_ID", "WAFER_X_MM", "WAFER_Y_MM",
    }

    result: dict[tuple[str, str, str], dict] = {}
    ts_miss   = 0
    key_miss  = 0
    rows_read = 0
    bad_rows  = 0

    try:
        with open(coords_csv, "r", encoding="utf-8", errors="replace") as fh:

            # ── parse header ──────────────────────────────────────────────
            raw_header = fh.readline()
            # auto-detect delimiter from header
            for delim in (",", "\t", "|", ";"):
                if delim in raw_header:
                    sep = delim
                    break
            else:
                sep = ","

            headers = [h.strip().strip('"') for h in raw_header.split(sep)]
            col_idx: dict[str, int] = {
                h: i for i, h in enumerate(headers) if h in NEEDED
            }
            print(f"  Delimiter detected: {sep!r}")
            print(f"  Columns found:      {sorted(col_idx.keys())}")

            if "WAFER_X_MM" not in col_idx or "WAFER_Y_MM" not in col_idx:
                print("  ERROR: WAFER_X_MM / WAFER_Y_MM not found in header.")
                return {}

            # ── stream rows ───────────────────────────────────────────────
            for raw_line in fh:
                raw_line = raw_line.rstrip("\r\n")
                if not raw_line:
                    continue

                fields = raw_line.split(sep)
                rows_read += 1

                try:
                    def _get(name: str) -> str:
                        idx = col_idx.get(name)
                        if idx is None or idx >= len(fields):
                            return ""
                        return fields[idx].strip().strip('"')

                    ts_raw = _get("INSPECTION_TIME")
                    ts     = normalize_ts(ts_raw)

                    if not ts or ts not in manifest_times:
                        ts_miss += 1
                        continue

                    x_raw = _get("WAFER_X_MM")
                    y_raw = _get("WAFER_Y_MM")
                    try:
                        x = float(x_raw)
                        y = float(y_raw)
                    except ValueError:
                        bad_rows += 1
                        continue

                    wid = _get("WAFER_ID").strip()
                    wk  = normalize_key(_get("WAFER_KEY"))
                    did = normalize_key(_get("DEFECT_ID"))

                    manifest_key = (
                        ts_fw_did_to_manifest.get((ts, wid, did))
                        or ts_wk_did_to_manifest.get((ts, wk, did))
                    )
                    if manifest_key is None:
                        key_miss += 1
                        continue

                    result[manifest_key] = {"x": x, "y": y}

                except Exception:
                    bad_rows += 1
                    continue

    except Exception as e:
        print(f"  ERROR reading coords file: {e}")
        print(f"  Partial matches collected: {len(result)}")
        return result

    print(f"  Coords rows read:               {rows_read}")
    print(f"  Coords rows skipped (ts miss):  {ts_miss}")
    print(f"  Coords rows skipped (key miss): {key_miss}")
    print(f"  Coords rows bad/unparseable:    {bad_rows}")
    print(f"  Coordinate matches:             {len(result)}")

    return result


# ---------------------------------------------------------------------------
# Step 4 — build report rows
# ---------------------------------------------------------------------------

def build_report_rows(
    filtered_df: pd.DataFrame,
    image_slots: dict[tuple[str, str, str], dict],
    coord_meta: dict[tuple[str, str, str], dict],
    all_edx_col_pairs: list[tuple[int, str]],
) -> list[dict]:

    rows = []
    for _, mrow in filtered_df.iterrows():
        equip     = str(mrow.get("PRIMARY_EQUIP", "")).strip()
        wafer_id  = str(mrow.get("WAFER_ID", "")).strip()
        defect_id = normalize_key(mrow.get("DEFECT_ID"))
        ts        = mrow.get("INSPECTION_TIME", "")
        wafer_key = normalize_key(mrow.get("WAFER_KEY"))

        key        = (equip, wafer_id, defect_id)
        slots_dict = image_slots.get(key, {str(b): None for b in BASE_IMAGE_IDS})
        slots_list = [slots_dict.get(str(b)) for b in BASE_IMAGE_IDS]
        coord      = coord_meta.get(key)

        rows.append({
            "equip":     equip,
            "ts":        ts,
            "wafer_key": wafer_key,
            "wafer_id":  wafer_id,
            "defect_id": defect_id,
            "slots":     slots_list,
            "x":         f"{coord['x']:.1f}" if coord else "",
            "y":         f"{coord['y']:.1f}" if coord else "",
            "elem":      format_edx_label(mrow, all_edx_col_pairs),
            "has_coord": coord is not None,
        })

    rows.sort(key=lambda r: r["ts"] or "", reverse=True)
    return rows


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def image_cell(slot: dict | None, out_dir: str) -> str:
    if not slot:
        return (
            "<td class='missing'>"
            "<div class='missing-txt'>—</div>"
            "</td>"
        )
    try:
        rel = os.path.relpath(slot["path"], out_dir).replace("\\", "/")
    except ValueError:
        rel = path_to_uri(slot["path"])
    safe = escape(rel)
    return (
        "<td><div class='img-wrap'>"
        f"<a href='{safe}' target='_blank'>"
        f"<img src='{safe}' loading='lazy' alt='surf image'></a>"
        "</div></td>"
    )


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

def render_html(
    report_rows: list[dict],
    svg_wafermap: str,
    equip_colour: dict[str, str],
    elements_of_interest: list[str],
    out_dir: str,
    lookback_days: int,
) -> str:

    elem_label = " + ".join(elements_of_interest)
    cutoff_str = (
        datetime.now() - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    # ── summary table rows ─────────────────────────────────────────────────
    seen_summary: set[tuple[str, str, str]] = set()
    summary_rows = []
    for row in report_rows:
        key = (row["equip"], row["ts"], row["wafer_id"])
        if key not in seen_summary:
            seen_summary.add(key)
            summary_rows.append(key)

    def swatch(equip: str) -> str:
        c = equip_colour.get(equip, "#607D8B")
        return (
            f"<span style='display:inline-block;width:8px;height:8px;"
            f"border-radius:50%;background:{c};"
            f"margin-right:4px;vertical-align:middle;'></span>"
        )

    summary_body = "".join(
        "<tr>"
        f"<td class='sum-td'>{swatch(eq)}{escape(eq)}</td>"
        f"<td class='sum-td ts-col'>{escape(ts)}</td>"
        f"<td class='sum-td'>{escape(wid)}</td>"
        "</tr>"
        for eq, ts, wid in summary_rows
    )

    # ── image table rows ───────────────────────────────────────────────────
    img_body = "".join(
        "<tr>"
        f"<td class='meta-col'>{swatch(row['equip'])}{escape(row['equip'])}</td>"
        + "".join(image_cell(slot, out_dir) for slot in row["slots"])
        + "</tr>"
        for row in report_rows
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Element Report: {escape(elem_label)}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  html, body {{
    height: 100%;
    background: #10161d;
    color: #e6edf3;
    font-family: 'Segoe UI', -apple-system, sans-serif;
    overflow: hidden;
  }}

  .header-bar {{
    height: 36px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 10px;
    flex-shrink: 0;
    background: #10161d;
    border-bottom: 1px solid #1e2d3a;
  }}
  h1     {{ color: #98d8c8; font-size: 16px; white-space: nowrap; }}
  p.meta {{ color: #9fb0bd; font-size: 11px; white-space: nowrap; }}

  .frame {{
    display: grid;
    grid-template-columns: 420px 1fr;
    gap: 8px;
    padding: 8px;
    height: calc(100vh - 36px);
    overflow: hidden;
    align-items: stretch;
  }}

  /* left panel: wafermap on top, summary table fills rest */
  .left-panel {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
    min-height: 0;
  }}
  .wm-block {{
    border: 1px solid #24303b;
    border-radius: 4px;
    padding: 6px;
    background: #0f151c;
    flex-shrink: 0;
  }}
  .summary-pane {{
    border: 1px solid #24303b;
    border-radius: 4px;
    background: #0f151c;
    flex: 1 1 0;
    min-height: 0;
    overflow: auto;
  }}
  .summary-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }}
  .summary-table th,
  .summary-table td {{
    border: 1px solid #24303b;
    padding: 2px 4px;
    text-align: left;
    white-space: nowrap;
  }}
  .summary-table th {{
    background: #1c2731;
    color: #98d8c8;
    position: sticky;
    top: 0;
    z-index: 2;
    font-weight: 600;
  }}
  .summary-table tr:nth-child(even) td {{ background: #141d25; }}
  .summary-table tr:nth-child(odd)  td {{ background: #111820; }}
  td.sum-td  {{ color: #b0c4d4; font-size: 11px; }}
  td.ts-col  {{ white-space: nowrap; }}

  /* right panel: image table */
  .img-panel {{
    overflow: auto;
    padding: 4px;
    min-height: 0;
  }}
  table.img-table {{
    width: auto;
    border-collapse: collapse;
    table-layout: auto;
  }}
  .img-table th,
  .img-table td {{
    border: 1px solid #24303b;
    padding: 2px 4px;
    text-align: center;
    vertical-align: top;
    white-space: nowrap;
  }}
  .img-table th {{
    background: #1c2731;
    color: #98d8c8;
    position: sticky;
    top: 0;
    z-index: 2;
    font-size: 11px;
  }}
  .img-table tr:nth-child(even) td {{ background: #141d25; }}
  .img-table tr:nth-child(odd)  td {{ background: #111820; }}
  td.meta-col {{
    font-size: 11px;
    color: #b0c4d4;
    text-align: left;
  }}
  .img-wrap {{
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }}
  .img-table td img {{
    height: 120px;
    width: auto;
    max-width: 200px;
    display: block;
    margin: 0 auto;
    object-fit: contain;
    background: #0c1117;
    border-radius: 2px;
  }}
  .img-table td.missing {{
    color: #768696;
    font-size: 11px;
    vertical-align: middle;
  }}
  .missing-txt {{
    min-height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  @media (max-width: 1100px) {{
    html, body {{ overflow: auto; }}
    .frame {{
      grid-template-columns: 1fr;
      height: auto;
      overflow: visible;
    }}
    .left-panel {{ overflow: visible; }}
    .img-panel  {{ overflow: visible; }}
  }}
</style>
</head>
<body>

<div class="header-bar">
  <h1>Element Report &nbsp;·&nbsp; {escape(elem_label)}</h1>
  <p class="meta">
    Last {lookback_days} days (since {cutoff_str})
    &nbsp;·&nbsp;
    {len(report_rows)} defects
    &nbsp;·&nbsp;
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  </p>
</div>

<div class="frame">

  <div class="left-panel">
    <div class="wm-block">
      {svg_wafermap}
    </div>
    <div class="summary-pane">
      <table class="summary-table">
        <thead>
          <tr>
            <th>CHAMBER</th>
            <th>INSPECTION TIME</th>
            <th>WAFER</th>
          </tr>
        </thead>
        <tbody>{summary_body}</tbody>
      </table>
    </div>
  </div>

  <div class="img-panel">
    <table class="img-table">
      <thead>
        <tr>
          <th>CHAMBER</th>
          <th>Base&nbsp;8</th>
          <th>Base&nbsp;2</th>
          <th>Base&nbsp;3</th>
          <th>Base&nbsp;4</th>
        </tr>
      </thead>
      <tbody>{img_body}</tbody>
    </table>
  </div>

</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate element-driven adhoc HTML report across chambers."
    )
    parser.add_argument(
        "--elements",
        nargs="+",
        default=["Ti", "Ni"],
        help="Element symbols to filter on (space-separated), e.g. --elements F Fe",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=60,
        help="Lookback window in days for manifest filtering.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Optional output directory override. "
            "Default: <workspace>/html/adhoc_elements"
        ),
    )
    args = parser.parse_args()

    elements_of_interest = args.elements
    lookback_days = args.lookback_days

    workspace_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_base_dir = os.path.join(workspace_dir, "images", "surf_scan")
    manifest_csv   = os.path.join(workspace_dir, "outputs", "surf_scan", "SS_EDX_IMAGES.csv")
    coords_csv     = os.path.join(workspace_dir, "outputs", "surf_scan", "SS_COORDINATES.csv")
    out_dir        = args.out_dir or os.path.join(workspace_dir, "html", "adhoc_elements")

    os.makedirs(out_dir, exist_ok=True)

    # 1. Filter manifest
    filtered_df, sym_to_col, all_edx_col_pairs = load_element_manifest_rows(
        manifest_csv, elements_of_interest, lookback_days
    )
    if filtered_df.empty:
        print("No matching rows found — exiting.")
        return

    # 2. Resolve image slots
    print("Resolving image slots from disk …")
    image_slots = resolve_image_slots(filtered_df, image_base_dir)
    found = sum(1 for s in image_slots.values() if any(v for v in s.values()))
    print(f"Defects with ≥1 image on disk: {found}")

    # 3. Load coordinates
    print("Loading coordinates …")
    coord_meta = load_coordinates(coords_csv, filtered_df)

    # 4. Build report rows
    report_rows = build_report_rows(
        filtered_df, image_slots, coord_meta, all_edx_col_pairs
    )
    print(f"Report rows:                   {len(report_rows)}")

    # 5. Assign chamber colours & build SVG wafermap
    equip_colour: dict[str, str] = {
        equip: _CHAMBER_COLOURS[i % len(_CHAMBER_COLOURS)]
        for i, equip in enumerate(sorted({r["equip"] for r in report_rows}))
    }
    print("Building SVG wafermap …")
    svg_wafermap = build_svg_wafermap(report_rows, coord_meta, equip_colour)

    # 6. Render HTML
    html = render_html(
        report_rows, svg_wafermap, equip_colour,
        elements_of_interest, out_dir, lookback_days
    )

    elem_label = "+".join(elements_of_interest)
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name   = f"elem_report_{elem_label}_{ts}.html"
    out_path   = os.path.join(out_dir, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written:                {out_path}")


if __name__ == "__main__":
    main()