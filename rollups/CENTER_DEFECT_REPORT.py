"""
CENTER_DEFECT_REPORT.py

Builds center/edge defect HTML reports from rollup CSVs in this BE workspace.

Manifest policy:
- Uses outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv only.
- Strictly includes defects only when both IMAGE_ID 2 and 3 exist in the manifest.
- Requires LOCAL_IMAGE_FILE to exist on disk for both images.

Image grid layout (4 columns, side-by-side):
  Col 1: 8M5CL brightfield (2)   Col 2: 8M5CL darkfield (3)
  Col 3: 8M6CL brightfield (2)   Col 4: 8M6CL darkfield (3)
"""

import os
import sys
from datetime import datetime
from html import escape
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLLUPS_DIR = os.path.join(WORKSPACE_DIR, 'rollups')
MANIFEST_CSV = os.path.join(WORKSPACE_DIR, 'outputs', 'defects', 'DEFECT_COORDINATES_EXTENDED_IMAGES.csv')

SOURCES = [
  {
    'prefix': 'Center',
    'csv': os.path.join(ROLLUPS_DIR, 'Center ICCR2 and SRCIP Center SMPs since December.csv'),
  },
  {
    'prefix': 'Edge',
    'csv': os.path.join(ROLLUPS_DIR, 'Edge ICCR2 and SRCIP Center SMPs since December.csv'),
  },
]

# ── Palette (shared with DEFECT_REPORT_GENERATOR) ─────────────────────────────
_COLORS = {
    'BEEP':           '#42A5F5',
    'SMALL_PARTICLE': '#FFA726',
    'FALLEN_LINES':   '#EF5350',
    'LOWCONF':        '#B0BEC5',
    'OTHER_UNKNOWN':  '#CE93D8',
    'SIZE_SMALL':     '#66BB6A',
}
_DEFAULT_COLOR = '#FFCC02'

_MARKERS = {
    'BEEP':           'o',
    'SMALL_PARTICLE': 's',
    'FALLEN_LINES':   '^',
    'LOWCONF':        'D',
    'OTHER_UNKNOWN':  'x',
    'SIZE_SMALL':     'P',
}
_DEFAULT_MARKER = 'o'

_LAYER_ACCENT = {'8M5CL': '#42A5F5', '8M6CL': '#FFA726'}


def normalize_key(value):
  """Normalize numeric-like key fields so CSV and manifest joins are stable."""
  if pd.isna(value):
    return None
  text = str(value).strip()
  if not text:
    return None
  try:
    num = float(text)
    if num.is_integer():
      return str(int(num))
  except (TypeError, ValueError):
    pass
  return text


def parse_time(value):
  if pd.isna(value):
    return datetime.min
  ts = pd.to_datetime(value, errors='coerce')
  if pd.isna(ts):
    return datetime.min
  return ts.to_pydatetime()


def path_to_uri(path_text):
  """Convert local filesystem paths to clickable file URIs for HTML."""
  try:
    return Path(path_text).as_uri()
  except (ValueError, OSError):
    return str(path_text).replace('\\', '/')


def load_manifest_index(manifest_csv):
  """
  Return {(wafer_key, defect_id): {'2': uri2, '3': uri3}} from inline manifest.
  Keeps the newest INSPECTION_TIME per key/image when duplicates exist.
  """
  cols = ['WAFER_KEY', 'DEFECT_ID', 'IMAGE_ID', 'LOCAL_IMAGE_FILE', 'INSPECTION_TIME']
  man = pd.read_csv(manifest_csv, usecols=cols)

  index = {}
  stats = {
    'manifest_rows': len(man),
    'usable_rows': 0,
    'missing_file_rows': 0,
    'bad_key_rows': 0,
    'duplicate_replaced': 0,
  }

  for _, row in man.iterrows():
    wafer_key = normalize_key(row['WAFER_KEY'])
    defect_id = normalize_key(row['DEFECT_ID'])
    image_id = normalize_key(row['IMAGE_ID'])
    local_file = str(row['LOCAL_IMAGE_FILE']).strip() if not pd.isna(row['LOCAL_IMAGE_FILE']) else ''
    if not wafer_key or not defect_id or image_id not in {'2', '3'}:
      stats['bad_key_rows'] += 1
      continue
    if not local_file or not os.path.isfile(local_file):
      stats['missing_file_rows'] += 1
      continue

    key = (wafer_key, defect_id)
    ts = parse_time(row['INSPECTION_TIME'])
    uri = path_to_uri(local_file)
    entry = index.setdefault(key, {})
    existing = entry.get(image_id)
    if existing and ts > existing['ts']:
      stats['duplicate_replaced'] += 1
      entry[image_id] = {'uri': uri, 'path': local_file, 'ts': ts}
    elif not existing:
      entry[image_id] = {'uri': uri, 'path': local_file, 'ts': ts}
      stats['usable_rows'] += 1

  strict_pairs = {}
  for key, rec in index.items():
    if '2' in rec and '3' in rec:
      strict_pairs[key] = {'2': rec['2']['uri'], '3': rec['3']['uri']}

  stats['strict_pair_keys'] = len(strict_pairs)
  return strict_pairs, stats


