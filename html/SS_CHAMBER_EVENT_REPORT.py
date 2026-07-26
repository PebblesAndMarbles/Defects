"""
Quick adhoc report generator for a single chamber/event token.
Scans folder inventory directly and builds HTML + wafermap.
"""

from __future__ import annotations

import argparse
import os
import re
import traceback
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE_IMAGE_IDS = [8, 2, 3, 4]
FILENAME_RE = re.compile(
    r"^(?P<event>\d{6}_\d{4})_(?P<lot>[^_]+)_(?P<wafer>\d+)_(?P<defect>\d+)_(?P<image>\d+)\.jpg$",
    re.IGNORECASE,
)
COORDS_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs", "surf_scan", "SS_COORDINATES.csv"
)

ELEMENT_SYMBOLS = {
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


# ---------------------------------------------------------------------------
# Quadtree for label collision avoidance
# ---------------------------------------------------------------------------

class _QTNode:
    """Minimal quadtree node for 2-D rectangle collision detection."""
    __slots__ = ("bounds", "items", "children", "capacity")

    def __init__(self, x0, y0, x1, y1, capacity=6):
        self.bounds = (x0, y0, x1, y1)
        self.capacity = capacity
        self.items: list[tuple[float, float, float, float]] = []  # (x0,y0,x1,y1)
        self.children: list[_QTNode] | None = None

    def _subdivide(self):
        x0, y0, x1, y1 = self.bounds
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        self.children = [
            _QTNode(x0, y0, mx, my, self.capacity),
            _QTNode(mx, y0, x1, my, self.capacity),
            _QTNode(x0, my, mx, y1, self.capacity),
            _QTNode(mx, my, x1, y1, self.capacity),
        ]

    @staticmethod
    def _overlaps(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def intersects(self, rect) -> bool:
        if not self._overlaps(rect, self.bounds):
            return False
        for item in self.items:
            if self._overlaps(item, rect):
                return True
        if self.children:
            return any(c.intersects(rect) for c in self.children)
        return False

    def insert(self, rect):
        if not self._overlaps(rect, self.bounds):
            return
        if self.children is None:
            self.items.append(rect)
            if len(self.items) > self.capacity:
                self._subdivide()
                for item in self.items:
                    for c in self.children:
                        c.insert(item)
                self.items = []
        else:
            for c in self.children:
                c.insert(rect)


def _place_label(
    ax,
    qt: _QTNode,
    px: float,
    py: float,
    label: str,
    data_to_fig,
    fig_to_data,
    font_size: float = 6.5,
):
    """
    Try candidate offsets (in points) around (px, py).
    Place the label at the first position that doesn't collide with
    already-placed labels or the wafer-circle boundary (r=150 mm).
    Falls back to the least-bad candidate if all collide.
    """
    # Candidate offsets in display points (dx, dy)
    offsets_pt = [
        (6, 6), (-6, 6), (6, -6), (-6, -6),
        (10, 0), (-10, 0), (0, 10), (0, -10),
        (14, 4), (-14, 4), (14, -4), (-14, -4),
        (4, 14), (-4, 14), (4, -14), (-4, -14),
        (18, 0), (-18, 0), (0, 18), (0, -18),
    ]

    # Estimate text box size in data units
    # Rough: ~5.5 pts per char wide, ~8 pts tall at font_size 6.5
    char_w_pt = font_size * 0.62
    text_w_pt = len(label) * char_w_pt
    text_h_pt = font_size * 1.3

    # Convert point sizes to data units via the axes transform
    # We'll use a small finite-difference approach
    def pt_to_data(pt_x, pt_y):
        """Convert a delta in display points to data-unit delta."""
        disp = ax.transData
        # origin in display coords
        o = disp.transform((0, 0))
        dx = disp.inverted().transform((o[0] + pt_x, o[1] + pt_y))
        return dx[0], dx[1]

    tw_d, _ = pt_to_data(text_w_pt, 0)
    _, th_d = pt_to_data(0, text_h_pt)
    tw_d = abs(tw_d)
    th_d = abs(th_d)

    best_rect = None
    best_offset = offsets_pt[0]

    for dx_pt, dy_pt in offsets_pt:
        dx_d, dy_d = pt_to_data(dx_pt, dy_pt)
        lx = px + dx_d
        ly = py + dy_d
        rect = (lx, ly, lx + tw_d, ly + th_d)

        # Check wafer boundary: label centre must be inside r<=150
        cx, cy = lx + tw_d / 2, ly + th_d / 2
        if cx ** 2 + cy ** 2 > 148 ** 2:
            # prefer inside wafer but don't hard-reject
            pass

        if not qt.intersects(rect):
            best_rect = rect
            best_offset = (dx_pt, dy_pt)
            break
        if best_rect is None:
            best_rect = rect
            best_offset = (dx_pt, dy_pt)

    dx_d, dy_d = pt_to_data(*best_offset)
    lx = px + dx_d
    ly = py + dy_d

    ax.annotate(
        label,
        xy=(px, py),
        xytext=(lx, ly),
        fontsize=font_size,
        color="#e0e0e0",
        arrowprops=dict(
            arrowstyle="-",
            color="#607D8B",
            lw=0.6,
            shrinkA=2,
            shrinkB=1,
        ),
        bbox=dict(
            boxstyle="round,pad=0.15",
            facecolor="#10161d",
            edgecolor="none",
            alpha=0.75,
        ),
        zorder=10,
    )

    final_rect = (lx, ly, lx + tw_d, ly + th_d)
    qt.insert(final_rect)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def path_to_uri(path_text: str) -> str:
    try:
        return Path(path_text).as_uri()
    except (ValueError, OSError):
        return str(path_text).replace("\\", "/")


def normalize_key(value):
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
    text = normalize_key(value)
    try:
        return (0, int(text))
    except (TypeError, ValueError):
        return (1, text)


def infer_offset_slot_map(actual_ids: list[str]) -> dict[str, str]:
    base_set = set(BASE_IMAGE_IDS)
    parsed = []
    for value in actual_ids:
        try:
            parsed.append(int(normalize_key(value)))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return {}

    best_offset = 0
    best_hits = -1
    for offset in range(0, 65):
        hits = sum(1 for img_id in parsed if (img_id - offset) in base_set)
        if hits > best_hits:
            best_hits = hits
            best_offset = offset

    if best_hits <= 0:
        return {}

    mapping: dict[str, str] = {}
    for img_id in parsed:
        base_id = img_id - best_offset
        if base_id in base_set:
            mapping[str(img_id)] = str(base_id)
    return mapping


def parse_inventory_name(file_name: str) -> dict | None:
    match = FILENAME_RE.match(file_name)
    if not match:
        return None
    return match.groupdict()


# ---------------------------------------------------------------------------
# Inventory / manifest / coordinate loaders  (unchanged logic)
# ---------------------------------------------------------------------------

def build_rows_from_inventory(
    image_dir: str,
    event_token: str,
    target_date: str | None = None,          # None = no date filter
) -> tuple[list[dict], dict]:
    rows_by_key = {}
    stats = {
        "files_scanned": 0,
        "files_parsed": 0,
        "defect_rows": 0,
        "remapped_slots": 0,
    }

    for entry in os.scandir(image_dir):
        if not entry.is_file():
            continue
        stats["files_scanned"] += 1

        # Date filter — skip only if a target_date is specified AND doesn't match
        if target_date is not None:
            modified = datetime.fromtimestamp(entry.stat().st_mtime)
            if modified.strftime("%Y-%m-%d") != target_date:
                continue

        parsed = parse_inventory_name(entry.name)
        if not parsed:
            continue
        if parsed["event"] != event_token:
            continue

        stats["files_parsed"] += 1
        wafer_id = parsed["wafer"]
        defect_id = normalize_key(parsed["defect"])
        image_id = normalize_key(parsed["image"])

        key = (wafer_id, defect_id)
        rec = rows_by_key.setdefault(
            key,
            {
                "WAFER_ID": wafer_id,
                "DEFECT_ID": defect_id,
                "LOT": parsed["lot"],
                "slots": {str(base): None for base in BASE_IMAGE_IDS},
                "actual_slots": {},
            },
        )
        rec["actual_slots"][image_id] = {
            "uri": path_to_uri(entry.path),
            "path": entry.path,
        }

    rows = []
    for rec in rows_by_key.values():
        image_id_map = infer_offset_slot_map(list(rec["actual_slots"].keys()))
        for actual_id, base_id in image_id_map.items():
            slot = rec["actual_slots"].get(actual_id)
            if slot and rec["slots"].get(base_id) is None:
                rec["slots"][base_id] = slot
                if actual_id != base_id:
                    stats["remapped_slots"] += 1

        for base in BASE_IMAGE_IDS:
            base_str = str(base)
            if rec["slots"].get(base_str) is None and base_str in rec["actual_slots"]:
                rec["slots"][base_str] = rec["actual_slots"][base_str]

        rec.pop("actual_slots", None)
        rec["slots"] = [rec["slots"].get(str(base)) for base in BASE_IMAGE_IDS]
        rows.append(rec)

    rows.sort(key=lambda r: (r["WAFER_ID"], defect_sort_key(r["DEFECT_ID"])))
    stats["defect_rows"] = len(rows)
    return rows, stats


def load_manifest_event_rows(
    manifest_csv: str, event_token: str, primary_equip: str
) -> tuple[pd.DataFrame, set, set, set]:
    usecols = [
        "PRIMARY_EQUIP", "INSPECTION_TIME", "WAFER_ID",
        "WAFER_KEY", "DEFECT_ID", "LOCAL_IMAGE_FILE",
    ]
    manifest = pd.read_csv(manifest_csv, usecols=usecols)

    event_rows = manifest[
        (manifest["PRIMARY_EQUIP"].astype(str).str.strip() == primary_equip)
        & (manifest["LOCAL_IMAGE_FILE"].astype(str).str.contains(event_token, regex=False))
    ].copy()

    if event_rows.empty:
        return event_rows, set(), set(), set()

    event_rows["INSPECTION_TIME"] = event_rows["INSPECTION_TIME"].map(normalize_ts)
    event_rows["WAFER_ID"] = event_rows["WAFER_ID"].astype(str).str.strip()
    event_rows["WAFER_KEY"] = event_rows["WAFER_KEY"].map(normalize_key)
    event_rows["DEFECT_ID"] = event_rows["DEFECT_ID"].map(normalize_key)

    key_wk = {
        (row["INSPECTION_TIME"], row["WAFER_KEY"], row["DEFECT_ID"])
        for _, row in event_rows.iterrows()
        if row["INSPECTION_TIME"] and row["WAFER_KEY"] and row["DEFECT_ID"]
    }
    key_wid = {
        (row["INSPECTION_TIME"], row["WAFER_ID"], row["DEFECT_ID"])
        for _, row in event_rows.iterrows()
        if row["INSPECTION_TIME"] and row["WAFER_ID"] and row["DEFECT_ID"]
    }
    key_img = {
        (row["WAFER_ID"], row["DEFECT_ID"])
        for _, row in event_rows.iterrows()
        if row["WAFER_ID"] and row["DEFECT_ID"]
    }
    return event_rows, key_wk, key_wid, key_img


def get_edx_columns(df):
    cols = []
    for col in df.columns:
        m = re.match(r"EDX_ELEM(\d+)_", col, re.IGNORECASE)
        if m:
            cols.append((int(m.group(1)), col))
    cols.sort()
    return [col for _, col in cols]


def format_edx_label(row, edx_cols):
    parts = []
    for col in edx_cols:
        val = pd.to_numeric(row.get(col), errors="coerce")
        if pd.isna(val) or val <= 0:
            continue
        m = re.match(r"EDX_ELEM(\d+)_", col, re.IGNORECASE)
        atomic_num = int(m.group(1)) if m else 0
        symbol = ELEMENT_SYMBOLS.get(atomic_num, col.split("_")[-1][:2].capitalize())
        parts.append((val, symbol, round(val)))
    parts.sort(reverse=True)
    if not parts:
        return ""
    symbols = "".join(p[1] for p in parts)
    values = ",".join(str(p[2]) for p in parts)
    return f"{symbols} - ({values})"


def load_coord_metadata(
    coords_csv: str,
    primary_equip: str,
    event_key_wk: set,
    event_key_wid: set,
) -> tuple[dict, int, list[dict]]:
    try:
        if not os.path.isfile(coords_csv):
            return {}, 0, []

        # Read only the columns we need — avoids loading 100+ EDX columns
        # from the 70 MB network-share CSV unnecessarily.
        _base_cols = [
            "PRIMARY_EQUIP", "SUBENTITY", "INSPECTION_TIME",
            "WAFER_ID", "WAFER_KEY", "DEFECT_ID",
            "WAFER_X_MM", "WAFER_Y_MM", "SIZE_D_UM",
            "EVENT_WAFER", "SLOT_ID",
        ]
        # Detect available columns first, then load with the intersection
        _peek = pd.read_csv(coords_csv, nrows=0)
        _edx = [c for c in _peek.columns if re.match(r"EDX_ELEM\d+_", c, re.IGNORECASE)]
        _usecols = [c for c in _base_cols if c in _peek.columns] + _edx

        coords = pd.read_csv(coords_csv, usecols=_usecols)
        if "SUBENTITY" in coords.columns:
            coords = coords[
                coords["SUBENTITY"].astype(str).str.strip() == primary_equip
            ].copy()
        elif "PRIMARY_EQUIP" in coords.columns:
            coords = coords[
                coords["PRIMARY_EQUIP"].astype(str).str.strip() == primary_equip
            ].copy()
        if "INSPECTION_TIME" not in coords.columns:
            return {}, 0, []

        for col in ("WAFER_ID", "WAFER_KEY", "DEFECT_ID", "WAFER_X_MM", "WAFER_Y_MM"):
            if col not in coords.columns:
                if col in ("WAFER_X_MM", "WAFER_Y_MM"):
                    return {}, 0, []
                coords[col] = ""

        coords["INSPECTION_TIME"] = coords["INSPECTION_TIME"].map(normalize_ts)
        coords["WAFER_ID"] = coords["WAFER_ID"].astype(str).str.strip()
        coords["WAFER_KEY"] = coords["WAFER_KEY"].map(normalize_key)
        coords["DEFECT_ID"] = coords["DEFECT_ID"].map(normalize_key)
        coords["WAFER_X_MM"] = pd.to_numeric(coords["WAFER_X_MM"], errors="coerce")
        coords["WAFER_Y_MM"] = pd.to_numeric(coords["WAFER_Y_MM"], errors="coerce")
        coords = coords.dropna(subset=["WAFER_X_MM", "WAFER_Y_MM"])

        event_times = {k[0] for k in event_key_wk} | {k[0] for k in event_key_wid}
        event_wafer_keys = {k[1] for k in event_key_wk}
        event_wafer_ids = {k[1] for k in event_key_wid}

        matched_rows = []
        for _, row in coords.iterrows():
            ts = row["INSPECTION_TIME"]
            wk = row["WAFER_KEY"]
            wid = row["WAFER_ID"]
            if not ts or ts not in event_times:
                continue
            if (wk and wk in event_wafer_keys) or (wid and wid in event_wafer_ids):
                matched_rows.append(row)

        if not matched_rows:
            return {}, 0, []

        matched_df = pd.DataFrame(matched_rows)

        result = {}
        for _, row in matched_df.iterrows():
            wafer_id = str(row.get("WAFER_ID", ""))
            defect_id = normalize_key(row.get("DEFECT_ID"))
            if not wafer_id or not defect_id:
                continue
            result[(wafer_id, defect_id)] = {
                "x": float(row.get("WAFER_X_MM")),
                "y": float(row.get("WAFER_Y_MM")),
            }

        edx_cols = get_edx_columns(matched_df)

        coord_rows = []
        for _, row in matched_df.sort_values(["EVENT_WAFER"]).iterrows():
            coord_rows.append(
                {
                    "event_wafer": normalize_key(row.get("EVENT_WAFER")),
                    "slot_id": normalize_key(row.get("SLOT_ID")),
                    "defect_id": normalize_key(row.get("DEFECT_ID")),
                    "x": (
                        ""
                        if pd.isna(row.get("WAFER_X_MM"))
                        else f"{float(row.get('WAFER_X_MM')):.1f}"
                    ),
                    "y": (
                        ""
                        if pd.isna(row.get("WAFER_Y_MM"))
                        else f"{float(row.get('WAFER_Y_MM')):.1f}"
                    ),
                    "size": (
                        ""
                        if pd.isna(row.get("SIZE_D_UM"))
                        else str(float(row.get("SIZE_D_UM")))
                    ),
                    "elem": format_edx_label(row, edx_cols),
                }
            )

        coord_rows.sort(
            key=lambda r: (r["event_wafer"], defect_sort_key(r["defect_id"]))
        )
        return result, len(matched_df), coord_rows

    except Exception:
        traceback.print_exc()
        return {}, 0, []


# ---------------------------------------------------------------------------
# Wafermap generator  — clean map + leader lines for imaged points only
# ---------------------------------------------------------------------------

def generate_wafermap(
    rows: list[dict],
    coord_meta: dict,
    coord_total_for_event: int,
    manifest_imaged_keys: set,
    out_dir: str,
    chamber: str,
    event_token: str,
) -> tuple[str, int, int]:
    png_name = f"{chamber}_{event_token}_wafermap.png"
    out_path = os.path.join(out_dir, png_name)

    fig, ax = plt.subplots(figsize=(7, 7), facecolor="#1a1a1a")
    ax.set_facecolor("#1a1a1a")

    # Wafer boundary circle
    ax.add_patch(
        plt.Circle((0, 0), 150, color="#90A4AE", fill=False, linewidth=2.0, zorder=5)
    )

    # Tight limits — no padding beyond ±151
    ax.set_xlim(-151, 151)
    ax.set_ylim(-151, 151)
    ax.set_aspect("equal")

    # Grid only — no ticks, no tick labels, no axis labels
    major = list(range(-150, 151, 50))
    ax.set_xticks(major)
    ax.set_yticks(major)
    ax.set_xticks(list(range(-150, 151, 25)), minor=True)
    ax.set_yticks(list(range(-150, 151, 25)), minor=True)
    ax.tick_params(which="both", bottom=False, left=False,
                   labelbottom=False, labelleft=False)
    ax.set_xlabel("")
    ax.set_ylabel("")

    ax.grid(which="major", color="#2E2E2E", linewidth=0.7, zorder=0)
    ax.grid(which="minor", color="#242424", linewidth=0.3, zorder=0)
    ax.axhline(0, color="#3E3E3E", linewidth=0.9, zorder=1)
    ax.axvline(0, color="#3E3E3E", linewidth=0.9, zorder=1)

    for spine in ax.spines.values():
        spine.set_visible(False)

    # --- Plot points ---
    imaged_points = 0
    non_imaged_points = 0
    imaged_coords: list[tuple[float, float, str]] = []  # (x, y, label)

    for key, meta in coord_meta.items():
        x, y = meta["x"], meta["y"]
        wafer_id, defect_id = key
        if key in manifest_imaged_keys:
            ax.scatter(
                x, y,
                c="#42A5F5", marker="o", s=56,
                alpha=0.88, zorder=3,
                edgecolors="#90CAF9", linewidth=1,
            )
            imaged_points += 1
            imaged_coords.append((x, y, defect_id))
        else:
            ax.scatter(
                x, y,
                c="#9E9E9E", marker="x", s=42,
                alpha=0.8, zorder=2,
            )
            non_imaged_points += 1

    # --- Leader lines for imaged points only ---
    # We need the figure rendered first so transforms are valid.
    # Draw the figure canvas so transforms are initialised.
    fig.canvas.draw()

    qt = _QTNode(-151, -151, 151, 151, capacity=6)

    # Sort by distance from centre so central (denser) points get first pick
    imaged_coords.sort(key=lambda t: t[0] ** 2 + t[1] ** 2)

    for px, py, label in imaged_coords:
        if not label:
            continue
        _place_label(ax, qt, px, py, label,
                     data_to_fig=None, fig_to_data=None)

    fig.tight_layout(pad=0.4)
    fig.savefig(out_path, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)

    return png_name, imaged_points, non_imaged_points


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def image_cell(slot: dict | None) -> str:
    if not slot:
        return (
            "<td class='missing'>"
            "<div class='missing-txt'>missing</div>"
            "</td>"
        )
    safe = escape(slot["uri"])
    return (
        "<td>"
        "<div class='img-wrap'>"
        f"<a href='{safe}' target='_blank'>"
        f"<img src='{safe}' loading='lazy' alt='surf image'></a>"
        "</div>"
        "</td>"
    )


# ---------------------------------------------------------------------------
# HTML renderer  — fixed scroll / layout
# ---------------------------------------------------------------------------

def render_html(
    rows: list[dict],
    chamber: str,
    event_token: str,
    wafermap_name: str,
    build_stats: dict,
    coord_rows: list[dict],
) -> str:

    body = []
    for row in rows:
        body.append(
            "<tr>"
            + f"<td class='defect-col'>{escape(row['DEFECT_ID'])}</td>"
            + "".join(image_cell(slot) for slot in row["slots"])
            + "</tr>"
        )

    coord_body = []
    for rec in coord_rows:
        coord_body.append(
            "<tr>"
            + f"<td>{escape(rec['event_wafer'])}</td>"
            + f"<td>{escape(rec['slot_id'])}</td>"
            + f"<td>{escape(rec['defect_id'])}</td>"
            + f"<td>{escape(rec['x'])}</td>"
            + f"<td>{escape(rec['y'])}</td>"
            + f"<td>{escape(rec['size'])}</td>"
            + f"<td>{escape(rec['elem'])}</td>"
            + "</tr>"
        )

    # ------------------------------------------------------------------
    # CSS strategy:
    #   • The outer page body does NOT scroll — overflow:hidden on html/body.
    #   • .frame fills the viewport below the header bar.
    #   • .left-panel scrolls internally (overflow-y:auto).
    #   • .right-panel scrolls internally (overflow-y:auto).
    #   • .wafermap-pane is NOT sticky — it sits at the top of left-panel
    #     naturally; the whole left-panel scrolls as one unit.
    #   • .coord-pane grows to fill remaining left-panel space.
    #   • On narrow screens (≤1100 px) we fall back to a stacked layout
    #     where the page body can scroll normally.
    # ------------------------------------------------------------------

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Adhoc Report: {escape(chamber)} {escape(event_token)}</title>
<style>
  /* ── reset ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  /* ── page shell ── */
  html, body {{
    height: 100%;
    background: #10161d;
    color: #e6edf3;
    font-family: 'Segoe UI', -apple-system, sans-serif;
    /* prevent the PAGE from scrolling — panels scroll internally */
    overflow: hidden;
  }}

  /* ── top header bar ── */
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
  h1 {{
    color: #98d8c8;
    font-size: 16px;
    white-space: nowrap;
  }}
  p.meta {{
    color: #9fb0bd;
    font-size: 11px;
    white-space: nowrap;
  }}

  /* ── main frame: sits below header, fills rest of viewport ── */
  .frame {{
    display: flex;
    flex-direction: row;
    gap: 8px;
    padding: 8px;
    /* subtract header height */
    height: calc(100vh - 36px);
    overflow: hidden;          /* children scroll, not the frame */
    align-items: stretch;
  }}

  /* ── left panel: fixed width, scrolls as a whole ── */
  .left-panel {{
    width: 410px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;          /* scroll left panel contents */
    overflow-x: hidden;
  }}

  /* wafermap pane — natural flow, no sticky */
  .wafermap-pane {{
    border: 1px solid #24303b;
    border-radius: 4px;
    padding: 6px;
    background: #0f151c;
    flex-shrink: 0;
  }}
  img.wafermap {{
    width: 100%;
    max-width: 390px;
    border: 1px solid #24303b;
    border-radius: 4px;
    display: block;
    margin: 0 auto;
  }}

  /* coord table pane — fills remaining left-panel height */
  .coord-pane {{
    border: 1px solid #24303b;
    border-radius: 4px;
    padding: 4px;
    background: #0f151c;
    /* grow to fill, but also independently scrollable */
    flex: 1 1 0;
    min-height: 120px;
    overflow: auto;
  }}

  .coord-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: auto;
    font-size: 11px;
  }}
  .coord-table th,
  .coord-table td {{
    border: 1px solid #24303b;
    padding: 2px 3px;
    text-align: right;
    color: #e6edf3;
    background: #0f151c;
  }}
  .coord-table th {{
    background: #1c2731;
    color: #98d8c8;
    position: sticky;
    top: 0;
    z-index: 2;
    font-weight: 600;
  }}
  .coord-table td:nth-child(1),
  .coord-table td:nth-child(2),
  .coord-table td:nth-child(3),
  .coord-table th:nth-child(1),
  .coord-table th:nth-child(2),
  .coord-table th:nth-child(3) {{ text-align: center; }}

  /* ── right panel: scrolls independently ── */
  .right-panel {{
    flex: 1 1 0;
    overflow: auto;
    padding: 4px;
  }}

  /* ── image table ── */
  table.img-table {{
    width: auto;
    border-collapse: collapse;
    table-layout: auto;
  }}
  col.col-defect  {{ width: 32px; }}
  col.col-base8   {{ width: 206px; }}
  col.col-base2,
  col.col-base3,
  col.col-base4   {{ width: 156px; }}

  .img-table th,
  .img-table td {{
    border: 1px solid #24303b;
    padding: 2px;
    text-align: center;
    vertical-align: top;
  }}
  .img-table th {{
    background: #1c2731;
    color: #e6edf3;
    position: sticky;
    top: 0;
    z-index: 2;
  }}
  .img-table th.defect-col,
  .img-table td.defect-col {{
    width: 32px;
    min-width: 32px;
    max-width: 32px;
    white-space: nowrap;
  }}
  .img-table tr:nth-child(even) td {{ background: #141d25; }}
  .img-table tr:nth-child(odd)  td {{ background: #111820; }}

  .img-wrap {{
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }}
  .img-table td img {{
    height: 120px;
    width: auto;
    max-width: 100%;
    display: block;
    margin: 0 auto;
    object-fit: contain;
    background: #0c1117;
    border-radius: 2px;
  }}
  .img-table td.missing {{ color: #768696; }}
  .missing-txt {{
    min-height: 120px;
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  /* ── narrow / portrait fallback ── */
  @media (max-width: 1100px) {{
    html, body {{ overflow: auto; }}
    .frame {{
      flex-direction: column;
      height: auto;
      overflow: visible;
    }}
    .left-panel {{
      width: 100%;
      flex-direction: row;
      overflow: visible;
    }}
    .wafermap-pane {{ flex-shrink: 0; width: auto; }}
    .coord-pane    {{ flex: 1; max-height: 50vh; }}
    .right-panel   {{ overflow: visible; }}
  }}
</style>
</head>
<body>

<div class="header-bar">
  <h1>Adhoc Report: {escape(chamber)} &nbsp;·&nbsp; Event {escape(event_token)}</h1>
  <p class="meta">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</div>

<div class="frame">

  <!-- LEFT PANEL -->
  <div class="left-panel">
    <div class="wafermap-pane">
      <img src="{escape(wafermap_name)}" class="wafermap" alt="wafermap">
    </div>
    <div class="coord-pane">
      <table class="coord-table">
        <thead>
          <tr>
            <th>#</th><th>SLOT</th><th>ID</th>
            <th>X</th><th>Y</th><th>SIZE</th><th>ELEM</th>
          </tr>
        </thead>
        <tbody>
          {''.join(coord_body)}
        </tbody>
      </table>
    </div>
  </div>

  <!-- RIGHT PANEL -->
  <div class="right-panel">
    <table class="img-table">
      <colgroup>
        <col class="col-defect">
        <col class="col-base8">
        <col class="col-base2">
        <col class="col-base3">
        <col class="col-base4">
      </colgroup>
      <thead>
        <tr>
          <th class="defect-col">ID</th>
          <th>Base 8</th>
          <th>Base 2</th>
          <th>Base 3</th>
          <th>Base 4</th>
        </tr>
      </thead>
      <tbody>
        {''.join(body)}
      </tbody>
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
        description="Generate adhoc chamber/event HTML report with wafermap and image grid."
    )
    parser.add_argument(
        "--chamber",
        default="AME409_PM6",
        help="Chamber/subentity name (example: AME409_PM6).",
    )
    parser.add_argument(
        "--event-token",
        default="260710_2002",
        help="Event token from filename prefix yymmdd_hhmm (example: 260701_1005).",
    )
    parser.add_argument(
        "--target-date",
        default=None,
        help=(
            "Optional file mtime filter YYYY-MM-DD. "
            "Leave unset to rely only on --event-token (recommended)."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Optional output directory override. "
            "Default: <workspace>/html/adhoc_chamber_events"
        ),
    )
    args = parser.parse_args()

    chamber = args.chamber
    event_token = args.event_token
    target_date = args.target_date


    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_dir = os.path.join(workspace_dir, "images", "surf_scan", chamber)
    manifest_csv = os.path.join(
        workspace_dir, "outputs", "surf_scan", "SS_EDX_IMAGES.csv"
    )
    out_dir = args.out_dir or os.path.join(workspace_dir, "html", "adhoc_chamber_events")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isdir(image_dir):
        raise FileNotFoundError(f"Image directory not found: {image_dir}")

    rows, build_stats = build_rows_from_inventory(image_dir, event_token, target_date)
    for row in rows:
        row["has_images"] = any(slot is not None for slot in row["slots"])

    print(f"Files scanned:              {build_stats['files_scanned']}")
    print(f"Files parsed:               {build_stats['files_parsed']}")
    print(f"Slots remapped by offset:   {build_stats['remapped_slots']}")
    print(f"Defect rows:                {build_stats['defect_rows']}")

    event_rows, event_key_wk, event_key_wid, event_img_keys = load_manifest_event_rows(
        manifest_csv, event_token, chamber
    )
    print(f"Manifest event rows:        {len(event_rows)}")
    print(f"Manifest key count (wk):    {len(event_key_wk)}")
    print(f"Manifest key count (wid):   {len(event_key_wid)}")
    print(f"Manifest imaged keys:       {len(event_img_keys)}")

    coord_meta, coord_total_for_event, coord_rows = load_coord_metadata(
        COORDS_CSV, chamber, event_key_wk, event_key_wid
    )
    print(f"Wafermap points:            {len(coord_meta)}")
    print(f"Coord rows matched:         {coord_total_for_event}")
    overlap = len(set(coord_meta.keys()) & event_img_keys)
    print(f"Image-key overlap:          {overlap}")

    wafermap_name, imaged_points, non_imaged_points = generate_wafermap(
        rows,
        coord_meta,
        coord_total_for_event,
        event_img_keys,
        out_dir,
        chamber,
        event_token,
    )
    print(f"Wafermap:                   {wafermap_name}")
    print(f"Imaged points plotted:      {imaged_points}")
    print(f"Non-imaged points plotted:  {non_imaged_points}")

    html = render_html(
        rows, chamber, event_token, wafermap_name, build_stats, coord_rows
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"adhoc_{chamber}_{event_token}_{ts}.html"
    out_path = os.path.join(out_dir, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written:             {out_path}")


if __name__ == "__main__":
    main()