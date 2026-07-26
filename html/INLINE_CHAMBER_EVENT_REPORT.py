"""
INLINE_CHAMBER_EVENT_REPORT.py

Generate a single-chamber inline defect HTML report.
Scans images/defects/<CHAMBER>/, groups by LOT7 (most recent first),
produces one combined wafermap + SMP/BEEP image grid per LOT.

Image filename format expected:
    YYMMDD_HHMM_LOT7_WAFERSEQ_CLASS_LAYER_DEFECTID_IMAGEID.jpg
    e.g.  260509_1851_D605312_716_BEEP_8M6CL_24_2.jpg

Image grid columns: SMP·2  SMP·3  BEEP·2  BEEP·3
Wafermap markers:   SMP → dot (o),  BEEP → x
                    imaged → blue,   non-imaged → gray

Usage:
    python html/INLINE_CHAMBER_EVENT_REPORT.py --chamber AME409_PM6
    python html/INLINE_CHAMBER_EVENT_REPORT.py --chamber AME409_PM6 --lot D605312
    python html/INLINE_CHAMBER_EVENT_REPORT.py --chamber AME409_PM6 --out-dir ./custom
"""
from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from collections import defaultdict

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

FILENAME_RE = re.compile(
    r"^(?P<event>\d{6}_\d{4})_(?P<lot>[^_]+)_(?P<wafer_seq>\d+)"
    r"_(?P<cls>[^_]+)_(?P<layer>[^_]+)_(?P<defect>\d+)_(?P<image_id>\d+)\.jpg$",
    re.IGNORECASE,
)

# 4 canonical image columns: SMP slot 2, SMP slot 3, BEEP slot 2, BEEP slot 3
SLOT_KEYS   = ["SMP_2",   "SMP_3",   "BEEP_2",   "BEEP_3"]
SLOT_LABELS = ["SMP · 2", "SMP · 3", "BEEP · 2", "BEEP · 3"]

