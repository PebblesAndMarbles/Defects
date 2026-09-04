"""
Backend for the rapid BEEP-vs-SMALL_PARTICLE labeling report
(reporting/build_beep_labeling_report.py).

Sibling of reporting/feedback_portal/backend/main.py, same Flask/CORS/file-lock
pattern, but a batch-oriented contract: the report accumulates selections
client-side (localStorage) and posts them all at once via /submit_labels
when the reviewer clicks "Submit All", rather than one row per selection.

Deployment model
-----------------
- The labeling report HTML is a static file opened directly via file:// (it
  lives next to its images and is regenerated per tranche by
  reporting/build_beep_labeling_report.py). This backend only needs to be
  running in the background so the page's fetch() calls to
  http://127.0.0.1:8001 succeed -- it does not serve the report page itself.
- Labels are appended to DATA_FILE, the ground-truth CSV (join key: pair_key).
  Point this at a different file via the BEEP_LABELING_DATA_FILE env var (or
  -DataFile on the launcher) -- do not edit this constant per run.
- Runs on port 8001 (not 8000) so it can run alongside the existing
  probe-review feedback_portal backend without a port clash.
"""

from flask import Flask, request, jsonify, make_response
import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

app = Flask(__name__)

REPORT_ID = "beep_labeling"

# Default target CSV; override per-run via the BEEP_LABELING_DATA_FILE env var
# (set by run_portal.ps1 -DataFile) rather than editing this constant.
DATA_FILE = os.environ.get(
    "BEEP_LABELING_DATA_FILE",
    os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "outputs", "beep_evidence", "beep_evidence_ground_truth.csv",
    )),
)

# Fresh minimal schema (see docs/TOOLING_INVENTORY_FOR_LABELING_AND_DISPOSITION.md
# plan): wafer_key/inspection_time/defect_id/layer match the production
# coordinate CSV's dedup key + LAYER 1:1 for a direct merge-back join.
FIELDNAMES = [
    'pair_key', 'wafer_key', 'inspection_time', 'defect_id', 'layer',
    'label', 'reviewer', 'submitted_at_utc', 'tranche_id',
]

file_lock = Lock()


def _write_rows_with_rev_fallback(rows: list[dict[str, str]]) -> str:
    target = Path(DATA_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)

    header_needed = not target.exists()
    try:
        with open(target, 'a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            if header_needed:
                writer.writeheader()
            writer.writerows(rows)
        return str(target)
    except PermissionError:
        rev = 2
        while True:
            candidate = target.with_name(f"{target.stem}_rev{rev}{target.suffix}")
            try:
                with open(candidate, 'a', newline='', encoding='utf-8') as handle:
                    writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                    if not candidate.exists() or candidate.stat().st_size == 0:
                        writer.writeheader()
                    writer.writerows(rows)
                return str(candidate)
            except PermissionError:
                rev += 1


def add_cors_headers(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    return resp


@app.after_request
def after_request_func(response):
    return add_cors_headers(response)


@app.route('/submit_labels', methods=['POST', 'OPTIONS'])
def submit_labels():
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response())
    data = request.get_json(silent=True) or {}
    reviewer = data.get('reviewer')
    tranche_id = data.get('tranche_id', '')
    items = data.get('labels') or []

    if not reviewer:
        return jsonify({'success': False, 'error': 'Missing required field: reviewer'}), 400
    if not isinstance(items, list) or not items:
        return jsonify({'success': False, 'error': 'labels must be a non-empty array'}), 400

    submitted_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in items:
        pair_key = item.get('pair_key')
        label = item.get('label')
        if not pair_key or label not in ('SMALL_PARTICLE', 'BEEP'):
            return jsonify({'success': False, 'error': f'Invalid label item: {item}'}), 400
        rows.append({
            'pair_key': pair_key,
            'wafer_key': item.get('wafer_key', ''),
            'inspection_time': item.get('inspection_time', ''),
            'defect_id': item.get('defect_id', ''),
            'layer': item.get('layer', ''),
            'label': label,
            'reviewer': reviewer,
            'submitted_at_utc': submitted_at,
            'tranche_id': tranche_id,
        })

    # Append-only: a batch resubmission writes new rows rather than an
    # in-place update; consumers take the latest row per pair_key.
    with file_lock:
        written_target = _write_rows_with_rev_fallback(rows)

    return jsonify({'success': True, 'written': len(rows), 'data_file': written_target})


@app.route('/labels', methods=['GET', 'OPTIONS'])
def get_labels():
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response())

    results = []
    if not os.path.isfile(DATA_FILE):
        return jsonify(results)
    with file_lock:
        with open(DATA_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
    return jsonify(results)


@app.route('/', methods=['GET'])
def status():
    return jsonify({
        'status': 'ok',
        'report_id': REPORT_ID,
        'data_file': DATA_FILE,
        'note': 'This server only provides /submit_labels and /labels. '
                'Open the beep labeling report HTML file directly in a browser.',
    })


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    print(f"Ground-truth CSV target: {DATA_FILE}")
    app.run(host='127.0.0.1', port=8001, debug=True)