# ── Wafermap ───────────────────────────────────────────────────────────────────
def generate_wafermap(df_layer, layer, out_dir, prefix='Center'):
    """Dark-theme wafermap for one layer subset. Saved to out_dir."""
    png_name = f"{prefix}_{layer}_wafermap.png"
    out_path = os.path.join(out_dir, png_name)

    fig, ax = plt.subplots(figsize=(6, 6), facecolor='#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    ax.add_patch(plt.Circle((0, 0), 150,
                             color='#90A4AE', fill=False, linewidth=2.0, zorder=5))

    ax.set_xlim(-170, 170);  ax.set_ylim(-170, 170);  ax.set_aspect('equal')

    major = list(range(-150, 151, 50))
    ax.set_xticks(major);  ax.set_yticks(major)
    ax.set_xticks(list(range(-150, 151, 25)), minor=True)
    ax.set_yticks(list(range(-150, 151, 25)), minor=True)

    ax.grid(which='major', color='#2E2E2E', linewidth=0.7, zorder=0)
    ax.grid(which='minor', color='#242424', linewidth=0.3, zorder=0)
    ax.axhline(0, color='#3E3E3E', linewidth=0.9, zorder=1)
    ax.axvline(0, color='#3E3E3E', linewidth=0.9, zorder=1)

    ax.tick_params(which='both', colors='#607D8B', labelsize=7)
    ax.tick_params(which='minor', length=2)
    ax.set_xlabel('X (mm)', color='#607D8B', fontsize=8, labelpad=4)
    ax.set_ylabel('Y (mm)', color='#607D8B', fontsize=8, labelpad=4)
    for spine in ax.spines.values():
        spine.set_edgecolor('#37474F')

    finebins = sorted(df_layer['FINEBIN'].unique())
    for fb in finebins:
        grp = df_layer[df_layer['FINEBIN'] == fb]
        ax.scatter(
            grp['WAFER_X_MM'].astype(float),
            grp['WAFER_Y_MM'].astype(float),
            c=_COLORS.get(fb, _DEFAULT_COLOR),
            marker=_MARKERS.get(fb, _DEFAULT_MARKER),
            s=22, alpha=0.88, zorder=3, edgecolors='none'
        )

    legend_handles = [
        mpatches.Patch(color=_COLORS.get(fb, _DEFAULT_COLOR),
                       label=f"{fb.replace('_',' ')}  (n={len(df_layer[df_layer['FINEBIN']==fb])})")
        for fb in finebins
    ]
    ax.legend(handles=legend_handles, fontsize=7, loc='upper right',
              facecolor='#263238', edgecolor='#37474F', labelcolor='#E0E0E0',
              framealpha=0.92, borderpad=0.8)

    accent = _LAYER_ACCENT.get(layer, '#90CAF9')
    ax.set_title(f"{prefix} Defects  ·  {layer}  (n={len(df_layer)})",
                 color=accent, fontsize=9, pad=8)

    fig.tight_layout(pad=0.8)
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Wafermap ({layer}) -> {png_name}")
    return png_name


# ── HTML helpers ───────────────────────────────────────────────────────────────
def img_cell(rel_path, label):
    if rel_path:
        return (f'<td>'
                f'<div class="cl">{label}</div>'
                f'<a href="{rel_path}" target="_blank">'
                f'<img src="{rel_path}" loading="lazy"></a>'
                f'</td>')
    return '<td></td>'


def empty_cells(n):
    return '<td></td>' * n


def section_divider(label, color):
    return (f'<tr class="sec-div">'
            f'<td colspan="4" style="border-top:3px solid {color};'
            f'color:{color};padding:10px 8px 6px;font-size:13px;'
            f'font-weight:bold;background:#1e2a2e">'
            f'{label}</td></tr>')