# Per-wafer color palette (dark-background visible)
WAFER_COLORS = [
    "#42A5F5",  # blue
    "#66BB6A",  # green
    "#FFA726",  # orange
    "#EF5350",  # red
    "#AB47BC",  # purple
    "#26C6DA",  # cyan
    "#FFCA28",  # amber
    "#EC407A",  # pink
]


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_key(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
    except (TypeError, ValueError):
        pass
    return text


def defect_sort_key(v: str):
    try:
        return (0, int(v))
    except (TypeError, ValueError):
        return (1, str(v))


def path_uri(path: str) -> str:
    try:
        return Path(path).as_uri()
    except (ValueError, OSError):
        return path.replace("\\", "/")


def _parse_fname(name: str) -> dict | None:
    m = FILENAME_RE.match(name)
    return m.groupdict() if m else None


# ─────────────────────────────────────────────────────────────────────────────
# Image inventory builder
# ─────────────────────────────────────────────────────────────────────────────

def build_inventory(
    image_dir: str,
    filter_lot: str | None = None,
) -> tuple[dict[str, list[dict]], dict]:
    """
    Scan chamber image folder.
    Returns:
        lots  : dict[lot7 → sorted list of defect row dicts]
        stats : {"scanned", "parsed", "skipped"}

    Each row dict:
        {wafer_seq, defect_id, layer, event, SMP_2, SMP_3, BEEP_2, BEEP_3}
        slot values are {"uri": ..., "path": ...} | None.
    """
    raw: dict[str, dict] = defaultdict(dict)   # lot → {(ws, did) → row}
    stats = {"scanned": 0, "parsed": 0, "skipped": 0}

    try:
        entries = list(os.scandir(image_dir))
    except OSError as exc:
        print(f"  [WARN] Could not scan image directory ({image_dir}): {exc}")
        return {}, stats

    for entry in entries:
        if not entry.is_file() or not entry.name.lower().endswith(".jpg"):
            continue
        stats["scanned"] += 1
        p = _parse_fname(entry.name)
        if p is None:
            stats["skipped"] += 1
            continue
        if filter_lot and p["lot"] != filter_lot:
            continue
        stats["parsed"] += 1

        lot      = p["lot"]
        ws       = p["wafer_seq"]
        did      = p["defect"]
        cls      = p["cls"].upper()
        layer    = p["layer"].upper()
        event    = p["event"]
        slot_key = f"{cls}_{p['image_id']}"
        key      = (ws, did)

        if key not in raw[lot]:
            raw[lot][key] = {
                "wafer_seq": ws,
                "defect_id": did,
                "layer":     layer,
                "event":     event,
                **{sk: None for sk in SLOT_KEYS},
            }

        if slot_key in SLOT_KEYS and raw[lot][key][slot_key] is None:
            raw[lot][key][slot_key] = {
                "uri":  path_uri(entry.path),
                "path": entry.path,
            }

    def _row_sort(r):
        ws = int(r["wafer_seq"]) if r["wafer_seq"].isdigit() else 0
        return (ws, defect_sort_key(r["defect_id"]))

    lots: dict[str, list[dict]] = {
        lot: sorted(row_dict.values(), key=_row_sort)
        for lot, row_dict in raw.items()
    }

    # Most recent event token → sort lots newest first
    lots = dict(sorted(
        lots.items(),
        key=lambda kv: max((r["event"] for r in kv[1]), default=""),
        reverse=True,
    ))
    return lots, stats


# ─────────────────────────────────────────────────────────────────────────────
# Coordinates loader
# ─────────────────────────────────────────────────────────────────────────────

def load_coords(coords_csv: str, chamber: str) -> pd.DataFrame:
    """
    Load defect coordinates filtered to a specific SUBENTITY (chamber).
    Keeps: LOT7, DEFECT_ID, CLASS, WAFER_X_MM, WAFER_Y_MM, IMAGE_COUNT, WAFER_KEY, LAYER.
    """
    if not os.path.isfile(coords_csv):
        return pd.DataFrame()
    try:
        wanted = {"LOT7", "ACTUAL_LOT", "DEFECT_ID", "CLASS", "WAFER_X_MM", "WAFER_Y_MM",
                  "IMAGE_COUNT", "WAFER_KEY", "SUBENTITY", "INSPECTION_TIME", "LAYER"}
        avail  = set(pd.read_csv(coords_csv, nrows=0).columns)
        usecols = list(wanted & avail)
        df = pd.read_csv(coords_csv, usecols=usecols)
    except Exception as exc:
        print(f"  [WARN] Could not read coords CSV ({coords_csv}): {exc}")
        return pd.DataFrame()

    if "SUBENTITY" not in df.columns:
        return pd.DataFrame()

    df = df[df["SUBENTITY"].astype(str).str.strip() == chamber].copy()

    for col in ("WAFER_X_MM", "WAFER_Y_MM"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "IMAGE_COUNT" in df.columns:
        df["IMAGE_COUNT"] = pd.to_numeric(df["IMAGE_COUNT"], errors="coerce").fillna(0)

    if "DEFECT_ID" in df.columns:
        df["DEFECT_ID"] = df["DEFECT_ID"].map(normalize_key)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# SVG wafermap generator  (pure string — no matplotlib)
# ─────────────────────────────────────────────────────────────────────────────

def build_svg_wafermap(
    lot: str,
    inventory_rows: list[dict],
    coords_df: pd.DataFrame,
    chamber: str,
    actual_lot: str | None = None,
) -> str | None:
    """
    Build an inline SVG wafermap for a single LOT.
    SMP → circle, BEEP → X.  Imaged points colored per-wafer; non-imaged gray.
    Returns SVG string or None if no coordinate data available.
    """
    if coords_df.empty or "LOT7" not in coords_df.columns:
        return None

    lot_coords = coords_df[
        coords_df["LOT7"].astype(str).str.strip() == lot
    ].dropna(subset=["WAFER_X_MM", "WAFER_Y_MM"]).copy()

    if lot_coords.empty:
        return None

    imaged_ids = {r["defect_id"] for r in inventory_rows}

    # ── Per-wafer color mapping ───────────────────────────────────────────────
    ws_to_dids: dict[str, set] = defaultdict(set)
    for r in inventory_rows:
        ws_to_dids[r["wafer_seq"]].add(r["defect_id"])

    wk_col = "WAFER_KEY" if "WAFER_KEY" in lot_coords.columns else None
    if wk_col:
        unique_wks = sorted(
            {normalize_key(v) for v in lot_coords[wk_col] if pd.notna(v)},
            key=lambda x: (int(x) if x.isdigit() else float("inf"), x),
        )
    else:
        unique_wks = ["all"]

    wk_to_label: dict[str, str] = {}
    if wk_col and ws_to_dids:
        for wk in unique_wks:
            wk_dids = set(
                lot_coords[lot_coords[wk_col].map(normalize_key) == wk]["DEFECT_ID"].tolist()
            )
            best_ws, best_votes = None, 0
            for ws, dids in ws_to_dids.items():
                votes = len(wk_dids & dids)
                if votes > best_votes:
                    best_votes, best_ws = votes, ws
            if best_ws and best_votes > 0:
                wk_to_label[wk] = best_ws
    for i, wk in enumerate(unique_wks):
        if wk not in wk_to_label:
            wk_to_label[wk] = f"W{i + 1}"

    wk_to_color: dict[str, str] = {
        wk: WAFER_COLORS[i % len(WAFER_COLORS)]
        for i, wk in enumerate(unique_wks)
    }

    # ── SVG coordinate helpers ──────────────────────────────────────────────
    SIZE  = 188
    PAD   = 8
    INNER = SIZE - 2 * PAD
    SCALE = INNER / 302.0  # 302 = span of -151..151 mm

    def to_px(mx: float, my: float) -> tuple[float, float]:
        return (
            round(PAD + (mx + 151) * SCALE, 1),
            round(PAD + (151 - my) * SCALE, 1),  # Y-axis flipped
        )

    cx, cy = to_px(0, 0)
    r150   = round(150 * SCALE, 1)

    # ── Build SVG ──────────────────────────────────────────────────────────────
    p: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}" '
        f'style="display:block;background:#1a1a1a;border-radius:4px;'
        f'border:1px solid #24303b;">'
    ]

    # Grid lines (major every 50 mm)
    for mm in range(-150, 151, 50):
        x1, y1 = to_px(mm, -151);  x2, y2 = to_px(mm,  151)
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#2E2E2E" stroke-width="0.6"/>')
        x1, y1 = to_px(-151, mm);  x2, y2 = to_px( 151, mm)
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#2E2E2E" stroke-width="0.6"/>')

    # Centre cross
    x1, y1 = to_px(-151, 0); x2, y2 = to_px(151, 0)
    p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3E3E3E" stroke-width="0.8"/>')
    x1, y1 = to_px(0, -151); x2, y2 = to_px(0, 151)
    p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3E3E3E" stroke-width="0.8"/>')

    # Wafer boundary
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r150}" fill="none" stroke="#90A4AE" stroke-width="1.5"/>')

    # Defect points + collect labels
    labeled:     list[tuple[float, float, str]] = []
    labeled_ids: set[str] = set()
    D = 4  # marker half-size in px

    for _, row in lot_coords.iterrows():
        mx      = float(row["WAFER_X_MM"])
        my      = float(row["WAFER_Y_MM"])
        did     = str(row.get("DEFECT_ID", ""))
        cls     = str(row.get("CLASS", "")).upper() if "CLASS" in lot_coords.columns else ""
        wk      = normalize_key(row.get(wk_col, "all")) if wk_col else "all"
        has_img = did in imaged_ids
        color   = wk_to_color.get(wk, WAFER_COLORS[0]) if has_img else "#6E7E8E"
        alpha   = "0.90" if has_img else "0.50"
        px, py  = to_px(mx, my)

        if cls == "BEEP":
            p.append(
                f'<line x1="{px-D}" y1="{py-D}" x2="{px+D}" y2="{py+D}" '
                f'stroke="{color}" stroke-width="2" stroke-opacity="{alpha}"/>'
                f'<line x1="{px+D}" y1="{py-D}" x2="{px-D}" y2="{py+D}" '
                f'stroke="{color}" stroke-width="2" stroke-opacity="{alpha}"/>'
            )
        else:
            sc = "#ffffff33" if has_img else "none"
            p.append(
                f'<circle cx="{px}" cy="{py}" r="{D}" '
                f'fill="{color}" fill-opacity="{alpha}" '
                f'stroke="{sc}" stroke-width="0.5"/>'
            )

        if has_img and did and did not in labeled_ids:
            labeled.append((px, py, did))
            labeled_ids.add(did)

    # Defect-ID labels (capped at 40)
    for px, py, did in labeled[:40]:
        p.append(
            f'<text x="{px + D + 2}" y="{py - 2}" '
            f'font-size="9" font-family="sans-serif" '
            f'fill="#e0e0e0" fill-opacity="0.9">{escape(did)}</text>'
        )

    # Burn-in metadata (upper left)
    insp_str = ""
    if "INSPECTION_TIME" in lot_coords.columns:
        dates = sorted({str(t)[:10] for t in lot_coords["INSPECTION_TIME"].dropna()})
        insp_str = dates[0] if len(dates) == 1 else f"{dates[0]}\u2013{dates[-1]}"

    meta_lines = [chamber, actual_lot or lot]
    if insp_str:
        meta_lines.append(insp_str)

    bw = max(len(ln) for ln in meta_lines) * 6 + 8
    bh = len(meta_lines) * 12 + 5
    p.append(
        f'<rect x="3" y="3" width="{bw}" height="{bh}" '
        f'rx="2" fill="#10161d" fill-opacity="0.82" stroke="#2a3a4a" stroke-width="0.5"/>'
    )
    for i, line in enumerate(meta_lines):
        p.append(
            f'<text x="7" y="{3 + 11 + i * 12}" '
            f'font-size="{"10" if i == 0 else "8"}" font-family="sans-serif" '
            f'fill="#b0c4d0">{escape(line)}</text>'
        )

    # Per-wafer color legend (upper right)
    if unique_wks and unique_wks != ["all"]:
        lw = max(len(wk_to_label.get(wk, wk)) for wk in unique_wks) * 6 + 20
        lh = len(unique_wks) * 14 + 6
        lx = SIZE - lw - 3
        ly = 3
        p.append(
            f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" '
            f'rx="2" fill="#1c2731" fill-opacity="0.88" stroke="#2a3a4a" stroke-width="0.5"/>'
        )
        for i, wk in enumerate(unique_wks):
            color = wk_to_color[wk]
            label = wk_to_label.get(wk, wk)
            ry = ly + 5 + i * 14
            p.append(
                f'<rect x="{lx + 4}" y="{ry}" width="9" height="9" fill="{color}" rx="1"/>'
                f'<text x="{lx + 16}" y="{ry + 8}" '
                f'font-size="9" font-family="sans-serif" fill="#e6edf3">{escape(label)}</text>'
            )

    p.append("</svg>")
    return "".join(p)


