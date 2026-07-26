"""
SS_INLINE_CHAMBER_REPORT.py

Generate a single-chamber SurfScan inline HTML report.

Scans images/surf_scan/<CHAMBER>/, groups by inspection-event (INSPECTION_TIME),
most recent first.  For each event a collapsible section (open by default) shows:

  Header:  SUBENTITY · INSPECTION_TIME · EVENT · N imaged · element summary
  Content: horizontal row of defect cards, each card = vertical stack of
           image slots [8, 4, 2, 3] (present images shown; absent slots
           rendered as a minimal dash placeholder).

No wafermap, no coordinate table — images are the primary artifact.

Data sources
------------
  images/surf_scan/<CHAMBER>/           image files
  outputs/surf_scan/SS_COORDINATES.csv  inspection-time + EDX metadata

Image filename format
---------------------
  YYMMDD_HHMM_LOT7_SLOTID_DEFECTID_IMAGEID.jpg
  e.g.  260710_2002_D450TS4_583_6_4.jpg

Usage
-----
  python html/SS_INLINE_CHAMBER_REPORT.py --chamber AME409_PM6
  python html/SS_INLINE_CHAMBER_REPORT.py --chamber AME409_PM6 --out-dir ./custom
  python html/SS_INLINE_CHAMBER_REPORT.py --chamber AME409_PM6 --lookback-days 30
"""
from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

FILENAME_RE = re.compile(
    r"^(?P<event_token>\d{6}_\d{4})_(?P<lot>[^_]+)_(?P<wafer_short>\d+)"
    r"_(?P<defect_id>\d+)_(?P<image_id>\d+)\.jpg$",
    re.IGNORECASE,
)

# Two slots displayed per defect (last two of pipeline base [2,3,4,8]):
# 4 = extra BF (medium brightness field)  — top image
# 8 = spectrum (EDX keV scale)            — bottom image
IMAGE_SLOT_ORDER = [4, 8]

# Per-slot colour palette for wafermaps (mirrors INLINE_CHAMBER_EVENT_REPORT.py)
WAFER_COLORS = [
    "#42A5F5",  # blue
    "#66BB6A",  # green
    "#FFA726",  # orange
    "#EF5350",  # red
    "#AB47BC",  # purple
    "#26C6DA",  # cyan
    "#FFCA28",  # amber
    "#EC407A",  # pink
    "#8D6E63",  # brown
    "#78909C",  # blue-grey
    "#7E57C2",  # deep-purple
    "#26A69A",  # teal
    "#D4E157",  # lime
    "#FF7043",  # deep-orange
    "#29B6F6",  # light-blue
    "#F06292",  # light-pink
]

# Pipeline-canonical base IMAGE_IDs (surf_scan_config.py: IMAGE_IDS_BASE).
# At download time the pipeline fetches these shifted by an offset:
#   offset = max(0, IMAGE_COUNT - 16)
#   actual_ids = [base + offset for base in IMAGE_IDS_BASE]
# This fires when the scanner captures extra out-of-focus frames before the
# final good block.  We reverse the shift below in _remap_images().
# 2=brightfield, 3=darkfield, 4=extra BF, 8=spectrum (EDX keV scale)
_PIPELINE_BASE_IDS     = [2, 3, 4, 8]
_PIPELINE_BASE_IDS_SET = set(_PIPELINE_BASE_IDS)

# SS_COORDINATES.csv base columns to load (EDX columns added dynamically)
_SS_COORDS_BASE = [
    "PRIMARY_EQUIP", "SUBENTITY", "INSPECTION_TIME",
    "SLOT_ID", "DEFECT_ID", "EVENT", "EVENT_WAFER",
    "SIZE_D_UM", "IMAGE_COUNT",
    "ACTUAL_LOT", "LOT7",
    "WAFER_X_MM", "WAFER_Y_MM",
    "WAFER_ID",
]

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


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _path_uri(path: str) -> str:
    try:
        return Path(path).as_uri()
    except (ValueError, OSError):
        return path.replace("\\", "/")


def _token_to_dt(token: str) -> datetime | None:
    """Parse 'YYMMDD_HHMM' → datetime, or None on failure."""
    try:
        return datetime.strptime(token, "%y%m%d_%H%M")
    except ValueError:
        return None


def _fmt_insp_time(raw: str) -> str:
    """Trim INSPECTION_TIME to 'YYYY-MM-DD HH:MM' for display."""
    s = str(raw).strip()
    return s[:16] if len(s) >= 16 else s


