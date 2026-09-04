"""
Build a rapid keyboard-driven labeling HTML report from a tranche manifest CSV
(tools/build_beep_labeling_tranche.py output).

Per case: bright+dark images side by side plus a two-option
SMALL_PARTICLE/BEEP radio group. Each case row is the sole Tab stop (radios
are tabindex=-1) so Tab moves case-to-case; while a row has focus, ArrowLeft
selects SMALL_PARTICLE, ArrowRight selects BEEP, and selecting auto-advances
focus to the next row. Selections are cached in localStorage (survive
reload/close) and posted as one batch to the beep_labeling_portal backend
(reporting/beep_labeling_portal/) via a single "Submit All" button.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path
from typing import Any


def _load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _dom_safe_id(raw: str) -> str:
    """Sanitize a pair_key for use as an HTML id/JS string suffix."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw) or "case"


def _img_tag(image_path_str: str, report_dir: Path, label: str) -> str:
    if not image_path_str:
        return f'<div class="missing-img">no {label} image</div>'
    image_path = Path(image_path_str)
    if not image_path.exists():
        return f'<div class="missing-img">missing: {html.escape(image_path.name or image_path_str)}</div>'
    try:
        rel = os.path.relpath(str(image_path.resolve()), str(report_dir)).replace("\\", "/")
        src = html.escape(rel)
    except ValueError:
        # Cross-mount (e.g. C:\ vs UNC): fall back to absolute file URI
        src = html.escape(image_path.resolve().as_uri())
    return (
        f'<img src="{src}" alt="{html.escape(label)}" '
        f'style="max-width:100%;display:block;border:1px solid #bbb;">'
    )


def _write_html_with_rev_fallback(html_doc: str, output_html: Path) -> Path:
    """Write to output_html; fall back to _revN on PermissionError (locked by an open browser tab)."""
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


_CSS = """
    body { font-family: Segoe UI, Arial, sans-serif; margin: 22px; background: #f8f9fb; color: #1f2937; }
    h1 { margin-bottom: 4px; }
    .box { background: white; border: 1px solid #d1d5db; padding: 10px; margin-bottom: 14px; }
    #progress-bar { position: sticky; top: 0; z-index: 10; }
    .case-row {
        display: flex; align-items: flex-start; gap: 14px; background: white;
        border: 1px solid #d1d5db; border-radius: 6px; padding: 10px; margin-bottom: 8px;
        outline: none;
    }
    .case-row:focus { border-color: #1d4ed8; box-shadow: 0 0 0 2px #bfdbfe; }
    .case-row.labeled-SMALL_PARTICLE { background: #eff6ff; }
    .case-row.labeled-BEEP { background: #fef2f2; }
    .case-images { display: flex; gap: 8px; flex: 0 0 auto; }
    .case-images > div { width: 220px; }
    .missing-img { width: 220px; height: 120px; display: flex; align-items: center;
        justify-content: center; background: #f3f4f6; color: #9ca3af; font-size: 12px; text-align: center; }
    .case-meta { font-size: 12px; color: #4b5563; flex: 1 1 auto; min-width: 0; }
    .case-choice { flex: 0 0 260px; }
    .case-choice label { display: block; font-size: 14px; margin-bottom: 4px; cursor: pointer; }
    .case-choice .hint { color: #9ca3af; font-size: 11px; }
    .case-status { font-weight: 600; font-size: 12px; margin-top: 4px; }
"""

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BEEP Evidence Labeling -- {tranche_id}</title>
  <style>{css}</style>
</head>
<body>
  <h1>BEEP Evidence Labeling -- {tranche_id}</h1>
  <div class="box" id="progress-bar">
    <b>Progress:</b> <span id="progress-count">0</span> / {total_cases} labeled
    &nbsp;|&nbsp; Tab = next/prev case, Left = SMALL_PARTICLE, Right = BEEP (auto-advances)
    &nbsp;|&nbsp; <button id="submit-btn" onclick="submitAll()">Submit All</button>
    &nbsp;<span id="submit-status" style="color:#16a34a;"></span>
    <div id="backend-status" style="margin-top:6px;font-size:12px;">Checking backend at {api_base}...</div>
  </div>
  <div id="cases">
    {case_rows}
  </div>
  <script>{script}</script>
