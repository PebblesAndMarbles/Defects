# SS Inline Reports — Plan and Design Notes

Companion to `SS_HTML_REPORT_PATTERNS.md` and `INLINE_HTML_REPORT_PATTERNS.md`.
Covers:
1. Diagnosis of the existing `SS_CHAMBER_EVENT_REPORT.py` wafermap failure
2. Design for the new `SS_Inline_Reports` fileset (parallel to `Inline_Subentity_Reports`)
3. Integration outlook into `AME_Dash/SS_Report/`

Generated: 2026-07-14

---

## Part 1 — Wafermap Bug in SS_CHAMBER_EVENT_REPORT.py

### Observed symptom

Running `SS_CHAMBER_EVENT_REPORT.py --chamber AME409_PM6 --event-token 260710_2002`
produced:

- images rendered correctly in the right panel ✓
- coord table tbody empty ✗
- wafermap PNG generated but blank (no data points) ✗

See: `html/adhoc_chamber_events/adhoc_AME409_PM6_260710_2002_20260713_173036.html`

### Data verified present

All source data for this event IS present and internally consistent:

| Source | Key | Value |
|--------|-----|-------|
| `SS_COORDINATES.csv` | `PRIMARY_EQUIP` | `AME409_PM6` |
| `SS_COORDINATES.csv` | `INSPECTION_TIME` | `2026-07-10 20:02:57` |
| `SS_COORDINATES.csv` | `WAFER_KEY` | `7190668` |
| `SS_COORDINATES.csv` | `WAFER_ID` | `DFEWE583MMF4` |
| `SS_EDX_IMAGES.csv` | `PRIMARY_EQUIP` | `AME409_PM6` |
| `SS_EDX_IMAGES.csv` | `INSPECTION_TIME` | `2026-07-10 20:02:57` |
| `SS_EDX_IMAGES.csv` | `WAFER_KEY` | `7190668.0` (normalizes to `7190668`) |
| `SS_EDX_IMAGES.csv` | `LOCAL_IMAGE_FILE` | contains `260710_2002` ✓ |
| `images/surf_scan/AME409_PM6/` | filenames | `260710_2002_D450TS4_583_*_*.jpg` |

### Root cause

`load_coord_metadata` has a broad `except Exception: return {}, 0, []` that silently
discards any failure without printing a traceback. The coord table emptiness is consistent
with a silent exception during one of these steps:

- `pd.read_csv(coords_csv)` — loads all 100+ columns of the 70 MB `SS_COORDINATES.csv`
  over a network share with no `usecols` filter
- The iteration/matching loop or the `matched_df.sort_values(["EVENT_WAFER"])` call

The broad catch means the script exits normally but the coord/wafermap data is zeroed.

### Proposed fix

Two changes to `load_coord_metadata` in `SS_CHAMBER_EVENT_REPORT.py`:

**Fix A — Surface the exception**
```python
except Exception:
    import traceback
    traceback.print_exc()
    return {}, 0, []
```

This immediately reveals the actual error on next run without changing behavior.

**Fix B — Reduce CSV load surface area**

Add `usecols` to the `pd.read_csv` call so only needed columns are loaded:

```python
SS_COORDS_USECOLS = [
    "PRIMARY_EQUIP", "INSPECTION_TIME", "WAFER_ID", "WAFER_KEY",
    "DEFECT_ID", "WAFER_X_MM", "WAFER_Y_MM", "SIZE_D_UM",
    "EVENT_WAFER", "SLOT_ID",
]
# plus any EDX_ELEM* columns via a two-pass read or a filter after load
```

Loading 10 columns instead of 100+ from a 70 MB CSV over a network share is a
significant performance and reliability improvement.

**Fix C (if timestamp mismatch is the actual cause)**

If the exception surfaces a timestamp comparison issue, add a minute-level fallback
that matches `INSPECTION_TIME` up to `HH:MM` rather than `HH:MM:SS`:

```python
event_minute = event_token[0:6] + " " + event_token[7:9] + ":" + event_token[9:11]
# e.g. "260710 20:02" for token "260710_2002"
# use this to directly filter coords_df when the manifest join returns empty
```

### Confirmed resolution (2026-07-14)

Fixes A + B applied together in `SS_CHAMBER_EVENT_REPORT.py`. Re-running immediately
produced correct output:

```
Manifest event rows:        28
Wafermap points:            7
Coord rows matched:         7
Image-key overlap:          7
Imaged points plotted:      7
```

Root cause confirmed: the broad `except Exception` was swallowing a pandas error caused
by loading the full 100+ column CSV without `usecols`. Once only the required columns were
loaded the match completed correctly. The `traceback.print_exc()` addition remains in place
as a permanent guard against future silent failures.

---

## Part 2 — New SS_Inline_Reports Fileset Design

### Goal

Create a production-ready, schedulable per-chamber SS HTML report set analogous to
`html/Inline_Subentity_Reports/` (inline defects). Output goes to a new folder:

```
html/SS_Inline_Reports/
    AME409_PM6.html           ← stable overwrite each run
    AME409_PM5.html
    ...
    logs/
        AME409_PM6_completeness.log
```

### Files to create

| File | Purpose |
|------|---------|
| `html/SS_INLINE_CHAMBER_REPORT.py` | Single-chamber SS report; exposes `run_for_chamber(chamber, out_dir)` |
| `html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py` | Fleet batch runner; reads fleet list, calls `run_for_chamber` for each |

These mirror:
- `html/INLINE_CHAMBER_EVENT_REPORT.py` → `html/SS_INLINE_CHAMBER_REPORT.py`
- `html/INLINE_PRODUCTION_SUBENTITY_REPORTS.py` → `html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py`

### SS image filename format

```
YYMMDD_HHMM_LOT7_SLOTID_DEFECTID_IMAGEID.jpg
e.g.  260710_2002_D450TS4_583_6_4.jpg
```

| Field | Notes |
|-------|-------|
| `YYMMDD_HHMM` | Event token; maps to `INSPECTION_TIME` in SS_COORDINATES.csv |
| `LOT7` | 7-char lot ID; matches `LOT7` column |
| `SLOTID` | Carrier slot number; matches `SLOT_ID` column in SS_COORDINATES.csv |
| `DEFECTID` | Defect ID integer |
| `IMAGEID` | Typically 4 or 8 (the two SS image angles) |

Key difference from inline defects:
- SS has **no CLASS** (`SMP`/`BEEP`) in the filename — defects are unclassified or have
  a single class from the coordinates `CLASS` column
- SS slot field maps to `SLOT_ID` (carrier slot), not a wafer_seq
- Image IDs are 4 and 8, not 2 and 3

### Data sources

| Source | Path | Usage |
|--------|------|-------|
| SS coordinates | `outputs/surf_scan/SS_COORDINATES.csv` | x/y positions, element data, lot grouping |
| SS images | `images/surf_scan/<CHAMBER>/` | Image files, parsed via filename regex |
| Fleet (reuse) | Inline FLEET list or separate SS fleet | Chamber enumeration for batch runner |

**No manifest dependency**: `SS_INLINE_CHAMBER_REPORT.py` should NOT require
`SS_EDX_IMAGES.csv` for the primary workflow. The coordinates CSV plus the local
image directory are the only required sources. This avoids the manifest-join failure
mode that broke `SS_CHAMBER_EVENT_REPORT.py`.

The join path:
1. Scan `images/surf_scan/<CHAMBER>/` → parse `(event_token, lot, slot_id, defect_id, image_id)`
2. Load `SS_COORDINATES.csv` filtered to `PRIMARY_EQUIP == chamber`
3. Match by `(event_token → INSPECTION_TIME, SLOT_ID, DEFECT_ID)`
4. Enrich each image row with `WAFER_X_MM`, `WAFER_Y_MM`, `SIZE_D_UM`, EDX elements from coords

### Report layout

Same dark-theme frame as `INLINE_CHAMBER_EVENT_REPORT.py`:

```
┌─────────────────────────────────────────────────┐
│  Header bar: chamber · generated time           │
├─────────────────────────────────────────────────┤
│ Left panel (410 px)   │ Right panel (fill)      │
│                        │                         │
│ [wafermap SVG]         │ [LOT section header]    │
│ [coord table]          │ [image grid per defect] │
│                        │ [LOT section header]    │
│                        │ ...                     │
└─────────────────────────────────────────────────┘
```

### Wafermap: inline SVG (not matplotlib PNG)

Following the `INLINE_CHAMBER_EVENT_REPORT.py` decision documented in
`INLINE_HTML_REPORT_PATTERNS.md §7`:

- **No matplotlib** — matplotlib PNG + tight_layout on dense chambers caused 4+ minute hangs
- **Pure SVG string** — wafermap built as string concatenation in ~1 ms regardless of point count
- Embedded inline in the HTML — no separate `.png` file, no broken-image risk
- Size: 340 × 340 px (slightly larger than inline defects 188 × 188, since SS reports have
  more spatial spread and the left panel is 410 px wide)

SVG contents:
- Dark background `#1a1a1a`, wafer boundary circle at r = 150 mm
- Major grid every 50 mm, minor every 25 mm, centre cross
- Defects colored per-lot (same `WAFER_COLORS` palette)
- Imaged defects: filled circle; non-imaged: gray × marker
- Labels: fixed offset (+5 px right, –2 px up), capped at 40, showing defect ID
- Legend: per-lot color key (upper right), chamber + lot + date metadata (upper left)

### Image grid

Two canonical slots per defect: image 4 and image 8.

```
| ID | Slot 4 | Slot 8 |
```

Column widths follow the SS image aspect ratio (typically landscape). Missing slots render
as `—` placeholder only when the companion slot has an image; single-image rows are also shown.

### Grouping and ordering