def _slot_sort_key(img_id_str: str) -> int:
    try:
        return IMAGE_SLOT_ORDER.index(int(img_id_str))
    except (ValueError, IndexError):
        return len(IMAGE_SLOT_ORDER)


def _remap_images(images: dict) -> dict:
    """
    Reverse the pipeline's offset-shift on actual image IDs.

    The pipeline downloads base IDs [2, 3, 4, 8] shifted by
        offset = max(0, IMAGE_COUNT - 16)
    so files on disk carry IDs like [5, 6, 7, 11] (offset=3) instead of
    [2, 3, 4, 8] (offset=0).  We find the shift that maps the actual IDs
    back to the base set and return a new dict keyed by canonical base IDs.

    If the actual IDs are already canonical the dict is returned unchanged.
    If no consistent offset is found (< 2 base hits) the dict is returned
    as-is so the caller still gets whatever images are available.
    """
    if not images:
        return images

    # Parse string keys to ints; skip any that are non-numeric
    int_ids: dict[str, int] = {}
    for k in images:
        try:
            int_ids[k] = int(k)
        except ValueError:
            pass

    if not int_ids:
        return images

    # Already canonical — nothing to do
    if all(v in _PIPELINE_BASE_IDS_SET for v in int_ids.values()):
        return images

    # Find the offset that maximises hits against the base set (range 0..64)
    best_offset, best_hits = 0, 0
    for offset in range(0, 65):
        hits = sum(1 for v in int_ids.values() if (v - offset) in _PIPELINE_BASE_IDS_SET)
        if hits > best_hits:
            best_hits, best_offset = hits, offset

    if best_hits < 2 or best_offset == 0:
        return images   # no useful remap found

    remapped: dict = {}
    for k, actual_int in int_ids.items():
        base_int = actual_int - best_offset
        if base_int in _PIPELINE_BASE_IDS_SET:
            remapped[str(base_int)] = images[k]
    return remapped if remapped else images


# ─────────────────────────────────────────────────────────────────────────────
# Image inventory builder
# ─────────────────────────────────────────────────────────────────────────────

def build_inventory(
    image_dir: str,
    lookback_days: int | None = None,
) -> tuple[dict[str, dict], dict]:
    """
    Scan chamber image folder and return:
        events : dict[event_token → dict[(slot_id, defect_id) → row]]
        stats  : {"scanned", "parsed", "skipped"}

    Row schema:
        {"lot": str, "slot_id": str, "defect_id": str,
         "images": {image_id_str: {"uri": str, "path": str}}}

    Images from the same (event_token, slot_id, defect_id) are merged into
    one row's "images" dict keyed by image_id.
    """
    events: dict[str, dict] = defaultdict(dict)
    stats = {"scanned": 0, "parsed": 0, "skipped": 0}
    cutoff_dt: datetime | None = None
    if lookback_days is not None:
        cutoff_dt = datetime.now() - timedelta(days=lookback_days)

    try:
        dir_entries = list(os.scandir(image_dir))
    except OSError as exc:
        print(f"  [WARN] Cannot scan {image_dir}: {exc}")
        return {}, stats

    for entry in dir_entries:
        if not entry.is_file() or not entry.name.lower().endswith(".jpg"):
            continue
        stats["scanned"] += 1
        m = FILENAME_RE.match(entry.name)
        if m is None:
            stats["skipped"] += 1
            continue

        token        = m.group("event_token")
        lot          = m.group("lot")
        wafer_short  = m.group("wafer_short")  # WAFER_ID[5:8], e.g. "583" from "DFEWE583MMF4"
        defect       = m.group("defect_id")
        img_id   = m.group("image_id")

        if cutoff_dt is not None:
            ev_dt = _token_to_dt(token)
            if ev_dt is not None and ev_dt < cutoff_dt:
                stats["skipped"] += 1
                continue

        stats["parsed"] += 1
        key = (wafer_short, defect)
        if key not in events[token]:
            events[token][key] = {
                "lot":         lot,
                "wafer_short": wafer_short,
                "defect_id":   defect,
                "images":      {},
            }
        row = events[token][key]
        if img_id not in row["images"]:
            row["images"][img_id] = {
                "uri":  _path_uri(entry.path),
                "path": entry.path,
            }

    # Post-scan: remap offset-shifted image IDs back to canonical base IDs.
    # The pipeline's offset = max(0, IMAGE_COUNT - 16) means defects with
    # IMAGE_COUNT > 16 have all image IDs shifted uniformly — we reverse
    # that shift per-defect so every card uses the same [2,3,4,8] key space.
    for token_dict in events.values():
        for row in token_dict.values():
            row["images"] = _remap_images(row["images"])

    return dict(events), stats