# ── Main ───────────────────────────────────────────────────────────────────────
def build_report(prefix, csv_path, manifest_index):
    print(f"\n{'='*60}")
    print(f"Building: {prefix} report  ({csv_path})")
    df = pd.read_csv(csv_path)

    raw_total = len(df)
    missing_key_rows = 0

    # Normalize keys used for strict manifest joining.
    df['WAFER_KEY_N'] = df['WAFER_KEY'].apply(normalize_key)
    df['DEFECT_ID_N'] = df['DEFECT_ID'].apply(normalize_key)
    missing_key_rows = int((df['WAFER_KEY_N'].isna() | df['DEFECT_ID_N'].isna()).sum())

    df_5 = df[df['LAYER'] == '8M5CL'].copy().reset_index(drop=True)
    df_6 = df[df['LAYER'] == '8M6CL'].copy().reset_index(drop=True)

    print(f"Loaded {len(df)} rows  (8M5CL={len(df_5)}, 8M6CL={len(df_6)})")

    # ── Wafermaps ──────────────────────────────────────────────────────────
    map5 = generate_wafermap(df_5, '8M5CL', ROLLUPS_DIR, prefix)
    map6 = generate_wafermap(df_6, '8M6CL', ROLLUPS_DIR, prefix)

    # ── Collect images ─────────────────────────────────────────────────────
    def get_imgs(df_layer):
        rows_out = []
        missing_both_or_one = 0
        for _, row in df_layer.iterrows():
            key = (row['WAFER_KEY_N'], row['DEFECT_ID_N'])
            rec = manifest_index.get(key) if all(key) else None
            p2 = rec.get('2') if rec else None
            p3 = rec.get('3') if rec else None
            if not (p2 and p3):
                missing_both_or_one += 1
                continue

            fb = row['FINEBIN']
            label = (
                f"{escape(str(row['WAFER_ID']))}<br>"
                f"<span style='color:#546e7a'>"
                f"{escape(str(row['SUBENTITY']))} &bull; #{escape(str(row['DEFECT_ID_N']))}</span>"
            )
            rows_out.append({'p2': p2, 'p3': p3, 'label': label,
                             'fb': fb, 'wafer': row['WAFER_ID'],
                             'did': row['DEFECT_ID'], 'ch': row['SUBENTITY']})
        return rows_out, missing_both_or_one

    imgs_5, missing_5 = get_imgs(df_5)
    imgs_6, missing_6 = get_imgs(df_6)
    filtered_total = len(imgs_5) + len(imgs_6)

    print(
        f"  Included defects (strict manifest IDs 2+3): {filtered_total} / {raw_total} "
        f"(excluded={raw_total-filtered_total}, missing_keys={missing_key_rows})"
    )
    if missing_5 or missing_6:
        print(f"  Excluded for missing id2/id3 image pair: 8M5CL={missing_5}, 8M6CL={missing_6}")

    # ── Table rows — zipped side-by-side from row 1 ────────────────────────
    body = ''
    n_rows = max(len(imgs_5), len(imgs_6))
    for i in range(n_rows):
        r5 = imgs_5[i] if i < len(imgs_5) else None
        r6 = imgs_6[i] if i < len(imgs_6) else None
        # row border color: prefer 8M5CL side if present
        fb_color = _COLORS.get((r5 or r6)['fb'], _DEFAULT_COLOR)
        body += f'<tr style="border-left:3px solid {fb_color}">\n'
        if r5:
            body += img_cell(r5['p2'], r5['label'])
            body += img_cell(r5['p3'], r5['label'])
        else:
            body += empty_cells(2)
        if r6:
            body += img_cell(r6['p2'], r6['label'])
            body += img_cell(r6['p3'], r6['label'])
        else:
            body += empty_cells(2)
        body += '</tr>\n'

    # ── FINEBIN summary for dist table ────────────────────────────────────
    def dist_rows(df_layer):
        from collections import Counter
        out = ''
        for (cls, fb), n in sorted(Counter(zip(df_layer['CLASS'], df_layer['FINEBIN'])).items()):
            col  = _COLORS.get(fb, _DEFAULT_COLOR)
            flag = ' style="color:#FFA726"' if cls != fb else ''
            out += (f'<tr><td>{cls}</td>'
                    f'<td style="color:{col};font-weight:bold"{flag}>{fb}</td>'
                    f'<td style="text-align:right">{n}</td></tr>\n')
        return out

    dist5 = dist_rows(df_5)
    dist6 = dist_rows(df_6)
    accent5 = _LAYER_ACCENT['8M5CL']
    accent6 = _LAYER_ACCENT['8M6CL']

    # ── Full HTML ──────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{prefix} Defect Report</title>
