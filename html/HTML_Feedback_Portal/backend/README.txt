HTML Feedback Portal — Backend

What this is
-------------
A minimal Flask server that serves a static HTML report and accepts
reviewer feedback via a small JS widget embedded in the page, writing
each submission as a row to a CSV file (optionally on a shared/UNC path).

Run instructions
-----------------
1. Ensure Flask is installed in your Python environment:
     pip install -r requirements.txt
   (If pypi.org is blocked in your environment, confirm Flask is already
   present in your managed Python install before trying to install it.)

2. Start the server:
     python main.py
   or use the paired launcher one directory up:
     run_portal.cmd   (double-click)
     run_portal.ps1   (PowerShell, supports -OpenBrowser and -PythonExe)

3. Open the report in a browser at:
     http://127.0.0.1:8000/
   Do NOT open frontend/index.html directly by double-clicking it —
   opening via file:// prevents feedback submission (browser same-origin
   security blocks fetch() from file:// to http://). The frontend
   template includes an apiBase auto-detect fallback for this case, but
   it still requires the server to be running.

Where feedback goes
---------------------
Edit DATA_FILE at the top of main.py to point at your desired CSV
location — this can be a UNC path so multiple users' local server
instances write to (or read from) a shared location. Set PER_USER_CSV
to True if you want one CSV per submitting user instead of one shared
file (avoids concurrent-write concerns across machines).

Customizing for your report
-----------------------------
- FIELDNAMES in main.py — the CSV columns written per feedback row.
- itemKeys array in frontend/index.html — the list of report items a
  reviewer can leave feedback on. In a real report, generate this list
  dynamically (e.g. server-side templating, or a small JS loader that
  reads item keys from a JSON file next to the report) instead of
  hardcoding it.

Provenance
-----------
Adapted from the PCSA flag_disposition_portal, originally built to let
flag/layer owners submit weekly disposition text against PCSA SPC flags.
See agents_history sessions 2026-08-07_002 and 2026-08-07_003 in the
PCSA workspace for full build history, decisions, and known issues.
