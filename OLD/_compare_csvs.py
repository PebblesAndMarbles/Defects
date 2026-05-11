import os
import pandas as pd
from pandas.util import hash_pandas_object

f1 = r"8M5CL_8M6CL_EXTENDED.csv"
f2 = r"outputs\\wafer\\8M5CL_8M6CL_EXTENDED.csv"


def human_size(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.2f} {u}" if u != "B" else f"{int(v)} B"
        v /= 1024


def get_columns(path):
    return list(pd.read_csv(path, nrows=0).columns)


def analyze(path, common_cols, inspect_col):
    rows = 0
    min_t = None
    max_t = None
    hashes = set()
    for chunk in pd.read_csv(path, chunksize=50000, low_memory=False, dtype=str):
        rows += len(chunk)
        if inspect_col and inspect_col in chunk.columns:
            t = pd.to_datetime(chunk[inspect_col], errors="coerce").dropna()
            if not t.empty:
                cmin = t.min()
                cmax = t.max()
                min_t = cmin if min_t is None or cmin < min_t else min_t
                max_t = cmax if max_t is None or cmax > max_t else max_t
        if common_cols:
            sub = chunk.reindex(columns=common_cols, fill_value="").fillna("")
            h = hash_pandas_object(sub, index=False)
            hashes.update(int(x) for x in h.values)
    return rows, min_t, max_t, hashes

cols1 = get_columns(f1)
cols2 = get_columns(f2)
set1 = set(cols1)
set2 = set(cols2)
common = [c for c in cols1 if c in set2]
only1 = [c for c in cols1 if c not in set2]
only2 = [c for c in cols2 if c not in set1]
inspect_col = "INSPECT_TIME" if ("INSPECT_TIME" in set1 or "INSPECT_TIME" in set2) else None

rows1, min1, max1, h1 = analyze(f1, common, inspect_col)
rows2, min2, max2, h2 = analyze(f2, common, inspect_col)

size1 = os.path.getsize(f1)
size2 = os.path.getsize(f2)
overlap = len(h1 & h2) if common else 0
subset1 = h1.issubset(h2) if common else False
subset2 = h2.issubset(h1) if common else False

reasons = []
if only1 or only2:
    reasons.append("different columns")
if rows1 != rows2:
    reasons.append("different row counts")
if (min1, max1) != (min2, max2):
    reasons.append("different INSPECT_TIME range")
if common:
    if overlap == 0:
        reasons.append("no shared row keys on common columns")
    elif subset1 and rows1 < rows2:
        reasons.append("file 1 appears to be a subset of file 2 on shared columns")
    elif subset2 and rows2 < rows1:
        reasons.append("file 2 appears to be a subset of file 1 on shared columns")
if not reasons:
    reasons.append("same data shape; remaining difference is likely CSV formatting/quoting/ordering")

fmt = lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if x is not None else "N/A"
print(f"File 1: size={size1} ({human_size(size1)}) | rows={rows1} | cols={len(cols1)}")
print(f"File 2: size={size2} ({human_size(size2)}) | rows={rows2} | cols={len(cols2)}")
print(f"Only in file 1: {only1 if only1 else 'None'}")
print(f"Only in file 2: {only2 if only2 else 'None'}")
print(f"INSPECT_TIME file 1: min={fmt(min1)} max={fmt(max1)}")
print(f"INSPECT_TIME file 2: min={fmt(min2)} max={fmt(max2)}")
print(f"Row-key overlap on shared columns ({len(common)} cols, hash-based): shared={overlap}; file1_subset_of_file2={subset1}; file2_subset_of_file1={subset2}")
print(f"Likely size difference: {'; '.join(reasons)}")
