# Inline Defect Image HTML Report — Patterns and Design Notes

Parallel to `SS_HTML_REPORT_PATTERNS.md` for the SurfScan reports.
This note captures design decisions and resolved gotchas for the inline defect image report pipeline.

---

## 1. Report Scripts

### `html/INLINE_CHAMBER_EVENT_REPORT.py`
Single-chamber report generator (ad-hoc and core engine for production).

- **Entry point**: `run_for_chamber(chamber, out_dir, filter_lot=None)` — importable by the batch runner.
- **CLI**: `--chamber AME409_PM6`, `--lot D605312`, `--out-dir ./custom`
- **Default output**: `html/adhoc_chamber_events/`

### `html/INLINE_PRODUCTION_SUBENTITY_REPORTS.py`
Batch runner for the full fleet.

- Reads chamber list from `docs/FLEET.txt` (one SUBENTITY per line, `#` comments supported).
- Calls `run_for_chamber` for each chamber via `importlib`.
- **Production output**: `html/Inline_Subentity_Reports/`
- **Dry-run**: `--dry-run` flag lists chambers + image-dir check without generating.
- **Single test**: `--chamber AME409_PM6` overrides the fleet list.

### `docs/FLEET.txt`
Authoritative list of 51 active SUBENTITY values. Based on subdirectories currently present
in `images/defects/`. Add new chambers here when they come online; the script skips missing dirs.

---

## 2. Output Layout

```
html/Inline_Subentity_Reports/          ← production output root
    AME401_PM1.html                     ← stable filename, overwritten each run
    AME401_PM2.html
    ...
    logs/
        AME401_PM1_completeness.log
        ...

html/adhoc_chamber_events/              ← ad-hoc single-chamber output
    AME409_PM6.html
    logs/
        AME409_PM6_completeness.log
```

No `wafermaps/` subdirectory — wafermaps are inline SVG embedded in the HTML.
No timestamps in filenames — files are overwritten on each run (scheduler-safe).

---

## 3. Image Filename Convention

```
YYMMDD_HHMM_LOT7_WAFERSEQ_CLASS_LAYER_DEFECTID_IMAGEID.jpg
e.g.  260509_1851_D605312_716_BEEP_8M6CL_24_2.jpg
```

| Field      | Notes |
|------------|-------|
| `LOT7`     | 7-char lot ID, matches `LOT7` column in coordinates CSV |
| `WAFERSEQ` | Sequential wafer number within the batch (not a wafer slot or WAFER_KEY) |
| `CLASS`    | `SMP` or `BEEP` |
| `LAYER`    | `8M5CL` or `8M6CL` |
| `DEFECTID` | Defect ID integer from the inspection |
| `IMAGEID`  | Always `2` or `3` (two inspection angles) |

**No SS-style slot offset problem**: inline images use a simple `_2` / `_3` suffix with no numeric
offset ambiguity. The SS quadtree / slot-inference logic is not needed here.

---

## 4. Data Sources and Joins

| Source | Path | Key columns used |
|--------|------|-----------------|
| Defect coords | `outputs/defects/DEFECT_COORDINATES_EXTENDED.csv` | `SUBENTITY`, `LOT7`, `ACTUAL_LOT`, `DEFECT_ID`, `CLASS`, `WAFER_X_MM`, `WAFER_Y_MM`, `WAFER_KEY`, `INSPECTION_TIME`, `IMAGE_COUNT` |
| Image manifest | `outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv` | Used only for completeness log |
| Image files | `images/defects/<SUBENTITY>/` | Parsed via filename regex |

**LOT7 vs ACTUAL_LOT**: image filenames use 7-char `LOT7` format. The report displays
`ACTUAL_LOT` (full lot ID from coords) in the LOT panel headers. Matching is done via the
`LOT7` column as the join key, with `ACTUAL_LOT` resolved and surfaced for display.

**SUBENTITY = chamber folder name**: `SUBENTITY` in the coords CSV matches the subdirectory
names in `images/defects/` exactly (e.g., `AME409_PM6`). No secondary tool-to-chamber
mapping is required.

---

## 5. HTML Layout — CSS Grid

The LOT section uses a **CSS Grid** on `.lot-content` as the layout engine. No flex wrappers:

```
grid-template-columns: repeat(auto-fill, 93px)
grid-auto-rows: 93px
grid-auto-flow: row dense
gap: 2px
```

- **Wafermap**: explicit `grid-column: 1/3; grid-row: 1/3` — always anchors at the top-left.
- **Defect entries**: `grid-column: span 1; grid-row: span 2` (single-class) or
  `grid-column: span 2; grid-row: span 2` (dual-class, see §6).