# ─────────────────────────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────────────────────────

def _img_cell(slot: dict | None) -> str:
    if not slot:
        return "<div class='miss'><div class='miss-txt'>—</div></div>"
    u = escape(slot["uri"])
    return (
        f"<div class='img-slot'><div class='img-wrap'>"
        f"<a href='{u}' target='_blank'>"
        f"<img src='{u}' loading='lazy' alt='defect image'>"
        f"</a></div></div>"
    )


def _lot_section(lot: str, rows: list[dict],
                 svg_map: str | None, lot_idx: int,
                 actual_lot: str | None = None) -> str:
    layers    = sorted({r["layer"] for r in rows if r["layer"]})
    latest    = max((r["event"] for r in rows), default="")
    try:
        date_label = datetime.strptime(latest[:6], "%y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        date_label = latest[:6]

    # Flat sort: wafer_seq ascending, then defect_id ascending
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            int(r["wafer_seq"]) if r["wafer_seq"].isdigit() else float("inf"),
            defect_sort_key(r["defect_id"]),
        ),
    )

    entries = []
    for r in sorted_rows:
        smp_slots  = [r["SMP_2"],  r["SMP_3"]]
        beep_slots = [r["BEEP_2"], r["BEEP_3"]]
        has_smp  = any(s is not None for s in smp_slots)
        has_beep = any(s is not None for s in beep_slots)
        smp_html = (
            "<div class='img-pair'>"
            + "".join(_img_cell(s) for s in smp_slots)
            + "</div>"
        ) if has_smp else ""
        beep_html = (
            "<div class='img-pair'>"
            + "".join(_img_cell(s) for s in beep_slots)
            + "</div>"
        ) if has_beep else ""
        if has_smp or has_beep:
            # dual: reclassified defect has both SMP and BEEP images → span 2 cols
            entry_cls = "defect-entry defect-entry--dual" if (has_smp and has_beep) else "defect-entry"
            entries.append(
                f"<div class='{entry_cls}'>"
                + smp_html
                + beep_html
                + "</div>"
            )

    wmap_html = ""
    if svg_map:
        wmap_html = f"<div class='lot-wmap'>{svg_map}</div>"

    layer_str    = " · ".join(layers) if layers else ""
    display_lot  = actual_lot or lot
    summary_meta = (
        f"{len(rows)} defect{'s' if len(rows) != 1 else ''}"
        f" · {layer_str}"
        f" · {date_label}"
    )

    return f"""
<details open class="lot-details">
  <summary class="lot-summary">
    <span class="lot-id">{escape(display_lot)}</span>
    <span class="lot-meta">{escape(summary_meta)}</span>
  </summary>
  <div class="lot-content">
    {wmap_html}
    {''.join(entries)}
  </div>
</details>"""


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

