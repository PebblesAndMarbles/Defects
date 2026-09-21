"""Build a static, filterable HTML report for enriched VLM production data.

The report is intentionally static: it renders a responsive image-density grid at
the top, then a defect-by-defect detail section below. Client-side JavaScript
handles filtering and simple cohort counts so the page remains usable directly
from file:// without any backend service.

Inputs are expected to come from tools/enrich_production_with_vlm_attributes.py.
The builder accepts an enriched CSV and optionally the BEEP ground-truth CSV so
the report can show labeled/unlabeled cohort counts when available.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


REPORTING_DIR = Path(__file__).resolve().parent
ALLOY_CLASS_DIR = REPORTING_DIR.parent
BE_ROOT = ALLOY_CLASS_DIR.parents[1]

DEFAULT_INPUT_CSV = ALLOY_CLASS_DIR / "outputs" / "production_vlm_enrichment" / "production_vlm_enriched.csv"
DEFAULT_GROUND_TRUTH_CSV = ALLOY_CLASS_DIR / "outputs" / "beep_evidence" / "beep_evidence_ground_truth.csv"
DEFAULT_OUTPUT_HTML = ALLOY_CLASS_DIR / "outputs" / "production_vlm_enrichment" / "vlm_attributes_filterable_report.html"


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_html_with_rev_fallback(html_doc: str, output_html: Path) -> Path:
    try:
        output_html.write_text(html_doc, encoding="utf-8")
        return output_html
    except PermissionError:
        rev = 2
        while True:
            candidate = output_html.with_name(f"{output_html.stem}_rev{rev}{output_html.suffix}")
            try:
                candidate.write_text(html_doc, encoding="utf-8")
                return candidate
            except PermissionError:
                rev += 1


def _normalize_join_value(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _inspection_time_norm(value: object) -> str:
    insp = pd.to_datetime(value, errors="coerce")
    return insp.strftime("%Y%m%d_%H%M%S") if pd.notna(insp) else "UNKNOWN"


def _join_key(wafer_key: object, inspection_time: object, defect_id: object) -> str:
    return (
        f"{_normalize_join_value(wafer_key)}_"
        f"{_inspection_time_norm(inspection_time)}_"
        f"{_normalize_join_value(defect_id)}"
    )


def _truth_bucket(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    return "SMALL_PARTICLE" if text in ("SMALL_PARTICLE", "PARTICLE") else "BEEP"


def _load_ground_truth_lookup(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    rows = _load_csv_rows(path)
    rows = [row for row in rows if str(row.get("tranche_id") or "")]
    rows.sort(key=lambda row: (str(row.get("pair_key") or ""), str(row.get("submitted_at_utc") or "")))

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        pair_key = str(row.get("pair_key") or "").strip()
        if not pair_key:
            continue
        existing = deduped.get(pair_key)
        if existing is None or str(row.get("submitted_at_utc") or "") >= str(existing.get("submitted_at_utc") or ""):
            deduped[pair_key] = row
    return deduped


def _manifest_image_columns(row: dict[str, Any]) -> tuple[str, str]:
    bright = (
        row.get("bright_local_image_file")
        or row.get("bright_image_file")
        or row.get("bright_path")
        or row.get("brightfield_image_file")
        or row.get("brightfield_path")
        or ""
    )
    dark = (
        row.get("dark_local_image_file")
        or row.get("dark_image_file")
        or row.get("dark_path")
        or row.get("darkfield_image_file")
        or row.get("darkfield_path")
        or ""
    )
    return str(bright).strip(), str(dark).strip()


def _img_tag(image_path_str: str, report_dir: Path, label: str) -> str:
    if not image_path_str:
        return f'<div class="missing-img">no {html.escape(label)} image</div>'
    image_path = Path(image_path_str)
    if not image_path.exists():
        return f'<div class="missing-img">missing: {html.escape(image_path.name or image_path_str)}</div>'
    try:
        rel = os.path.relpath(str(image_path.resolve()), str(report_dir)).replace("\\", "/")
        src = html.escape(rel)
    except ValueError:
        src = html.escape(image_path.resolve().as_uri())
    return f'<img src="{src}" alt="{html.escape(label)}" loading="lazy">'


def _cell_value(row: dict[str, Any], *keys: str) -> str:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(str(key).lower(), "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _detail_fields() -> list[str]:
    return [
        "coarse_shape",
        "shape_elongated",
        "shape_rounded_corners",
        "shape_jagged",
        "shape_concave",
        "shape_flake",
    "coarse_texture",
        "texture_interior_layer",
        "texture_interior_line",
        "texture_interior_fracture",
        "texture_scraggly",
        "defect_count",
        "size_percent_of_image",
        "location_relative",
        "focus_quality",
        "confidence",
        "review_required",
        "truth_label",
        "truth_is_beep",
        "truth_alignment_state",
        "current_class",
        "current_reclass",
        "vlm_prompt_version",
        "wafer_key",
        "inspection_time",
        "defect_id",
        "lot",
        "layer",
        "query_site",
        "finebin",
        "size_x",
        "size_y",
        "size_d",
        "area",
        "enrichment_status",
    ]


def _structured_attribute_pairs(structured: dict[str, Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    left_keys = [
        "coarse_shape",
        "shape_elongated",
        "shape_rounded_corners",
        "shape_jagged",
        "shape_concave",
        "shape_flake",
        "coarse_texture",
        "texture_interior_layer",
        "texture_interior_line",
        "texture_interior_fracture",
        "texture_scraggly",
        "defect_count",
        "size_percent_of_image",
        "location_relative",
        "focus_quality",
        "confidence",
        "review_required",
    ]
    right_keys = [
        "query_site",
        "inspection_time",
        "subentity",
        "lot",
        "layer",
        "wafer_id",
        "wafer_key",
        "defect_id",
        "finebin",
        "size_x",
        "size_y",
        "size_d",
        "area",
    ]

    def _paired_rows(keys: list[str]) -> list[tuple[str, str]]:
        return [(key, html.escape(str(structured.get(key, "")))) for key in keys]

    return _paired_rows(left_keys), _paired_rows(right_keys)


def _render_four_column_table(left_pairs: list[tuple[str, str]], right_pairs: list[tuple[str, str]]) -> str:
    row_count = max(len(left_pairs), len(right_pairs))
    rows: list[str] = []
    for index in range(row_count):
        left_key, left_value = left_pairs[index] if index < len(left_pairs) else ("", "")
        right_key, right_value = right_pairs[index] if index < len(right_pairs) else ("", "")
        rows.append(
            "<tr>"
            f"<td><b>{html.escape(left_key)}</b></td><td>{left_value}</td>"
            f"<td><b>{html.escape(right_key)}</b></td><td>{right_value}</td>"
            "</tr>"
        )
    return (
        '<div style="overflow-x:auto;">'
        '<table class="detail-table" style="width:max-content; table-layout:auto; white-space:nowrap;">'
        f'{"".join(rows)}'
        '</table>'
        '</div>'
    )


def _row_dom_id(case_id: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in case_id) or "case"


def _case_id_from_row(row: dict[str, Any]) -> str:
    case_id = _cell_value(row, "case_id")
    if case_id:
        return case_id
    return _join_key(row.get("WAFER_KEY") or row.get("wafer_key"), row.get("INSPECTION_TIME") or row.get("inspection_time"), row.get("DEFECT_ID") or row.get("defect_id"))


def _truth_from_row(row: dict[str, Any], truth_lookup: dict[str, dict[str, str]]) -> tuple[str, str]:
    pair_key = _cell_value(row, "pair_key")
    if not pair_key:
        pair_key = _join_key(row.get("WAFER_KEY") or row.get("wafer_key"), row.get("INSPECTION_TIME") or row.get("inspection_time"), row.get("DEFECT_ID") or row.get("defect_id"))
    gt = truth_lookup.get(pair_key)
    truth_label = str(gt.get("label") or "") if gt else ""
    truth_is_beep = "true" if _truth_bucket(truth_label) == "BEEP" else ("false" if truth_label else "")
    return truth_label, truth_is_beep


def _cohort_key(row: dict[str, Any]) -> str:
    parts = []
    for key in ("coarse_shape", "coarse_texture", "shape_jagged", "shape_flake", "defect_count", "truth_is_beep"):
        value = str(row.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    return " | ".join(parts) if parts else "all"


def _render_filter_controls() -> str:
    return """
  <div class="box controls-box">
    <div class="controls-row">
      <label>Search <input id="filter-search" type="text" placeholder="case_id, wafer, lot, description"></label>
      <label><input id="show-labeled-only" type="checkbox"> labeled only</label>
      <label><input id="show-unlabeled-only" type="checkbox"> unlabeled only</label>
      <label><input id="show-beep-only" type="checkbox"> BEEP truth only</label>
      <label><input id="show-particle-only" type="checkbox"> particle truth only</label>
    </div>
    <div class="controls-grid">
      <label><input type="checkbox" class="filter-flag" data-field="shape_jagged"> jagged</label>
      <label><input type="checkbox" class="filter-flag" data-field="shape_flake"> flake</label>
      <label><input type="checkbox" class="filter-flag" data-field="shape_concave"> concave</label>
      <label><input type="checkbox" class="filter-flag" data-field="shape_rounded_corners"> rounded corners</label>
      <label><input type="checkbox" class="filter-flag" data-field="shape_elongated"> elongated</label>
      <label><input type="checkbox" class="filter-flag" data-field="texture_scraggly"> scraggly</label>
      <label><input type="checkbox" class="filter-flag" data-field="texture_interior_layer"> interior layer</label>
      <label><input type="checkbox" class="filter-flag" data-field="texture_interior_line"> interior line</label>
      <label><input type="checkbox" class="filter-flag" data-field="texture_interior_fracture"> interior fracture</label>
      <label><input type="checkbox" class="filter-flag" data-field="review_required"> review required</label>
      <label><input type="checkbox" class="filter-flag" data-field="truth_is_beep"> truth BEEP</label>
      <label><input type="checkbox" class="filter-flag" data-field="truth_is_particle"> truth particle</label>
    </div>
    <div class="controls-row">
      <label>Min defect count <input id="min-defect-count" type="number" min="0" step="1" placeholder="0"></label>
      <label>Max defect count <input id="max-defect-count" type="number" min="0" step="1" placeholder="any"></label>
      <label>Start date <input id="start-date" type="date"></label>
      <label>End date <input id="end-date" type="date"></label>
      <button id="clear-filters" type="button">Clear filters</button>
    </div>
  </div>
