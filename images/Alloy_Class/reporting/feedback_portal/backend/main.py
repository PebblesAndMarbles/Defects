"""
Feedback portal backend for probe_review.html (VLM alloy-class probe review).

Adapted from html/HTML_Feedback_Portal template (see that template's
backend/README.txt for the general pattern/provenance). Customized for:
docs/HANDOFF_HTML_FEEDBACK_PORTAL_INTEGRATION.md.

Deployment model
-----------------
- probe_review.html is a static file opened directly via file:// (it lives
  next to its images and is regenerated per run by
  reporting/build_probe_html_report.py --with-feedback-portal). This
  backend only needs to be running in the background so the page's
  fetch() calls to http://127.0.0.1:8000 succeed -- it does not serve the
  report page itself.
- Feedback rows are appended to DATA_FILE, a CSV living next to whichever
  run's probe_scored_cases.jsonl produced the report (join key: case_id).
  Point this at a new run's output folder via the FEEDBACK_DATA_FILE env
  var (or -DataFile on the launcher) each time a new report is generated
  for review -- do not edit this constant per run.
"""

from flask import Flask, request, jsonify, make_response
import csv
import os
from datetime import datetime
from threading import Lock

app = Flask(__name__)

REPORT_ID = "probe_review"

# Default target CSV; override per-run via the FEEDBACK_DATA_FILE env var
# (set by run_portal.ps1 -DataFile) rather than editing this constant.
DATA_FILE = os.environ.get(
    "FEEDBACK_DATA_FILE",
    os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "outputs", "probes", "scored", "beep_lexicon_v1_20260828_full31",
        "probe_review_feedback.csv",
    )),
)

# One shared CSV across reviewers (not one-per-user): reviewers are expected
# to disagree/comment on the same cases, and the consuming side (coding
# agent) reads all rows per case_id, so a shared file is more useful here.
PER_USER_CSV = False

# Matches the schema in docs/HANDOFF_HTML_FEEDBACK_PORTAL_INTEGRATION.md,
# plus run_id so rows stay attributable if DATA_FILE is ever pointed at a
# combined/multi-run file.
FIELDNAMES = [
    'case_id', 'reviewer', 'submitted_at_utc',
    'agrees_with_vlm', 'corrected_class', 'comment', 'run_id',
]

file_lock = Lock()


def add_cors_headers(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    return resp


@app.after_request
def after_request_func(response):
    return add_cors_headers(response)


@app.route('/submit_feedback', methods=['POST', 'OPTIONS'])
def submit_feedback():
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response())
    data = request.get_json(silent=True) or {}
    required = ['case_id', 'reviewer']
    if not all(k in data and data[k] for k in required):
        return jsonify({'success': False, 'error': 'Missing required fields (case_id, reviewer)'}), 400

    row = {
        'case_id': data['case_id'],
        'reviewer': data['reviewer'],
        'submitted_at_utc': datetime.utcnow().isoformat(),
        'agrees_with_vlm': data.get('agrees_with_vlm', ''),
        'corrected_class': data.get('corrected_class', ''),
        'comment': data.get('comment', ''),
        'run_id': data.get('run_id', ''),
    }

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    # Append-only: a reviewer changing their mind writes a new row rather
    # than an in-place update, so nothing is lost -- consumers take the
    # latest row per case_id.
    with file_lock:
        file_exists = os.path.isfile(DATA_FILE)
        with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    return jsonify({'success': True, 'row': row})


@app.route('/feedback', methods=['GET', 'OPTIONS'])
def get_feedback():
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
        'note': 'This server only provides /submit_feedback and /feedback. '
                'Open the probe_review.html report file directly in a browser.',
    })


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    print(f"Feedback CSV target: {DATA_FILE}")
    app.run(host='127.0.0.1', port=8000, debug=True)