<style>
  body  {{ font-family:Arial,sans-serif; background:#1a1a1a; color:#e0e0e0; margin:24px; }}
  h1   {{ color:#90caf9; margin-bottom:4px; }}
  h2   {{ color:#80cbc4; margin:24px 0 8px; font-size:15px; }}
  a    {{ color:inherit; text-decoration:none; }}

  /* ── wafermaps ── */
  .maps {{ display:flex; gap:24px; justify-content:center; margin:20px 0 28px; }}
  .maps figure {{ margin:0; text-align:center; }}
  .maps img {{ max-width:420px; border:2px solid #37474f; border-radius:6px; }}
  .maps figcaption {{ font-size:12px; color:#607d8b; margin-top:5px; }}

  /* ── dist table ── */
  table.dist {{ border-collapse:collapse; font-size:12px; margin-bottom:24px; }}
  table.dist th {{ background:#263238; color:#80cbc4; padding:6px 16px;
                   border:1px solid #37474f; text-align:left; }}
  table.dist td {{ padding:5px 16px; border:1px solid #37474f; }}
  table.dist tr:hover td {{ background:#263238; }}

  /* ── image grid ── */
  table.main {{ border-collapse:collapse; width:100%; table-layout:fixed; }}
  table.main th {{
    background:#263238; color:#e0e0e0;
    padding:8px 10px; font-size:12px;
    border:1px solid #37474f; text-align:left;
    width:25%;
  }}
  table.main th.l5 {{ border-top:3px solid {accent5}; }}
  table.main th.l6 {{ border-top:3px solid {accent6}; }}
  table.main td {{
    vertical-align:top; padding:7px;
    border:1px solid #2e2e2e; background:#212121;
  }}
  table.main td img {{
    width:100%; display:block;
    border-radius:3px; cursor:pointer;
    transition:opacity .15s;
  }}
  table.main td img:hover {{ opacity:.8; }}
  .cl {{ font-size:10px; color:#90a4ae; margin-bottom:3px; line-height:1.4; }}

  /* column separator between 8M5CL and 8M6CL */
  table.main th:nth-child(3),
  table.main td:nth-child(3) {{ border-left:3px solid #37474f; }}
</style>
</head>
<body>

<h1>{prefix} Defect Report</h1>
<p style="color:#607d8b;font-size:13px;margin-top:0">
  Source: {escape(os.path.basename(csv_path))} &nbsp;&bull;&nbsp;
  Raw: {len(df_5)} defects @ 8M5CL, {len(df_6)} defects @ 8M6CL &nbsp;|&nbsp;
  Included (manifest IDs 2+3): {len(imgs_5)} @ 8M5CL, {len(imgs_6)} @ 8M6CL
</p>

<p style="color:#90a4ae;font-size:12px;margin-top:0">
  Filter summary: raw rows {raw_total}; included {filtered_total}; excluded {raw_total-filtered_total};
  rows with missing WAFER_KEY/DEFECT_ID {missing_key_rows}.
</p>

<div class="maps">
  <figure>
    <a href="{map5}" target="_blank"><img src="{map5}" alt="8M5CL wafermap"></a>
    <figcaption>8M5CL &nbsp;&bull;&nbsp; {len(df_5)} defects</figcaption>
  </figure>
  <figure>
    <a href="{map6}" target="_blank"><img src="{map6}" alt="8M6CL wafermap"></a>
    <figcaption>8M6CL &nbsp;&bull;&nbsp; {len(df_6)} defects</figcaption>
  </figure>
</div>

<h2>CLASS &rarr; FINEBIN &nbsp;&mdash;&nbsp;
  <span style="color:{accent5}">8M5CL</span></h2>
<table class="dist">
<thead><tr>
  <th>CLASS (original)</th><th>FINEBIN (refined)</th>
  <th style="text-align:right">Count</th>
</tr></thead>
<tbody>{dist5}</tbody>
</table>

<h2>CLASS &rarr; FINEBIN &nbsp;&mdash;&nbsp;
  <span style="color:{accent6}">8M6CL</span></h2>
<table class="dist">
<thead><tr>
  <th>CLASS (original)</th><th>FINEBIN (refined)</th>
  <th style="text-align:right">Count</th>
</tr></thead>
<tbody>{dist6}</tbody>
</table>

<h2>Defect Images</h2>
<table class="main">
<thead><tr>
  <th class="l5">8M5CL &mdash; Brightfield</th>
  <th class="l5">8M5CL &mdash; Darkfield</th>
  <th class="l6">8M6CL &mdash; Brightfield</th>
  <th class="l6">8M6CL &mdash; Darkfield</th>
</tr></thead>
<tbody>
{body}
</tbody>
</table>

</body>
</html>"""

    out_path = os.path.join(ROLLUPS_DIR, f'{prefix}_Defect_Report.html')
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f"\nReport written -> {out_path}")


if __name__ == '__main__':
    manifest_index, manifest_stats = load_manifest_index(MANIFEST_CSV)
    print("Manifest loaded:")
    print(
      "  rows={manifest_rows}, usable={usable_rows}, strict_pairs={strict_pair_keys}, "
      "missing_file_rows={missing_file_rows}, bad_key_rows={bad_key_rows}, "
      "duplicate_replaced={duplicate_replaced}".format(**manifest_stats)
    )

    for src in SOURCES:
      build_report(src['prefix'], src['csv'], manifest_index)