"""


def _render_summary(summary: dict[str, Any]) -> str:
    return f'<div class="box"><pre>{html.escape(json.dumps(summary, indent=2))}</pre></div>'


def _render_cohort_table(rows: list[dict[str, Any]]) -> str:
    counts: Counter[tuple[str, str]] = Counter()
    totals: Counter[str] = Counter()
    for row in rows:
        key = _cohort_key(row)
        truth = str(row.get("truth_is_beep") or "") or "unknown"
        counts[(key, truth)] += 1
        totals[key] += 1

    body = []
    for cohort in sorted(totals.keys()):
        total = totals[cohort]
        beep = counts[(cohort, "true")]
        particle = counts[(cohort, "false")]
        unlabeled = counts[(cohort, "unknown")]
        body.append(
            "<tr>"
            f"<td>{html.escape(cohort)}</td>"
            f"<td>{total}</td>"
            f"<td>{beep}</td>"
            f"<td>{particle}</td>"
            f"<td>{unlabeled}</td>"
            "</tr>"
        )

    return (
        '<div class="box"><b>Cohort counts</b>'
        '<table class="cohort-table">'
        '<thead><tr><th>Cohort</th><th>Total</th><th>BEEP truth</th><th>Particle truth</th><th>Unlabeled</th></tr></thead>'
        f'<tbody>{"".join(body) if body else "<tr><td colspan=5>No cohorts.</td></tr>"}</tbody>'
        '</table></div>'
    )


def _build_detail_card(row: dict[str, Any], report_dir: Path) -> str:
    case_id = _case_id_from_row(row)
    dom_id = _row_dom_id(case_id)
    bright, dark = _manifest_image_columns(row)
    bright_html = _img_tag(bright, report_dir, "brightfield")
    dark_html = _img_tag(dark, report_dir, "darkfield")
    left_pairs, right_pairs = _structured_attribute_pairs(row)
    detail_html = _render_four_column_table(left_pairs, right_pairs)
    description = html.escape(str(row.get("description") or row.get("model_description") or ""))
    title_text = f"{html.escape(case_id)} description: {description}" if description else html.escape(case_id)
    return (
        f'<table class="case-card" id="case-{dom_id}" data-case-id="{html.escape(case_id)}" '
        f'data-dom-id="{html.escape(dom_id)}" '
        f'data-row-text="{html.escape(" ".join(str(row.get(k, "") or "") for k in ("case_id", "wafer_key", "lot", "layer", "description", "coarse_shape", "coarse_texture")))}" '
        f'data-join-key="{html.escape(str(row.get("join_key") or ""))}" '
        f'data-truth-is-beep="{html.escape(str(row.get("truth_is_beep") or ""))}" '
        f'data-truth-label="{html.escape(str(row.get("truth_label") or ""))}" '
        f'data-defect-count="{html.escape(str(row.get("defect_count") or ""))}" '
        f'data-inspection-time="{html.escape(str(row.get("inspection_time") or row.get("INSPECTION_TIME") or ""))}">'
        '<tbody>'
        f'<tr class="case-title-row"><td colspan="2"><div class="case-title">{title_text}</div></td></tr>'
        '<tr class="case-detail-row">'
        f'<td class="images-panel">{bright_html}{dark_html}</td>'
        f'<td class="calls-panel"><table class="detail-table">{detail_html}</table></td>'
        '</tr>'
        '</tbody>'
        '</table>'
    )


def _client_script(rows: list[dict[str, Any]]) -> str:
    payload = []
    for row in rows:
        payload.append({
            "case_id": _case_id_from_row(row),
            "wafer_key": str(row.get("wafer_key") or row.get("WAFER_KEY") or ""),
            "inspection_time": str(row.get("inspection_time") or row.get("INSPECTION_TIME") or ""),
            "defect_id": str(row.get("defect_id") or row.get("DEFECT_ID") or ""),
            "lot": str(row.get("lot") or row.get("LOT") or ""),
            "layer": str(row.get("layer") or row.get("LAYER") or ""),
            "truth_is_beep": str(row.get("truth_is_beep") or ""),
            "truth_label": str(row.get("truth_label") or ""),
            "defect_count": str(row.get("defect_count") or ""),
            "coarse_shape": str(row.get("coarse_shape") or ""),
            "coarse_texture": str(row.get("coarse_texture") or ""),
            "shape_jagged": str(row.get("shape_jagged") or ""),
            "shape_flake": str(row.get("shape_flake") or ""),
            "shape_concave": str(row.get("shape_concave") or ""),
            "shape_rounded_corners": str(row.get("shape_rounded_corners") or ""),
            "shape_elongated": str(row.get("shape_elongated") or ""),
            "texture_scraggly": str(row.get("texture_scraggly") or ""),
            "texture_interior_layer": str(row.get("texture_interior_layer") or ""),
            "texture_interior_line": str(row.get("texture_interior_line") or ""),
            "texture_interior_fracture": str(row.get("texture_interior_fracture") or ""),
            "review_required": str(row.get("review_required") or ""),
            "confidence": str(row.get("confidence") or ""),
            "join_key": str(row.get("join_key") or ""),
            "inspection_date": str(row.get("inspection_date") or row.get("INSPECTION_DATE") or ""),
            "search_text": " ".join(str(row.get(k) or "") for k in (
                "case_id", "wafer_key", "lot", "layer", "description", "coarse_shape", "coarse_texture",
                "shape_jagged", "shape_flake", "shape_concave", "shape_rounded_corners", "shape_elongated",
                "texture_scraggly", "texture_interior_layer", "texture_interior_line", "texture_interior_fracture",
                "truth_label", "truth_is_beep", "defect_count", "confidence", "review_required",
            )),
        })

    return f"""
  <script>
    const ROWS = {json.dumps(payload)};
    const FIELDS = ["shape_jagged", "shape_flake", "shape_concave", "shape_rounded_corners", "shape_elongated", "texture_scraggly", "texture_interior_layer", "texture_interior_line", "texture_interior_fracture", "review_required", "truth_is_beep", "truth_is_particle"];

    function storageKey() {{
      return `vlm_report_draft_notes_${{location.pathname.replace(/[^a-z0-9]+/gi, '_')}}`;
    }}

    function loadNotes() {{
      try {{ return JSON.parse(localStorage.getItem(storageKey()) || '{{}}'); }} catch (e) {{ return {{}}; }}
    }}

    function getElementValue(id) {{
      const el = document.getElementById(id);
      if (!el) return '';
      if (el.type === 'checkbox') return el.checked ? '1' : '';
      return el.value || '';
    }}

    function normalizeText(text) {{
      return (text || '').toString().toLowerCase();
    }}

    function rowMatches(row) {{
      const search = normalizeText(getElementValue('filter-search'));
      if (search && !normalizeText(row.search_text).includes(search)) return false;

      const showLabeledOnly = document.getElementById('show-labeled-only')?.checked;
      const showUnlabeledOnly = document.getElementById('show-unlabeled-only')?.checked;
      const truthIsBeep = (row.truth_is_beep || '').toLowerCase();
      const isLabeled = truthIsBeep === 'true' || truthIsBeep === 'false';
      if (showLabeledOnly && !isLabeled) return false;
      if (showUnlabeledOnly && isLabeled) return false;

      const showBeepOnly = document.getElementById('show-beep-only')?.checked;
      const showParticleOnly = document.getElementById('show-particle-only')?.checked;
      if (showBeepOnly && truthIsBeep !== 'true') return false;
      if (showParticleOnly && truthIsBeep !== 'false') return false;

      const minDefect = document.getElementById('min-defect-count')?.value;
      const maxDefect = document.getElementById('max-defect-count')?.value;
      const defectCount = parseFloat(row.defect_count || '');
      if (minDefect !== '' && !Number.isNaN(parseFloat(minDefect)) && !(defectCount >= parseFloat(minDefect))) return false;
      if (maxDefect !== '' && !Number.isNaN(parseFloat(maxDefect)) && !(defectCount <= parseFloat(maxDefect))) return false;

      const startDate = document.getElementById('start-date')?.value;
      const endDate = document.getElementById('end-date')?.value;
      const rowDate = (row.inspection_date || row.inspection_time || '').toString().slice(0, 10);
      if (startDate && rowDate && rowDate < startDate) return false;
      if (endDate && rowDate && rowDate > endDate) return false;

      for (const field of FIELDS) {{
        const checkbox = document.querySelector(`.filter-flag[data-field="${{field}}"]`);
        if (!checkbox || !checkbox.checked) continue;
        const value = (row[field] || '').toString().toLowerCase();
        if (!['1', 'true', 'yes'].includes(value)) return false;
      }}

      const truthParticleFlag = document.querySelector('.filter-flag[data-field="truth_is_particle"]');
      if (truthParticleFlag && truthParticleFlag.checked) {{
        if (truthIsBeep !== 'false') return false;
      }}

      return true;
    }}

    function updateVisibility() {{
      let visible = 0;
      document.querySelectorAll('.case-card').forEach(card => {{
        const caseId = card.dataset.caseId || '';
        const row = ROWS.find(r => r.case_id === caseId);
        const keep = row ? rowMatches(row) : true;
        card.style.display = keep ? '' : 'none';
        if (keep) visible += 1;
      }});
      document.getElementById('visible-count').textContent = String(visible);
      document.getElementById('total-count').textContent = String(ROWS.length);
    }}

    function updateCohorts() {{
      const tableBody = document.getElementById('cohort-body');
      if (!tableBody) return;
      const groups = new Map();
      for (const row of ROWS) {{
        if (!rowMatches(row)) continue;
        const cohort = [
          ['coarse_shape', row.coarse_shape],
          ['coarse_texture', row.coarse_texture],
          ['shape_jagged', row.shape_jagged],
          ['shape_flake', row.shape_flake],
          ['defect_count', row.defect_count],
          ['truth_is_beep', row.truth_is_beep],
        ].map(([k, v]) => `${{k}}=${{v || ''}}`).filter(text => !text.endsWith('=')).join(' | ') || 'all';
        const truthKey = row.truth_is_beep || 'unknown';
        const bucket = groups.get(cohort) || {{ total: 0, beep: 0, particle: 0, unlabeled: 0 }};
        bucket.total += 1;
        if (truthKey === 'true') bucket.beep += 1;
        else if (truthKey === 'false') bucket.particle += 1;
        else bucket.unlabeled += 1;
        groups.set(cohort, bucket);
      }}

      const entries = Array.from(groups.entries()).sort((a, b) => b[1].total - a[1].total || a[0].localeCompare(b[0]));
      tableBody.innerHTML = entries.length ? '' : '<tr><td colspan="5">No cohorts after filtering.</td></tr>';
      for (const [cohort, bucket] of entries) {{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${{cohort}}</td><td>${{bucket.total}}</td><td>${{bucket.beep}}</td><td>${{bucket.particle}}</td><td>${{bucket.unlabeled}}</td>`;
        tableBody.appendChild(tr);
      }}
    }}

    function wireEvents() {{
      const controls = [
        '#filter-search', '#show-labeled-only', '#show-unlabeled-only', '#show-beep-only', '#show-particle-only',
        '#min-defect-count', '#max-defect-count', '#start-date', '#end-date', '#clear-filters',
      ];
      controls.forEach(selector => {{
        const el = document.querySelector(selector);
        if (!el) return;
        if (selector === '#clear-filters') {{
          el.addEventListener('click', () => {{
            document.querySelectorAll('input').forEach(input => {{
              if (input.type === 'checkbox') input.checked = false;
              if (input.type === 'text' || input.type === 'number' || input.type === 'date') input.value = '';
            }});
            updateVisibility();
            updateCohorts();
          }});
        }} else {{
          el.addEventListener('input', () => {{ updateVisibility(); updateCohorts(); }});
          el.addEventListener('change', () => {{ updateVisibility(); updateCohorts(); }});
        }}
      }});
      document.querySelectorAll('.filter-flag').forEach(el => el.addEventListener('change', () => {{ updateVisibility(); updateCohorts(); }}));
    }}

    wireEvents();
    updateVisibility();
    updateCohorts();
  </script>
"""


def build_report(input_csv: Path, output_html: Path, ground_truth_csv: Path | None = None) -> tuple[dict[str, Any], Path]:
    df = pd.read_csv(input_csv, low_memory=False, dtype=str)
    rows = df.fillna("").to_dict(orient="records")
    report_dir = output_html.resolve().parent
    truth_lookup = _load_ground_truth_lookup(ground_truth_csv) if ground_truth_csv else {}

    prepared_rows: list[dict[str, Any]] = []
    for row in rows:
        prepared = dict(row)
        truth_label, truth_is_beep = _truth_from_row(prepared, truth_lookup)
        prepared["truth_label"] = prepared.get("truth_label") or truth_label
        prepared["truth_is_beep"] = prepared.get("truth_is_beep") or truth_is_beep
        prepared["case_id"] = _case_id_from_row(prepared)
        prepared["join_key"] = prepared.get("join_key") or _join_key(prepared.get("WAFER_KEY") or prepared.get("wafer_key"), prepared.get("INSPECTION_TIME") or prepared.get("inspection_time"), prepared.get("DEFECT_ID") or prepared.get("defect_id"))
        prepared["inspection_date"] = str(prepared.get("inspection_time") or prepared.get("INSPECTION_TIME") or "")[:10]
        if not prepared.get("coarse_shape") and prepared.get("description"):
            prepared["coarse_shape"] = prepared.get("description")
        prepared_rows.append(prepared)

    summary = {
        "total_cases": len(prepared_rows),
        "labeled_cases": sum(1 for row in prepared_rows if str(row.get("truth_is_beep") or "") in {"true", "false"}),
        "truth_beep_cases": sum(1 for row in prepared_rows if str(row.get("truth_is_beep") or "") == "true"),
        "truth_particle_cases": sum(1 for row in prepared_rows if str(row.get("truth_is_beep") or "") == "false"),
        "truth_unlabeled_cases": sum(1 for row in prepared_rows if not str(row.get("truth_is_beep") or "")),
        "source_csv": str(input_csv),
        "ground_truth_csv": str(ground_truth_csv) if ground_truth_csv else "",
    }

    cards_html = "\n".join(_build_detail_card(row, report_dir) for row in prepared_rows)
    cohort_html = _render_cohort_table(prepared_rows)
    html_doc = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>VLM Attributes Filterable Report</title>
  <style>
    body {{ margin: 22px; background: #f8f9fb; color: #1f2937; font-family: Segoe UI, Arial, sans-serif; }}
    .page-body {{ padding: 22px; }}
    .box {{ background: white; border: 1px solid #d1d5db; border-radius: 0; padding: 10px; margin-bottom: 14px; }}
    .controls-box {{ background: white; backdrop-filter: none; }}
    h1 {{ margin-bottom: 6px; color: #1f2937; }}
    .summary-stats {{ font-size: 13px; color: #4b5563; margin-top: 4px; }}
    .controls-row label, .controls-grid label {{ font-size: 13px; color: #374151; }}
    .controls-row input[type="text"], .controls-row input[type="number"], .controls-row input[type="date"] {{ background: white; color: #1f2937; border: 1px solid #d1d5db; border-radius: 4px; padding: 4px 6px; min-width: 180px; }}
    .controls-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 4px 10px; margin-bottom: 8px; }}
    .controls-row {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px; }}
    .case-card {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; background: white; border: 1px solid #d1d5db; border-radius: 0; overflow: hidden; }}
    .case-title-row td {{ background: #e5eefb; padding: 8px 10px 4px; border: 0; }}
    .case-title {{ font-size: 15px; font-weight: 400; color: #1f2937; margin: 0; text-align: left; }}
    .case-detail-row td {{ vertical-align: top; background: white; padding: 8px 10px 10px; border: 0; }}
    .case-detail-row {{ border-top: 1px solid #d1d5db; }}
    .hero-wall {{ display: grid; grid-template-columns: repeat(auto-fill, 186px); grid-auto-rows: auto; gap: 4px; align-items: start; }}
    .hero-cell {{ width: 186px; overflow: hidden; }}
    .hero-cell img {{ width: 186px; height: auto; max-width: none; display: block; background: #f8f9fb; border: 1px solid #bbb; border-radius: 0; }}
    .hero-cell .missing-img {{ width: 186px; min-height: 140px; border: 0; border-radius: 0; background: #f8f9fb; }}
    .images-panel {{ width: 186px; min-width: 186px; padding-right: 10px; }}
    .images-panel img {{ width: 186px; height: auto; display: block; background: #f8f9fb; border: 1px solid #bbb; border-radius: 0; margin-bottom: 2px; }}
    .images-panel .missing-img {{ width: 186px; min-height: 140px; border-radius: 0; display: flex; align-items: center; justify-content: center; color: #9ca3af; background: #f3f4f6; border: 1px solid #d1d5db; font-size: 11px; text-align: center; padding: 4px; box-sizing: border-box; margin-bottom: 2px; }}
    .calls-panel {{ width: auto; min-width: 0; border-left: 1px solid #d1d5db; padding-left: 10px; }}
    .case-subtitle {{ color: #4b5563; font-size: 12px; margin-bottom: 6px; }}
    .case-note {{ color: #4b5563; font-size: 13px; margin-bottom: 8px; white-space: pre-wrap; word-break: break-word; }}
    .detail-table, .cohort-table {{ width: 100%; border-collapse: collapse; }}
    .detail-table td, .cohort-table td, .cohort-table th {{ border: 1px solid #d1d5db; padding: 6px 8px; vertical-align: top; font-size: 12px; background: white; color: #1f2937; }}
    .detail-table td:first-child {{ width: 220px; background: white; color: #1f2937; font-weight: 600; }}
    .cohort-table th {{ background: #e5eefb; text-align: left; }}
        .case-card[style*="display: none"] {{ display: none !important; }}
        pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; }}
        .json-box pre {{ font-family: Segoe UI, Arial, sans-serif; color: #1f2937; }}
  </style>
</head>
<body>
  <div class="page-body">
    <h1 style="font-family: Segoe UI, Arial, sans-serif; margin-bottom: 6px; color: #1f2937;">VLM Attributes Filterable Report</h1>
    <div class="summary-stats">Visible <span id="visible-count">0</span> of <span id="total-count">0</span> defects</div>
    <div class="box json-box"><pre>{html.escape(json.dumps(summary, indent=2))}</pre></div>
    {_render_filter_controls()}
    <div class="hero-wall">
      {''.join(
          f'<div class="hero-cell">{_img_tag(_manifest_image_columns(row)[0], report_dir, "brightfield")}{_img_tag(_manifest_image_columns(row)[1], report_dir, "darkfield")}</div>'
          for row in prepared_rows[:80]
      )}
    </div>
    {cohort_html}
    <div class="box"><b>Detail section</b><div style="color:#9fb0bd;font-size:12px;">Scroll below the image grid for per-defect attributes and provenance.</div></div>
    <div id="case-list">{cards_html}</div>
  </div>
  {_client_script(prepared_rows)}
</body>
</html>
"""

    written_path = _write_html_with_rev_fallback(html_doc, output_html)
    return summary, written_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a static filterable HTML report for enriched VLM production data")
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT_CSV), help="Enriched CSV from tools/enrich_production_with_vlm_attributes.py")
    parser.add_argument("--output-html", default=str(DEFAULT_OUTPUT_HTML), help="Output HTML report path")
    parser.add_argument("--ground-truth-csv", default=str(DEFAULT_GROUND_TRUTH_CSV), help="Optional BEEP ground-truth CSV for labeled/unlabeled cohort counts")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv)
    output_html = Path(args.output_html)
    ground_truth_csv = Path(args.ground_truth_csv) if args.ground_truth_csv else None

    summary, written_path = build_report(
        input_csv=input_csv,
        output_html=output_html,
        ground_truth_csv=ground_truth_csv,
    )
    print(json.dumps(summary, indent=2))
    print(str(written_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())