- Auto-placement fills to the right of the wafermap in rows 1–2, then wraps below for row 3+.
- **Image size**: 93 × 93 px. Two images + 2 px gap + 4 px padding = 188 px = exact grid 2-cell span.

---

## 6. Dual-Class Defects (Reclassification Gotcha)

A defect can be reclassified between `SMP` and `BEEP` across different inspection events.
The image inventory may therefore contain both `SMP_2`, `SMP_3` and `BEEP_2`, `BEEP_3` images
for the same `(lot, wafer_seq, defect_id)` key.

**Handling**:
- `defect-entry` normally spans `1 col × 2 rows` (one image column, e.g., SMP only).
- When both SMP and BEEP images are present, the entry gets the CSS class
  `defect-entry defect-entry--dual` which overrides to `span 2 cols × 2 rows`.
- The 2×2 grid shows: left column = SMP (slot-2 above slot-3), right column = BEEP (slot-2 above slot-3).

This also explains why the coords CSV may produce duplicate coordinate rows for the same defect
(one for SMP class, one for BEEP class) — the wafermap deduplicates labels by `defect_id`
(`labeled_ids` set), ensuring one label per physical defect regardless of how many class rows exist.

---

## 7. Wafermap — Pure SVG (No Matplotlib)

**Critical decision**: wafermaps are generated as inline SVG strings, not PNG files.

Reason: matplotlib + `tight_layout()` + `ax.legend()` + `ax.annotate()` was O(n²) for dense
lots (26-lot chambers like AME421_PM3 caused 4+ minute hangs). The pure SVG approach builds
the wafermap as string concatenation in ~1 ms regardless of point count.

**What was dropped vs the SS reports**:
- No `_QTNode` quadtree / leader-line label collision avoidance.
- Labels are placed at a fixed offset (5 px right, 2 px up from the point) — occasional overlap
  is acceptable at this scale.
- Capped at 40 labeled points per wafermap to keep SVG size bounded.

**Wafermap SVG contents**:
- Dark background (`#1a1a1a`), 188 × 188 px, inline in HTML.
- Major grid every 50 mm, centre cross, wafer boundary circle at r = 150 mm.
- SMP defects → filled circle (`<circle>`); BEEP defects → X marker (two `<line>` elements).
- Imaged defects: per-wafer color from `WAFER_COLORS` palette. Non-imaged: gray `#6E7E8E`.
- Per-wafer color legend (upper-right), burn-in metadata (upper-left): chamber, `ACTUAL_LOT`, inspection date range.

**Per-wafer color matching**: `WAFER_KEY` values from the coords CSV are matched to `wafer_seq`
values from image filenames via defect-ID overlap (majority-vote). Falls back to `W1`, `W2`... labels if ambiguous.

---

## 8. Image Grid Convention

Four columns per defect entry (when dual-class) or two columns (single-class):

| Column | Content |
|--------|---------|
| SMP · 2 | First SMP image slot |
| SMP · 3 | Second SMP image slot |
| BEEP · 2 | First BEEP image slot (only if reclassified) |
| BEEP · 3 | Second BEEP image slot (only if reclassified) |

Within each column, images stack vertically (slot-2 above slot-3). Absent images render as `—`
placeholder only when the companion slot in that column also has an image; empty columns are
suppressed entirely.

---

## 9. Completeness Log

Written to `{out_dir}/logs/{chamber}_completeness.log` on every run (stable filename, overwritten).

Reports:
- Inventory scan stats (scanned / parsed / skipped).
- Cross-reference: defects in coords with `IMAGE_COUNT > 0` that have no matching image file
  in the current library. Most gaps are expected (60-day pruning policy removes older images).
  Only entries within the current 60-day window with no image are genuine concerns.

---

## 10. Known Differences from SS Reports

| Aspect | SS Reports | Inline Reports |
|--------|-----------|----------------|
| Wafermap renderer | matplotlib PNG (base64) | Pure SVG string |
| Image slots | [8, 2, 3, 4] with offset inference | Always [2, 3] per class, no offset |
| EDX / element data | EDX columns from manifest | Not applicable |
| Manifest join | Multi-key normalize + fallback | Filename regex only |
| Event token | `yymmdd_hhmm` in filename | Same — but used for grouping, not filtering |
| Label collision | Quadtree + `ax.annotate` | Fixed-offset `<text>`, capped at 40 |
| Output | Timestamped files, `wafermaps/` folder | Stable overwrite, SVG inline |

---

*Document created: 2026-07-09*
*Reference: `html/SS_HTML_REPORT_PATTERNS.md`, `PIPELINE_DESIGN.md`*
