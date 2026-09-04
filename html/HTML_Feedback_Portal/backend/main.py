"""
Generic HTML Report Feedback Portal — Flask backend.

Purpose
-------
Small local Flask server that lets a static HTML report collect reviewer
feedback (comments, status, ratings, etc.) and persist it to a CSV on a
shared/UNC network path. Adapted from the PCSA flag_disposition_portal
pattern (see agents_history session 2026-08-07_003 in the PCSA workspace).

Deployment model
-----------------
- No corporate web server required. Each user runs this locally
  (via the paired launcher script) and views the report at
  http://127.0.0.1:8000/ — NOT by double-clicking the HTML file.
  Opening via file:// breaks fetch()/XHR due to browser same-origin
  security rules (this bit the original portal — see BUG-001 in the
  PCSA session logs).
- The frontend is served by this same Flask process (same-origin),
  so no CORS setup is strictly required, but a permissive CORS header
  is still added for flexibility (e.g. testing the HTML from a
  different origin/port).
- Feedback rows are appended to a CSV under DATA_FILE, which can point
  at a shared/UNC path so results are centrally visible without a
  database.

Customize before use
---------------------
1. Set REPORT_ID to a short identifier for this report (used only in
   comments; the actual CSV name/columns are set below).
2. Edit FIELDNAMES to match the fields your report's feedback form
   collects. Keep 'timestamp' and 'user' — most reports want them.
3. Point DATA_FILE at the desired output location (can be a UNC path,
   e.g. r"\\\\server\\share\\path\\feedback.csv").
4. If you want one CSV per user instead of a shared file, see the
   PER_USER_CSV toggle below (mirrors THREAD-004 from the PCSA portal,
   which deferred but planned this).
"""

from flask import Flask, request, jsonify, make_response, send_from_directory
import csv
import os
from datetime import datetime
from threading import Lock

app = Flask(__name__)

REPORT_ID = "generic_report"  # customize: short name for this report

# Where feedback rows are written. Point this at a UNC path for a
# shared/team-visible location, e.g.:
#   r"\\server\share\reports\feedback\generic_report_feedback.csv"
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'feedback.csv')

# Set True to write one CSV per submitting user instead of a shared file.
# Mirrors the per-user CSV naming idea from the PCSA portal (never
# finished there — implemented here as an opt-in).
PER_USER_CSV = False

# Customize these fields to match your report's feedback form.
FIELDNAMES = [
    'item_key', 'comment_text', 'status', 'user', 'timestamp', 'extra'
]

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

file_lock = Lock()


def _resolve_data_file(user: str) -> str:
    """Return the CSV path to write to, honoring PER_USER_CSV."""
    if not PER_USER_CSV:
        return DATA_FILE
    base, ext = os.path.splitext(DATA_FILE)
    safe_user = "".join(c for c in user if c.isalnum() or c in ('_', '-')) or 'anonymous'
    return f"{base}_{safe_user}{ext}"


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
    required = ['item_key', 'comment_text', 'user']
    if not all(k in data and data[k] for k in required):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    row = {
        'item_key': data['item_key'],
        'comment_text': data['comment_text'],
        'status': data.get('status', ''),
        'user': data['user'],
        'timestamp': datetime.utcnow().isoformat(),
        'extra': data.get('extra', ''),
    }

    target_file = _resolve_data_file(row['user'])
    os.makedirs(os.path.dirname(target_file), exist_ok=True)

    with file_lock:
        file_exists = os.path.isfile(target_file)
        with open(target_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    return jsonify({'success': True, 'row': row})


@app.route('/feedback', methods=['GET', 'OPTIONS'])
def get_feedback():
    if request.method == 'OPTIONS':
        return add_cors_headers(make_response())

    user = request.args.get('user', '')
    target_file = _resolve_data_file(user) if PER_USER_CSV and user else DATA_FILE

    results = []
    if not os.path.isfile(target_file):
        return jsonify(results)
    with file_lock:
        with open(target_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
    return jsonify(results)


@app.route('/', methods=['GET'])
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    app.run(host='0.0.0.0', port=8000, debug=True)
