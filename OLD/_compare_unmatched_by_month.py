import pandas as pd
from collections import Counter

f1 = r"8M5CL_8M6CL_EXTENDED.csv"
f2 = r"outputs\\wafer\\8M5CL_8M6CL_EXTENDED.csv"
desired = ["LOT", "WAFER_ID", "LAYER", "INSPECT_TIME", "SUBENTITY"]

cols1 = list(pd.read_csv(f1, nrows=0).columns)
cols2 = list(pd.read_csv(f2, nrows=0).columns)
key_cols = [c for c in desired if c in cols1 and c in cols2]

if not key_cols:
    raise SystemExit("No shared key columns found from desired key list.")

inspect1 = "INSPECT_TIME" in cols1
inspect2 = "INSPECT_TIME" in cols2


def build_key_set(path, cols, chunksize=50000):
    keys = set()
    for chunk in pd.read_csv(path, usecols=cols, dtype=str, low_memory=False, chunksize=chunksize):
        chunk = chunk.fillna("")
        if len(cols) == 1:
            keys.update(chunk[cols[0]].tolist())
        else:
            keys.update(chunk.itertuples(index=False, name=None))
    return keys


def summarize_unmatched(path, cols, other_keys, has_inspect, chunksize=50000):
    needed = list(cols)
    if has_inspect and "INSPECT_TIME" not in needed:
        needed.append("INSPECT_TIME")
    month_counts = Counter()
    total = 0
    min_ts = None
    max_ts = None

    for chunk in pd.read_csv(path, usecols=needed, dtype=str, low_memory=False, chunksize=chunksize):
        key_frame = chunk[cols].fillna("")
        if len(cols) == 1:
            keys = key_frame[cols[0]].tolist()
        else:
            keys = list(key_frame.itertuples(index=False, name=None))
        mask = [k not in other_keys for k in keys]
        unmatched = sum(mask)
        if unmatched == 0:
            continue
        total += unmatched
        if has_inspect:
            ts = pd.to_datetime(chunk.loc[mask, "INSPECT_TIME"], errors="coerce")
            valid = ts.dropna()
            invalid_count = int(ts.isna().sum())
            if invalid_count:
                month_counts["INVALID"] += invalid_count
            if not valid.empty:
                month_counts.update(valid.dt.strftime("%Y-%m").tolist())
                local_min = valid.min()
                local_max = valid.max()
                min_ts = local_min if min_ts is None else min(min_ts, local_min)
                max_ts = local_max if max_ts is None else max(max_ts, local_max)
    return total, month_counts, min_ts, max_ts


def fmt_ts(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts is not None else "NA"

keys1 = build_key_set(f1, key_cols)
keys2 = build_key_set(f2, key_cols)
res1 = summarize_unmatched(f1, key_cols, keys2, inspect1)
res2 = summarize_unmatched(f2, key_cols, keys1, inspect2)

print("KEY_COLS=" + ",".join(key_cols))
for label, res in (("file1_only", res1), ("file2_only", res2)):
    total, month_counts, min_ts, max_ts = res
    months = ", ".join(f"{m}:{month_counts[m]}" for m in sorted(month_counts)) if month_counts else "none"
    print(f"{label} total={total} min_INSPECT_TIME={fmt_ts(min_ts)} max_INSPECT_TIME={fmt_ts(max_ts)}")
    print(f"  months={months}")