PAGE_CSS = """\
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body {
    background: #10161d;
    color: #e6edf3;
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
  }

  /* ── sticky header bar ── */
  .header-bar {
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 12px;
    height: 38px;
    background: #0d131a;
    border-bottom: 1px solid #1e2d3a;
  }
  h1 { color: #98d8c8; font-size: 15px; white-space: nowrap; }
  .meta { color: #9fb0bd; font-size: 11px; }

  /* ── page body ── */
  .page-body { padding: 10px 12px; }

  /* ── LOT collapsible sections ── */
  .lot-details {
    border: 1px solid #1e2d3a;
    border-radius: 5px;
    margin-bottom: 8px;
    background: #0f151c;
    overflow: hidden;
  }
  .lot-summary {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 7px 12px;
    cursor: pointer;
    background: #131c26;
    border-bottom: 1px solid #1e2d3a;
    list-style: none;
    user-select: none;
  }
  .lot-summary::-webkit-details-marker { display: none; }
  .lot-summary::before {
    content: "\u25b6";
    font-size: 9px;
    color: #607D8B;
    flex-shrink: 0;
    transition: transform 0.12s;
  }
  .lot-details[open] > .lot-summary::before { transform: rotate(90deg); }
  .lot-id   { color: #98d8c8; font-weight: 700; font-size: 13px; flex-shrink: 0; }
  .lot-meta { color: #9fb0bd; font-size: 11px; }

  /* ── LOT content: CSS grid — wafermap anchored at [rows 1-2, cols 1-2],
        entries auto-fill to the right then wrap below as needed ── */
  .lot-content {
    display: grid;
    grid-template-columns: repeat(auto-fill, 93px);
    grid-auto-rows: 93px;
    grid-auto-flow: row dense;
    gap: 2px;
    padding: 4px;
    width: 100%;
  }
  .lot-wmap {
    grid-column: 1 / 3;   /* pins wafermap to cols 1-2 */
    grid-row:    1 / 3;   /* pins wafermap to rows 1-2 */
  }
  /* inline SVG fills the 2×2 grid area (2×93px + 1×2px gap = 188px) */
  .lot-wmap svg { display: block; }

  /* ── each defect entry: 1 col wide (single class) or 2 cols wide (dual: reclassified),
        always 2 rows tall. SMP column on left, BEEP column on right ── */
  .defect-entry {
    grid-column: span 1;   /* default: SMP-only or BEEP-only — 1 col × 2 rows */
    grid-row:    span 2;
    display: flex;
    flex-direction: row;
    gap: 2px;
    border: 1px solid #2a3a4a;
    border-radius: 2px;
    background: #0c1117;
    overflow: hidden;
  }
  /* reclassified defect has both SMP and BEEP images — expands to 2 cols */
  .defect-entry--dual {
    grid-column: span 2;
  }
  /* images within a pair (SMP or BEEP) stack vertically: slot-2 above slot-3 */
  .img-pair {
    width: 93px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .img-slot {}
  .img-wrap {
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }
  .img-slot img {
    width: 93px;
    height: 93px;
    max-width: none;
    display: block;
    object-fit: contain;
    background: #0c1117;
    border-radius: 2px;
  }
  div.miss { color: #4a5a6a; }
  .miss-txt {
    width: 93px;
    height: 93px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    opacity: 0.35;
  }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Page render
# ─────────────────────────────────────────────────────────────────────────────

def render_html(
    chamber: str,
    lot_sections: list[str],
    n_lots: int,
    n_defects: int,
) -> str:
    meta = (
        f"{n_lots} lot{'s' if n_lots != 1 else ''}"
        f" \u00b7 {n_defects} defect{'s' if n_defects != 1 else ''}"
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{escape(chamber)}</title>
<style>
{PAGE_CSS}
</style>
</head>
<body>
<div class="header-bar">
  <h1>{escape(chamber)}</h1>
  <p class="meta">{escape(meta)}</p>
</div>
<div class="page-body">
{''.join(lot_sections)}
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Completeness log
# ─────────────────────────────────────────────────────────────────────────────

def write_completeness_log(
    log_path: str,
    chamber: str,
    coords_df: pd.DataFrame,
    lots: dict[str, list[dict]],
    inv_stats: dict,
) -> None:
    """
    Compare image inventory against coordinates CSV.
    Flags defects where IMAGE_COUNT > 0 in coords but no image file was found.
    """
    lines = [
        f"Completeness Log — {chamber}",
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "─" * 64,
        (
            f"Inventory : {inv_stats['scanned']} files scanned, "
            f"{inv_stats['parsed']} parsed, {inv_stats['skipped']} skipped"
        ),
        f"LOTs in library : {len(lots)}",
        "",
    ]

    if coords_df.empty or "LOT7" not in coords_df.columns:
        lines.append("No coordinates data available — completeness check skipped.")
    else:
        # Set of (lot7, defect_id) present in the image library
        imaged_pairs: set[tuple[str, str]] = {
            (lot, r["defect_id"])
            for lot, rows in lots.items()
            for r in rows
        }

        n_with_count = 0
        missing_rows: list[dict] = []

        if "IMAGE_COUNT" in coords_df.columns:
            has_count = coords_df[coords_df["IMAGE_COUNT"] > 0]
            n_with_count = len(has_count)
            for _, row in has_count.iterrows():
                lot7  = str(row.get("LOT7", "")).strip()
                did   = str(row.get("DEFECT_ID", "")).strip()
                if (lot7, did) not in imaged_pairs:
                    missing_rows.append({
                        "lot7":   lot7,
                        "defect": did,
                        "cnt":    int(row.get("IMAGE_COUNT", 0)),
                        "wk":     normalize_key(row.get("WAFER_KEY", "")),
                        "insp":   str(row.get("INSPECTION_TIME", "")).strip(),
                        "layer":  str(row.get("LAYER", "")).strip(),
                    })

        lines.append(f"Coord rows (chamber)        : {len(coords_df)}")
        lines.append(f"Coord rows with IMAGE_COUNT>0: {n_with_count}")
        lines.append(f"Missing from image library  : {len(missing_rows)}")
        lines.append("")

        if missing_rows:
            hdr = f"{'LOT7':<12} {'DEFECT':<10} {'CNT':<5} {'LAYER':<8} {'WAFER_KEY':<14} INSPECTION_TIME"
            lines.append(hdr)
            lines.append("─" * len(hdr))
            for r in missing_rows[:300]:
                lines.append(
                    f"{r['lot7']:<12} {r['defect']:<10} {r['cnt']:<5} "
                    f"{r['layer']:<8} {r['wk']:<14} {r['insp']}"
                )
            if len(missing_rows) > 300:
                lines.append(f"  ... and {len(missing_rows) - 300} more rows omitted.")
        else:
            lines.append(
                "All IMAGE_COUNT>0 coord defects have matching images in the library."
            )

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Completeness log:           {log_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Core generator — importable by batch runner
# ─────────────────────────────────────────────────────────────────────────────

def run_for_chamber(
    chamber: str,
    out_dir: str,
    filter_lot: str | None = None,
) -> str:
    """
    Generate an inline defect HTML report for one chamber.
    Returns 'ok' on success, 'skipped' if no image directory exists.
    Outputs: <out_dir>/<chamber>.html  (stable, overwritten each run)
             <out_dir>/wafermaps/<chamber>_*_wafermap.png
             <out_dir>/logs/<chamber>_completeness.log
    """
    workspace  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_dir  = os.path.join(workspace, "images", "defects", chamber)
    coords_csv = os.path.join(workspace, "outputs", "defects",
                              "DEFECT_COORDINATES_EXTENDED.csv")

    if not os.path.isdir(image_dir):
        print(f"  [SKIP] Image dir not found: {image_dir}")
        return "skipped"

    os.makedirs(out_dir, exist_ok=True)

    # 1. Scan image inventory
    lots, inv_stats = build_inventory(image_dir, filter_lot=filter_lot)
    print(
        f"  Files: {inv_stats['scanned']} scanned, {inv_stats['parsed']} parsed"
        f"  |  LOTs: {len(lots)}"
    )

    # 2. Load coordinates
    coords_df = load_coords(coords_csv, chamber)
    print(f"  Coord rows : {len(coords_df)}")

    # Build LOT7 → ACTUAL_LOT lookup
    lot7_to_actual: dict[str, str] = {}
    if "LOT7" in coords_df.columns and "ACTUAL_LOT" in coords_df.columns:
        for _, row in coords_df[["LOT7", "ACTUAL_LOT"]].drop_duplicates().iterrows():
            l7 = str(row["LOT7"]).strip()
            al = str(row["ACTUAL_LOT"]).strip()
            if l7 and al and l7 not in lot7_to_actual:
                lot7_to_actual[l7] = al

    # 3. Per-LOT: wafermap + HTML section
    lot_sections: list[str] = []
    total_defects = 0

    for idx, (lot, rows) in enumerate(lots.items()):
        svg_map = build_svg_wafermap(lot, rows, coords_df, chamber,
                                     actual_lot=lot7_to_actual.get(lot))
        lot_sections.append(_lot_section(lot, rows, svg_map, idx,
                                         actual_lot=lot7_to_actual.get(lot)))
        total_defects += len(rows)
        display = lot7_to_actual.get(lot, lot)
        print(f"    {display}: {len(rows)} defect(s)  [svg {'ok' if svg_map else 'no coords'}]")

    # 4. Render and write HTML (stable filename — overwritten each run)
    html_out = render_html(chamber, lot_sections, len(lots), total_defects)
    out_html = os.path.join(out_dir, f"{chamber}.html")
    tmp_html = out_html + ".tmp"
    with open(tmp_html, "w", encoding="utf-8") as fh:
        fh.write(html_out)
    os.replace(tmp_html, out_html)
    print(f"  Written    : {out_html}")

    # 5. Completeness log (stable filename)
    logs_dir = os.path.join(out_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f"{chamber}_completeness.log")
    write_completeness_log(log_path, chamber, coords_df, lots, inv_stats)
    return "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Entry point (ad-hoc single-chamber mode)
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-chamber inline defect HTML report."
    )
    parser.add_argument(
        "--chamber", default="AME409_PM6",
        help="Chamber SUBENTITY name, e.g. AME409_PM6",
    )
    parser.add_argument(
        "--lot", default=None,
        help="Restrict to a single LOT7 value, e.g. D605312",
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="Output directory (default: <workspace>/html/adhoc_chamber_events/)",
    )
    args = parser.parse_args()

    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out_dir or os.path.join(
        workspace, "html", "adhoc_chamber_events"
    )
    print(f"Chamber    : {args.chamber}")
    print(f"Output dir : {out_dir}")
    run_for_chamber(args.chamber, out_dir, filter_lot=args.lot)


if __name__ == "__main__":
    main()