- Group by **LOT7** (or `ACTUAL_LOT` for display), most recent first
- Within each LOT section: rows sorted by `(SLOT_ID, DEFECT_ID)`
- LOT section header: lot name, event date, event time, defect count
- Each lot gets its own wafermap color entry in the legend

### coord table columns

| Col | Source | Notes |
|-----|--------|-------|
| EV_W | `EVENT_WAFER` | Wafer sequence within the event run |
| SLOT | `SLOT_ID` | Carrier slot |
| ID | `DEFECT_ID` | |
| X | `WAFER_X_MM` | 1 decimal |
| Y | `WAFER_Y_MM` | 1 decimal |
| SIZE | `SIZE_D_UM` | |
| ELEM | EDX columns | Same `format_edx_label` function |

### Completeness log

Written to `{out_dir}/logs/{chamber}_completeness.log` (stable, overwritten).
Reports:
- Files scanned / parsed / matched to coords
- Defects in coords with `IMAGE_COUNT > 0` but no matching local image (likely 60-day pruned)

### `run_for_chamber` entry point

```python
def run_for_chamber(
    chamber: str,
    out_dir: str,
) -> str:
    """
    Generate SS inline HTML report for one chamber.
    Returns 'ok' on success, 'skipped' if image dir not found.
    Output: <out_dir>/<chamber>.html  (stable, overwritten each run)
            <out_dir>/logs/<chamber>_completeness.log
    """
    ...
```

### Fleet list

Reuse the inline defect `FLEET` list from `INLINE_PRODUCTION_SUBENTITY_REPORTS.py`
or define a parallel `SS_FLEET` list — both cover the same 51 chambers, but the SS
image directory may be missing for some if SS data hasn't been seeded.

Skip logic: if `images/surf_scan/<CHAMBER>/` doesn't exist, print `[SKIP]` and return
`"skipped"` (same as inline defects pattern).

### Dashboard refresh hook

`SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py` should call a dashboard refresh at the end
of a successful batch run, following the same pattern as `INLINE_PRODUCTION_SUBENTITY_REPORTS.py`:

```python
DASHBOARD_SS_MAIN = (
    Path(__file__).resolve().parents[3]
    / "AME_Dash" / "SS_Report" / "ss_report_main.py"
)
```

This will be wired once `ss_report_main.py` is built (see Part 3).

---

## Part 3 — Integration into AME_Dash/SS_Report/

Reference: `\\orshfs.intel.com\...\AME_Dash\SS_Report\SS_REPORTS_INTEGRATION.md`

### Current state

`AME_Dash/SS_Report/` exists with `SS_REPORTS_INTEGRATION.md` and a `Wafermaps/` folder.
No `ss_report_main.py`, no `launcher.py`, no `ss_report.html` yet.

### Recommended first milestone (from SS_REPORTS_INTEGRATION.md §13)

1. `SS_Report/launcher.py` (thin ScriptHost entry point)
2. `SS_Report/ss_report_main.py` (page builder, exposes `build_report()`)
3. `SS_Report/ss_report.html` (stable iframe target, generated by builder)
4. Add `ss` tab to `AME_dashboard.html`

The per-chamber inline reports (`html/SS_Inline_Reports/<CHAMBER>.html`) are the
**linked artifacts** from the dashboard page — not the dashboard page itself.
The dashboard page aggregates/indexes them, similar to how `defects_60day_report.html`
links to per-chamber `Inline_Subentity_Reports/<CHAMBER>.html`.

### Suggested dashboard section for SS

```
SS_Report/ss_report.html
├── Hero/header + refresh timestamp
├── Summary cards (fleet health, defect counts)
├── Chamber matrix / link grid → SS_Inline_Reports/<CHAMBER>.html
└── Fleet trend table or per-monitor section
```

### File linkage

```
AME_Dash/SS_Report/
    launcher.py
    ss_report_main.py
    ss_summary.py                     ← helper for chamber health block
    ss_chamber_matrix.py              ← helper for chamber link matrix
    ss_report.html                    ← stable output, iframe target
    SS_REPORTS_INTEGRATION.md

html/SS_Inline_Reports/               ← per-chamber detail pages
    AME409_PM6.html
    AME409_PM5.html
    ...
    logs/
```

---

## Implementation Sequence

1. **Fix `SS_CHAMBER_EVENT_REPORT.py`** — add `traceback.print_exc()` to the except clause
   and add `usecols` to the `pd.read_csv` call in `load_coord_metadata`

2. **Create `html/SS_INLINE_CHAMBER_REPORT.py`** — single-chamber engine with inline SVG
   wafermap, no manifest dependency, `run_for_chamber(chamber, out_dir)` entry point

3. **Create `html/SS_INLINE_PRODUCTION_SUBENTITY_REPORTS.py`** — fleet batch runner with
   `--dry-run`, `--chamber` overrides, dashboard refresh hook stub

4. **Validate** against AME409_PM6 (known-good event `260710_2002`)

5. **Dashboard scaffold** (separate task): `SS_Report/launcher.py` +
   `ss_report_main.py` + first `ss_report.html` + dashboard tab