# ─────────────────────────────────────────────────────────────────────────────
# Coordinates / EDX loader
# ─────────────────────────────────────────────────────────────────────────────

def load_event_meta(
    coords_csv: str,
    chamber: str,
    event_tokens: list[str],
) -> dict[str, dict]:
    """
    Load SS_COORDINATES.csv and return per-event metadata keyed by event_token:

        event_token → {
            "insp_time":    str,   # canonical INSPECTION_TIME (YYYY-MM-DD HH:MM:SS)
            "event":        str,   # EVENT column value, e.g. "SS0"
            "elem_summary": str,   # top elements sorted by aggregate EDX value
        }

    Matching strategy: event_token's YYMMDD_HHMM is parsed to a "YYYY-MM-DD HH:MM"
    minute-level prefix and compared against the first 16 characters of each
    INSPECTION_TIME row.  This is robust to seconds differences between the
    manifest and the coordinates CSV.
    """
    if not os.path.isfile(coords_csv):
        return {}

    try:
        # Two-pass usecols: peek headers, then load only what we need
        _peek    = pd.read_csv(coords_csv, nrows=0)
        _edx     = [c for c in _peek.columns if re.match(r"EDX_ELEM\d+_", c, re.IGNORECASE)]
        _base    = [c for c in _SS_COORDS_BASE if c in _peek.columns]
        usecols  = _base + _edx
        df       = pd.read_csv(coords_csv, usecols=usecols)
    except Exception as exc:
        print(f"  [WARN] Could not read SS_COORDINATES.csv: {exc}")
        return {}

    # Filter to this chamber
    if "SUBENTITY" in df.columns:
        df = df[df["SUBENTITY"].astype(str).str.strip() == chamber].copy()
    elif "PRIMARY_EQUIP" in df.columns:
        df = df[df["PRIMARY_EQUIP"].astype(str).str.strip() == chamber].copy()
    else:
        return {}

    if df.empty or "INSPECTION_TIME" not in df.columns:
        return {}

    # Build minute-level prefix index from the coords DataFrame
    df["_minute"] = df["INSPECTION_TIME"].astype(str).str[:16]

    # Build the EDX column list for this DataFrame
    edx_cols = [c for c in df.columns if re.match(r"EDX_ELEM\d+_", c, re.IGNORECASE)]

    result: dict[str, dict] = {}
    for token in event_tokens:
        ev_dt = _token_to_dt(token)
        if ev_dt is None:
            continue
        minute_key = ev_dt.strftime("%Y-%m-%d %H:%M")
        ev_df = df[df["_minute"] == minute_key]
        if ev_df.empty:
            continue

        # Canonical INSPECTION_TIME
        insp_mode = ev_df["INSPECTION_TIME"].mode()
        insp_time = str(insp_mode.iloc[0]) if not insp_mode.empty else minute_key

        # EVENT column (e.g. "SS0", "BASELINE")
        event_val = ""
        if "EVENT" in ev_df.columns:
            ev_mode = ev_df["EVENT"].dropna().mode()
            event_val = str(ev_mode.iloc[0]).strip() if not ev_mode.empty else ""

        # Lot for event header (ACTUAL_LOT preferred over LOT7)
        lot = ""
        for lot_col in ("ACTUAL_LOT", "LOT7"):
            if lot_col in ev_df.columns:
                lt = ev_df[lot_col].dropna()
                if not lt.empty:
                    lot = str(lt.mode().iloc[0]).strip()
                    break

        # EDX aggregate: sum each element across all defect rows; keep positives
        elem_parts: list[tuple[float, str]] = []
        for col in edx_cols:
            total = pd.to_numeric(ev_df[col], errors="coerce").fillna(0).sum()
            if total <= 0:
                continue
            m_col = re.match(r"EDX_ELEM(\d+)_", col, re.IGNORECASE)
            if m_col:
                sym = ELEMENT_SYMBOLS.get(int(m_col.group(1)), f"#{m_col.group(1)}")
                elem_parts.append((total, sym))
        elem_parts.sort(reverse=True)
        # Top 6 symbols joined by thin dot; keep compact for the header bar
        elem_summary = " · ".join(p[1] for p in elem_parts[:6]) if elem_parts else ""

        # Coordinate rows for wafermap — key on wafer_short (WAFER_ID[5:8]),
        # matching the download naming in surf_scan_images._organized_dest:
        #   short_w = waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw
        coord_rows: list[dict] = []
        if "WAFER_X_MM" in ev_df.columns and "WAFER_Y_MM" in ev_df.columns:
            for _, r in ev_df.dropna(subset=["WAFER_X_MM", "WAFER_Y_MM"]).iterrows():
                waf_raw    = str(r.get("WAFER_ID", "")).strip()
                short_w    = waf_raw[5:8] if len(waf_raw) >= 8 else waf_raw
                try:
                    did = str(int(float(str(r.get("DEFECT_ID", "")).strip())))
                except (ValueError, TypeError):
                    did = str(r.get("DEFECT_ID", "")).strip()
                if short_w and did:
                    coord_rows.append({
                        "wafer_short": short_w,
                        "defect_id":   did,
                        "x": float(r["WAFER_X_MM"]),
                        "y": float(r["WAFER_Y_MM"]),
                    })

        result[token] = {
            "insp_time":    insp_time[:19],
            "event":        event_val,
            "lot":          lot,
            "elem_summary": elem_summary,
            "coord_rows":   coord_rows,
        }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_wafermap_svg(
    chamber: str,
    lot: str,
    insp_date: str,
    coord_rows: list[dict],
    imaged_keys: set,
) -> str:
    """
    Build a 188×188 px inline SVG wafermap for one inspection event.

    coord_rows  : [{"slot_id": str, "defect_id": str, "x": float, "y": float}]
    imaged_keys : {(slot_id_str, defect_id_str)} — defects that have local images

    Defects with images → coloured circle, coloured by SLOT_ID.
    Defects without images → gray × marker.
    Upper-left box : chamber · lot · date.
    Upper-right legend : SLOT_ID (3-digit) → colour.
    """
    # Wmap dimensions tied to grid layout:
    #   WIDTH  = 2 cols × 93 px + 1 gap × 2 px = 188 px
    #   HEIGHT = meta-row(43) + gap(2) + slot4-row(93) + gap(2) + slot8-row(70) = 210 px
    # Uses width-based uniform scale so the wafer circle is never cropped
    # horizontally; 11 px of vertical padding appears top/bottom (intentional).
    WMAP_W = 188
    WMAP_H = 210
    cx     = WMAP_W // 2    # 94
    cy     = 96              # shifted up from centre to free ~21 px at bottom for legend
    scale  = WMAP_W / 302.0  # 0.623 — 302 mm range → 188 px

    def to_px(mx: float, my: float) -> tuple[float, float]:
        return round(cx + mx * scale, 1), round(cy - my * scale, 1)

    r150 = round(150 * scale, 1)

    # Assign one colour per wafer_short (sorted for determinism)
    wafer_shorts_sorted = sorted({r["wafer_short"] for r in coord_rows})
    slot_colors = {
        ws: WAFER_COLORS[i % len(WAFER_COLORS)]
        for i, ws in enumerate(wafer_shorts_sorted)
    }

    p: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WMAP_W}" height="{WMAP_H}" '
        f'style="display:block;background:#1a1a1a;border-radius:4px;'
        f'border:1px solid #24303b;">'
    ]

    # Major grid every 50 mm
    for mm in range(-150, 151, 50):
        x1, y1 = to_px(mm, -151);  x2, y2 = to_px(mm,  151)
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="#2E2E2E" stroke-width="0.6"/>')
        x1, y1 = to_px(-151, mm);  x2, y2 = to_px( 151, mm)
        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="#2E2E2E" stroke-width="0.6"/>')

    # Centre cross
    x1, y1 = to_px(-151, 0); x2, y2 = to_px(151, 0)
    p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3E3E3E" stroke-width="0.8"/>')
    x1, y1 = to_px(0, -151); x2, y2 = to_px(0, 151)
    p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3E3E3E" stroke-width="0.8"/>')

    # Wafer boundary circle
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r150}" '
             f'fill="none" stroke="#90A4AE" stroke-width="1.5"/>')

    # Defect points
    D = 3

    for row in coord_rows:
        px, py   = to_px(row["x"], row["y"])
        ws, did  = row["wafer_short"], row["defect_id"]
        has_img  = (ws, did) in imaged_keys
        color    = slot_colors.get(ws, WAFER_COLORS[0])  # legend color for all points
        alpha    = "0.90" if has_img else "0.45"

        if has_img:
            p.append(
                f'<circle cx="{px}" cy="{py}" r="{D}" '
                f'fill="{color}" fill-opacity="{alpha}" '
                f'stroke="#ffffff33" stroke-width="0.5"/>'
            )
        else:
            p.append(
                f'<line x1="{px-D}" y1="{py-D}" x2="{px+D}" y2="{py+D}" '
                f'stroke="{color}" stroke-width="1.4" stroke-opacity="{alpha}"/>'
                f'<line x1="{px+D}" y1="{py-D}" x2="{px-D}" y2="{py+D}" '
                f'stroke="{color}" stroke-width="1.4" stroke-opacity="{alpha}"/>'
            )

    # Horizontal legend at bottom: coloured text only, no boxes.
    # With cy=96 the circle bottom is at ~189 px, leaving ~21 px for the legend.
    # Up to ITEMS_PER_ROW IDs per row; second row at +12 px if needed.
    if wafer_shorts_sorted:
        def _fmt_slot(s: str) -> str:
            try:
                return f"{int(s):03d}"
            except ValueError:
                return s

        ITEMS_PER_ROW = 8
        n_items  = len(wafer_shorts_sorted)
        n_rows   = (n_items + ITEMS_PER_ROW - 1) // ITEMS_PER_ROW
        item_w   = 23.0   # px per item (3-char monospace + gap)
        leg_fs   = 9 if n_rows == 1 else 8   # slightly smaller for two-row layout
        row_gap  = 12     # px between row baselines

        # Bottom-anchor the legend with 3 px margin
        bottom_y = WMAP_H - 3
        row_baselines = [
            bottom_y - (n_rows - 1 - r) * row_gap
            for r in range(n_rows)
        ]

        for row_idx, y_base in enumerate(row_baselines):
            row_ws   = wafer_shorts_sorted[row_idx * ITEMS_PER_ROW : (row_idx + 1) * ITEMS_PER_ROW]
            n_in_row = len(row_ws)
            # centre the row; item spacing includes ~6 px between items
            total_w  = n_in_row * item_w - 6
            start_x  = (WMAP_W - total_w) / 2
            for col_idx, ws in enumerate(row_ws):
                color = slot_colors[ws]
                lbl   = _fmt_slot(ws)
                x     = start_x + col_idx * item_w
                p.append(
                    f'<text x="{x:.1f}" y="{y_base}" '
                    f'font-size="{leg_fs}" font-weight="600" '
                    f'font-family="monospace" fill="{color}">'
                    f'{escape(lbl)}</text>'
                )

    p.append("</svg>")
    return "".join(p)