</body>
</html>
"""


def _case_row_html(case: dict[str, Any], report_dir: Path) -> str:
    pair_key = case.get("pair_key", "")
    dom_id = _dom_safe_id(pair_key)
    bright = _img_tag(case.get("bright_image_path", ""), report_dir, "bright")
    dark = _img_tag(case.get("dark_image_path", ""), report_dir, "dark")
    meta_fields = ["wafer_key", "inspection_time", "lot", "defect_id", "layer", "subentity", "factory_class"]
    meta_html = "<br>".join(
        f"<b>{f}:</b> {html.escape(str(case.get(f, '')))}" for f in meta_fields if case.get(f, "") != ""
    )
    return f"""
  <div class="case-row" tabindex="0" id="row-{dom_id}" data-pair-key="{html.escape(str(pair_key))}"
       data-wafer-key="{html.escape(str(case.get('wafer_key', '')))}"
       data-inspection-time="{html.escape(str(case.get('inspection_time', '')))}"
       data-defect-id="{html.escape(str(case.get('defect_id', '')))}"
       data-layer="{html.escape(str(case.get('layer', '')))}">
    <div class="case-images">
      <div>{bright}<div style="text-align:center;font-size:11px;color:#6b7280;">bright</div></div>
      <div>{dark}<div style="text-align:center;font-size:11px;color:#6b7280;">dark</div></div>
    </div>
    <div class="case-meta">{meta_html}</div>
    <div class="case-choice">
      <label><input type="radio" tabindex="-1" name="label_{dom_id}" value="SMALL_PARTICLE"
        onchange="onRadioChange('{dom_id}')"> SMALL_PARTICLE <span class="hint">(&larr; Left)</span></label>
      <label><input type="radio" tabindex="-1" name="label_{dom_id}" value="BEEP"
        onchange="onRadioChange('{dom_id}')"> BEEP <span class="hint">(Right &rarr;)</span></label>
      <div class="case-status" id="status-{dom_id}">unlabeled</div>
    </div>
  </div>"""


_SCRIPT_TEMPLATE = """
const TRANCHE_ID = {tranche_id_json};
const API_BASE = {api_base_json};
const STORAGE_KEY = `beep_labeling_${{TRANCHE_ID}}`;

function loadState() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {{}}; }} catch (e) {{ return {{}}; }}
}}
function saveState(state) {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }}

function getReviewerName() {{
  let name = localStorage.getItem('beep_labeling_reviewer') || '';
  if (!name) {{
    name = prompt('Enter your name (used for the label submissions on this tranche):') || '';
    if (name) localStorage.setItem('beep_labeling_reviewer', name);
  }}
  return name;
}}

function updateProgress() {{
  const state = loadState();
  document.getElementById('progress-count').textContent = Object.keys(state).length;
}}

function applyRowVisual(domId, label) {{
  const row = document.getElementById(`row-${{domId}}`);
  row.classList.remove('labeled-SMALL_PARTICLE', 'labeled-BEEP');
  if (label) {{
    row.classList.add(`labeled-${{label}}`);
    document.getElementById(`status-${{domId}}`).textContent = label;
  }}
}}

function selectLabel(row, domId, label) {{
  const radio = row.querySelector(`input[value="${{label}}"]`);
  if (radio) radio.checked = true;
  const state = loadState();
  state[row.dataset.pairKey] = {{
    label: label,
    wafer_key: row.dataset.waferKey,
    inspection_time: row.dataset.inspectionTime,
    defect_id: row.dataset.defectId,
    layer: row.dataset.layer,
  }};
  saveState(state);
  applyRowVisual(domId, label);
  updateProgress();
}}

function onRadioChange(domId) {{
  const row = document.getElementById(`row-${{domId}}`);
  const checked = row.querySelector('input[type=radio]:checked');
  if (checked) selectLabel(row, domId, checked.value);
}}

function focusNextRow(row) {{
  const rows = Array.from(document.querySelectorAll('.case-row'));
  const idx = rows.indexOf(row);
  const next = rows[idx + 1];
  if (next) next.focus();
}}

function handleRowKeydown(e) {{
  const row = e.currentTarget;
  const domId = row.id.replace(/^row-/, '');
  if (e.key === 'ArrowLeft') {{
    e.preventDefault();
    selectLabel(row, domId, 'SMALL_PARTICLE');
    focusNextRow(row);
  }} else if (e.key === 'ArrowRight') {{
    e.preventDefault();
    selectLabel(row, domId, 'BEEP');
    focusNextRow(row);
  }}
}}

