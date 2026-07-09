import pandas as pd
import numpy as np
from pathlib import Path

csv = Path(r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED.csv")
df = pd.read_csv(csv, low_memory=False)

k = df[df['CLASS'].isin(['BEEP', 'SMALL_PARTICLE'])].copy()
for c in ['WAFER_X_MM', 'WAFER_Y_MM']:
    k[c] = pd.to_numeric(k[c], errors='coerce')
k = k.dropna(subset=['WAFER_ID', 'LAYER', 'CLASS', 'WAFER_X_MM', 'WAFER_Y_MM'])

rows = []
for (wafer, layer), g in k.groupby(['WAFER_ID', 'LAYER'], dropna=False):
    b = g[g['CLASS'] == 'BEEP'][['WAFER_X_MM', 'WAFER_Y_MM']].to_numpy(dtype=float)
    s = g[g['CLASS'] == 'SMALL_PARTICLE'][['WAFER_X_MM', 'WAFER_Y_MM']].to_numpy(dtype=float)
    if len(b) == 0 or len(s) == 0:
        continue

    d = np.sqrt(((s[:, None, :] - b[None, :, :]) ** 2).sum(axis=2))
    nearest = d.min(axis=1)

    status_vals = g['STATUS'].dropna().unique().tolist()
    status = status_vals[0] if status_vals else 'UNKNOWN'

    rows.append({
        'WAFER_ID': wafer,
        'LAYER': layer,
        'STATUS': status,
        'n_beep': int(len(b)),
        'n_smp': int(len(s)),
        'min_mm': float(nearest.min()),
        'median_nn_mm': float(np.median(nearest)),
        'p90_nn_mm': float(np.percentile(nearest, 90)),
        'frac_smp_within_5mm': float(np.mean(nearest <= 5.0)),
        'frac_smp_within_10mm': float(np.mean(nearest <= 10.0)),
        'frac_smp_within_15mm': float(np.mean(nearest <= 15.0)),
    })

res = pd.DataFrame(rows)
print(f"WAFER_LAYER_WITH_BOTH={len(res)}")
if len(res) == 0:
    raise SystemExit(0)

for st in ['BSL', 'HIGHFLIER']:
    g = res[res['STATUS'] == st]
    if g.empty:
        continue
    print(f"\nSTATUS={st} N={len(g)}")
    print(f"  median(median_nn_mm)={g['median_nn_mm'].median():.2f}")
    print(f"  median(min_mm)={g['min_mm'].median():.2f}")
    print(f"  median(frac<=5mm)={g['frac_smp_within_5mm'].median():.3f}")
    print(f"  median(frac<=10mm)={g['frac_smp_within_10mm'].median():.3f}")
    print(f"  median(frac<=15mm)={g['frac_smp_within_15mm'].median():.3f}")

cand = res[(res['n_beep'] >= 2) & (res['n_smp'] >= 2)].copy()
cand['score'] = (
    0.45 * cand['frac_smp_within_10mm'] +
    0.30 * cand['frac_smp_within_5mm'] +
    0.25 * (1.0 / (1.0 + cand['median_nn_mm']))
)
cand = cand.sort_values(['score', 'n_beep', 'n_smp'], ascending=[False, False, False])
print("\nTOP10_CANDIDATES")
print(cand[['WAFER_ID', 'LAYER', 'STATUS', 'n_beep', 'n_smp', 'median_nn_mm', 'frac_smp_within_5mm', 'frac_smp_within_10mm', 'score']].head(10).to_string(index=False))