def _defect_entry(row: dict) -> str:
    """
    One defect column: slot-4 (BF, square ~93px) on top, slot-8 (spectrum,
    landscape ~70px) below.  Images use height:auto so there are no black
    letterbox bars.  Missing slots use slot-specific placeholder heights.
    """
    def _img_slot(base_id_str: str) -> str:
        info = row["images"].get(base_id_str)
        if info:
            u = escape(info["uri"])
            return (
                f'<div class="img-slot"><div class="img-wrap">'
                f'<a href="{u}" target="_blank">'
                f'<img src="{u}" loading="lazy" alt="slot {base_id_str}">'
                f'</a></div></div>'
            )
        return f'<div class="img-miss miss-{base_id_str}"><div>—</div></div>'

    return (
        '<div class="defect-entry">'
        + _img_slot("4")
        + _img_slot("8")
        + "</div>"
    )


def _event_section(
    token: str,
    defect_map: dict,
    chamber: str,
    meta: dict,
    idx: int,
) -> str:
    """
    Build one <details open> section for an inspection event.

    Header: LOT · inspection-time · EVENT badge · N imaged · elements.
    Body:   CSS grid — wafermap anchored top-left, defect entries fill right.
            Each entry is 1 col × 2 rows: slot-4 (BF) above slot-8 (spectrum).
    """
    insp_time  = meta.get("insp_time", "")
    event_val  = meta.get("event", "")
    elem_summ  = meta.get("elem_summary", "")
    lot        = meta.get("lot", "")
    coord_rows = meta.get("coord_rows", [])

    if not insp_time:
        dt = _token_to_dt(token)
        insp_time = dt.strftime("%Y-%m-%d %H:%M") if dt else token

    # Fall back to lot from image filenames if coords had no data
    if not lot:
        lots = {row["lot"] for row in defect_map.values()}
        lot = next(iter(lots), "")

    n_def = len(defect_map)

    # ── wafermap ─────────────────────────────────────────────────────────────
    imaged_keys = set(defect_map.keys())   # {(slot_id, defect_id)}
    insp_date   = insp_time[:10] if len(insp_time) >= 10 else ""
    wmap_html   = ""
    if coord_rows:
        svg       = _build_wafermap_svg(chamber, lot, insp_date, coord_rows, imaged_keys)
        wmap_html = f'<div class="wmap-pane">{svg}</div>'

    # ── defect entries ────────────────────────────────────────────────────────
    def _sort_key(r: dict) -> tuple:
        ws  = int(r["wafer_short"]) if r["wafer_short"].isdigit() else 999999
        did = int(r["defect_id"])   if r["defect_id"].isdigit()   else 999999
        return (ws, did)

    entries_html = "".join(
        _defect_entry(row)
        for row in sorted(defect_map.values(), key=_sort_key)
    )

    # ── metadata strip (grid row 1) ──────────────────────────────────────────
    wafer_ids_sorted = sorted(
        {row["wafer_short"] for row in defect_map.values()},
        key=lambda x: int(x) if x.isdigit() else x,
    )
    wafer_id_str = " \u00b7 ".join(
        f"{int(ws):03d}" if ws.isdigit() else ws for ws in wafer_ids_sorted
    )

    ms_parts: list[str] = [
        f'<span class="ms-subentity">{escape(chamber)}</span>',
    ]
    if lot:
        ms_parts.append(f'<span class="ms-lot">{escape(lot)}</span>')
    if event_val:
        ms_parts.append(f'<span class="ms-badge">{escape(event_val)}</span>')
    if insp_time:
        ms_parts.append(f'<span class="ms-time">{escape(_fmt_insp_time(insp_time))}</span>')
    if wafer_id_str:
        ms_parts.append(f'<span class="ms-wafers">{escape(wafer_id_str)}</span>')
    if elem_summ:
        ms_parts.append(f'<span class="ms-elem">{escape(elem_summ)}</span>')

    # ── assemble content ──────────────────────────────────────────────────────
    # wmap, meta-strip, and defect entries are all direct grid children.
    # With wmap: meta at cols 3/-1 row 1; entries auto-fill from col 3 rows 2-3,
    # then wrap to col 1 rows 4-5+ (below the wmap boundary).
    # Without wmap: meta spans full width (cols 1/-1 row 1).
    ms_cls          = "meta-strip" if wmap_html else "meta-strip ms-full"
    meta_strip_html = f'<div class="{ms_cls}">{chr(10).join(ms_parts)}</div>'

    content_inner = (
        f"\n    {wmap_html}"   # empty str when no wafermap
        f"\n    {meta_strip_html}"
        f"\n    {entries_html}"
    )

    return (
        f'\n<div class="event-details" id="ev-{idx}">'
        f'\n  <div class="event-content">'
        + content_inner
        + "\n  </div>"
        "\n</div>"
    )


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

  /* ── page body ─────────────────────────────────────────────────────────── */
  .page-body { padding: 10px 14px 40px; }

  /* ── event section (collapsible) ───────────────────────────────────────── */
  .event-details {
    border: 1px solid #1e2d3a;
    border-radius: 5px;
    margin-bottom: 8px;
    background: #0f151c;
  }

  /* ── event content: CSS grid ─────────────────────────────────────────── */
  /*
   * Explicit rows:  43 px (meta)  +  93 px (slot-4)  +  70 px (slot-8)
   * Auto rows:      repeating pattern 93 px / 70 px for additional pairs
   * Wmap:           grid-column 1/3 × grid-row 1/4 = 188 × 210 px
   * Meta-strip:     grid-column 3/-1 × grid-row 1   = beside wmap top
   * Defect entries: span 1 col × span 2 rows (93+70 = 165 px)
   * Row-2 overflow: auto-flow wraps to col 1 below the wmap boundary
   */
  .event-content {
    display: grid;
    grid-template-columns: repeat(auto-fill, 93px);
    grid-template-rows: 43px 93px 70px;
    grid-auto-rows: 93px 70px;
    grid-auto-flow: row dense;
    gap: 2px;
    padding: 4px;
    width: 100%;
    align-items: start;
  }

  /* wafermap: 2 cols × 3 rows = 188 × 210 px */
  .wmap-pane {
    grid-column: 1 / 3;
    grid-row: 1 / 4;
    align-self: start;
  }
  .wmap-pane svg { display: block; }

  /* metadata strip: beside wmap top (row 1 only, cols 3+) */
  .meta-strip {
    grid-column: 3 / -1;
    grid-row: 1;
    align-self: stretch;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 0 10px;
    background: #0c1320;
    border: 1px solid #1a2840;
    border-radius: 3px;
    overflow: hidden;
  }
  /* no-wmap variant: meta-strip spans full width */
  .meta-strip.ms-full { grid-column: 1 / -1; }

  .ms-subentity { color: #98d8c8; font-size: 11px; font-weight: 700; flex-shrink: 0; }
  .ms-lot   { color: #b8ccd8; font-size: 11px; font-weight: 600; }
  .ms-badge {
    color: #80CBC4; font-size: 9px; font-weight: 600;
    padding: 1px 5px; border-radius: 3px;
    background: #1a2e2e; border: 1px solid #2a4444;
    letter-spacing: 0.04em;
  }
  .ms-time   { color: #6a8090; font-size: 10px; font-family: monospace; }
  .ms-count  { color: #9fb0bd; font-size: 10px; }
  .ms-wafers { color: #7bb8b0; font-size: 10px; letter-spacing: 0.03em; }
  .ms-elem   { color: #7bb8b0; font-size: 10px; letter-spacing: 0.04em; }

  /* defect entry: 1 col × 2 rows (93 px slot-4 + 70 px slot-8 = 165 px) */
  .defect-entry {
    grid-column: span 1;
    grid-row: span 2;
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: #0c1117;
    border: 1px solid #2a3a4a;
    border-radius: 2px;
    overflow: hidden;
  }
  .img-slot {}
  .img-wrap {
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }
  /* height:auto — slot-4 (504×504) renders 93×93, slot-8 (1170×884) renders 93×70 */
  .img-slot img {
    width: 93px;
    height: auto;
    max-width: none;
    display: block;
    border-radius: 2px;
    background: #0c1117;
  }
  div.img-miss {
    width: 93px;
    color: #4a5a6a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    opacity: 0.35;
  }
  div.img-miss.miss-4 { height: 93px; }
  div.img-miss.miss-8 { height: 70px; }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Full page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_page(
    chamber: str,
    events: dict[str, dict],
    event_meta: dict[str, dict],
    gen_ts: str,
) -> str:
    # Newest event first (event tokens are YYMMDD_HHMM — lexicographic sort works)
    sorted_tokens = sorted(events.keys(), reverse=True)

    sections = [
        _event_section(token, events[token], chamber, event_meta.get(token, {}), idx)
        for idx, token in enumerate(sorted_tokens)
    ]
    body = "\n".join(sections) if sections else (
        '<p class="hdr-meta" style="padding:20px;">No events found.</p>'
    )

    n_events  = len(sorted_tokens)
    n_defects = sum(len(v) for v in events.values())
    meta_str  = (
        f"{n_events} event{'s' if n_events != 1 else ''}"
        f" · {n_defects} imaged defect{'s' if n_defects != 1 else ''}"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(chamber)} — SS Events</title>
<style>
{PAGE_CSS}
</style>
</head>
<body>

<div class="page-body">
{body}
</div>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Entry point — importable by batch runner
# ─────────────────────────────────────────────────────────────────────────────

def _find_cross_chamber_tokens(manifest_csv: str, chamber: str) -> set[str]:
    """
    Detect event tokens in this chamber's image folder that are orphaned
    cross-chamber images (pipeline routing bug).

    Signature of a leaked event:
      - At least one manifest row points to a file under this chamber's folder
      - None of those rows have PRIMARY_EQUIP == chamber (they are blank or
        reference another chamber — i.e. the metadata join failed at download time)

    These events produce images in the wrong folder with zeroed-second
    INSPECTION_TIMEs (HH:MM:00 vs. actual DB seconds).  They also have no
    matching row in SS_COORDINATES.csv for this chamber, so they never get
    a wafermap — consistent with all 11 missing-wafermap events observed.

    Returns the set of suspect event_tokens to exclude from the report.
    """
    if not os.path.isfile(manifest_csv):
        return set()
    try:
        df = pd.read_csv(
            manifest_csv,
            usecols=["PRIMARY_EQUIP", "LOCAL_IMAGE_FILE"],
            low_memory=False,
        )
    except Exception as exc:
        print(f"  [WARN] Could not read manifest for cross-chamber check: {exc}")
        return set()

    # Keep rows whose path falls under this chamber's subfolder
    in_folder = df["LOCAL_IMAGE_FILE"].astype(str).str.contains(
        chamber, regex=False, na=False
    )
    df = df[in_folder].copy()
    if df.empty:
        return set()

    # Parse event token from the filename portion of LOCAL_IMAGE_FILE
    _tok_re = re.compile(r"(\d{6}_\d{4})_")
    def _parse_token(path_str: str) -> str:
        fname = os.path.basename(path_str)
        m = _tok_re.match(fname)
        return m.group(1) if m else ""

    df["_token"] = df["LOCAL_IMAGE_FILE"].astype(str).apply(_parse_token)
    df = df[df["_token"] != ""]

    suspect: set[str] = set()
    for token, grp in df.groupby("_token"):
        pe = grp["PRIMARY_EQUIP"].astype(str).str.strip()
        has_match = (pe == chamber).any()
        if not has_match:
            suspect.add(token)

    return suspect


def run_for_chamber(
    chamber: str,
    out_dir: str,
    lookback_days: int | None = None,
) -> str:
    """
    Generate SS inline HTML report for one chamber.

    Returns 'ok' on success, 'skipped' if the image directory does not exist.
    Output files:
        <out_dir>/<chamber>.html            (stable filename, overwritten each run)
        <out_dir>/logs/<chamber>_completeness.log
    """
    workspace    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_dir    = os.path.join(workspace, "images", "surf_scan", chamber)
    coords_csv   = os.path.join(workspace, "outputs", "surf_scan", "SS_COORDINATES.csv")
    manifest_csv = os.path.join(workspace, "outputs", "surf_scan", "SS_EDX_IMAGES.csv")

    if not os.path.isdir(image_dir):
        print(f"  [SKIP] No image dir: {image_dir}")
        return "skipped"

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)

    # 1 — scan image inventory
    events, stats = build_inventory(image_dir, lookback_days=lookback_days)
    n_raw_events = len(events)
    print(
        f"  Files   : {stats['scanned']} scanned · {stats['parsed']} parsed"
        f" · {stats['skipped']} skipped"
        f"  |  Events: {n_raw_events}"
    )

    # 2 — cross-chamber leak detection via manifest
    suspect = _find_cross_chamber_tokens(manifest_csv, chamber)
    if suspect:
        print(
            f"  [WARN] {len(suspect)} cross-chamber event(s) excluded "
            f"(images routed to wrong folder by pipeline): {sorted(suspect)}"
        )
        events = {t: v for t, v in events.items() if t not in suspect}
    n_defects_total = sum(len(v) for v in events.values())
    print(f"  Events (after leak filter): {len(events)}  Defects: {n_defects_total}")

    # 3 — load coordinate / EDX metadata
    event_meta = load_event_meta(coords_csv, chamber, list(events.keys()))
    print(f"  Coord match: {len(event_meta)} / {len(events)} events")

    # 4 — render HTML
    gen_ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_out = render_page(chamber, events, event_meta, gen_ts)
    out_path = os.path.join(out_dir, f"{chamber}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"  Report  : {out_path}")

    # 5 — completeness log
    log_path = os.path.join(out_dir, "logs", f"{chamber}_completeness.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Chamber        : {chamber}\n")
        f.write(f"Generated      : {gen_ts}\n")
        f.write(f"Files scanned  : {stats['scanned']}\n")
        f.write(f"Files parsed   : {stats['parsed']}\n")
        f.write(f"Files skipped  : {stats['skipped']}\n")
        f.write(f"Events (raw)   : {n_raw_events}\n")
        f.write(f"Cross-chamber excluded: {len(suspect)}\n")
        if suspect:
            f.write(f"  Excluded tokens: {', '.join(sorted(suspect))}\n")
        f.write(f"Events (clean) : {len(events)}\n")
        f.write(f"Events in coords: {len(event_meta)}\n")
        f.write(f"Total defects  : {n_defects_total}\n")
    print(f"  Log     : {log_path}")

    return "ok"


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate SS inline chamber HTML report."
    )
    parser.add_argument(
        "--chamber", required=True,
        help="Chamber subentity name, e.g. AME409_PM6",
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="Output directory (default: html/SS_Inline_Reports/)",
    )
    parser.add_argument(
        "--lookback-days", type=int, default=None,
        help="Include only events within this many days (default: all events in folder)",
    )
    args = parser.parse_args()

    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir   = args.out_dir or os.path.join(workspace, "html", "SS_Inline_Reports")

    result = run_for_chamber(args.chamber, out_dir, lookback_days=args.lookback_days)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