function restoreState() {{
  const state = loadState();
  document.querySelectorAll('.case-row').forEach(row => {{
    const domId = row.id.replace(/^row-/, '');
    const entry = state[row.dataset.pairKey];
    if (entry) {{
      const radio = row.querySelector(`input[value="${{entry.label}}"]`);
      if (radio) radio.checked = true;
      applyRowVisual(domId, entry.label);
    }}
    row.addEventListener('keydown', handleRowKeydown);
  }});
  updateProgress();
}}

async function checkBackendStatus() {{
  const el = document.getElementById('backend-status');
  try {{
    const resp = await fetch(`${{API_BASE}}/`);
    const data = await resp.json();
    if (data.report_id === 'beep_labeling') {{
      el.style.color = '#16a34a';
      el.textContent = `Connected: ${{API_BASE}} -> ${{data.data_file}}`;
    }} else {{
      el.style.color = '#dc2626';
      el.textContent = `WRONG SERVER on ${{API_BASE}} (report_id=${{data.report_id}}). `
        + 'Stop it and start reporting/beep_labeling_portal/run_portal.cmd instead -- your labels are still safe in this browser tab until you submit successfully.';
    }}
  }} catch (e) {{
    el.style.color = '#dc2626';
    el.textContent = `No server reachable at ${{API_BASE}}. Start reporting/beep_labeling_portal/run_portal.cmd (not feedback_portal's) `
      + '-- your labels are still safe in this browser tab until you submit successfully.';
  }}
}}

async function submitAll() {{
  const state = loadState();
  const pairKeys = Object.keys(state);
  if (!pairKeys.length) {{ alert('Nothing labeled yet.'); return; }}
  const reviewer = getReviewerName();
  if (!reviewer) {{ alert('Reviewer name is required.'); return; }}
  const labels = pairKeys.map(pk => ({{ pair_key: pk, ...state[pk] }}));
  const statusEl = document.getElementById('submit-status');
  try {{
    const resp = await fetch(`${{API_BASE}}/submit_labels`, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ reviewer: reviewer, tranche_id: TRANCHE_ID, labels: labels }})
    }});
    if (!resp.ok) throw new Error('bad response');
    const data = await resp.json();
    statusEl.textContent = `Submitted ${{data.written}} label(s) \\u2713`;
    localStorage.removeItem(STORAGE_KEY);
    updateProgress();
  }} catch (e) {{
    statusEl.textContent = '';
    alert('Submission failed. Is the beep_labeling_portal backend running (port 8001)?');
  }}
}}

restoreState();
checkBackendStatus();
"""


def build_report(input_csv: Path, output_html: Path, tranche_id: str, api_base: str) -> tuple[dict[str, Any], Path]:
    cases = _load_cases(input_csv)
    report_dir = output_html.resolve().parent

    case_rows_html = "\n".join(_case_row_html(case, report_dir) for case in cases)
    script = _SCRIPT_TEMPLATE.format(
        tranche_id_json=json.dumps(tranche_id),
        api_base_json=json.dumps(api_base),
    )
    html_doc = _HTML_TEMPLATE.format(
        tranche_id=html.escape(tranche_id),
        css=_CSS,
        total_cases=len(cases),
        case_rows=case_rows_html,
        script=script,
        api_base=html.escape(api_base),
    )

    written_path = _write_html_with_rev_fallback(html_doc, output_html)
    summary = {"tranche_id": tranche_id, "total_cases": len(cases)}
    return summary, written_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the BEEP-vs-SMALL_PARTICLE rapid labeling HTML report")
    parser.add_argument("--input-csv", required=True, help="tranche_NNNN_cases.csv from build_beep_labeling_tranche.py")
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--tranche-id", default=None, help="Defaults to the input CSV's stem minus '_cases'")
    parser.add_argument("--api-base", default="http://127.0.0.1:8001", help="beep_labeling_portal backend base URL")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv)
    tranche_id = args.tranche_id or input_csv.stem.replace("_cases", "")
    summary, written_path = build_report(
        input_csv=input_csv,
        output_html=Path(args.output_html),
        tranche_id=tranche_id,
        api_base=args.api_base,
    )
    print(json.dumps(summary, indent=2))
    print(str(written_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
