import pandas as pd
from collections import Counter

f1 = r"8M5CL_8M6CL_EXTENDED.csv"
f2 = r"outputs\\wafer\\8M5CL_8M6CL_EXTENDED.csv"
KEY_COLS = ["LOT", "WAFER_ID", "LAYER", "SUBENTITY"]
TIME_COL = "INSPECT_TIME"
USE_COLS = KEY_COLS + [TIME_COL]
CHUNK = 50000
CUTOFF = pd.Timestamp("2026-02-28 23:59:59")


def normalize_chunk(df):
    out = pd.DataFrame(index=df.index)
    for c in KEY_COLS:
        out[c] = df[c].fillna("").astype(str).str.strip()
    ts = pd.to_datetime(df[TIME_COL], errors="coerce")
    out[TIME_COL] = ts.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    out["_MONTH"] = ts.dt.strftime("%Y-%m").fillna("INVALID")
    out["_TS"] = ts
    return out


def build_key_set(path):
    keys = set()
    for chunk in pd.read_csv(path, usecols=USE_COLS, dtype=str, low_memory=False, chunksize=CHUNK):
        n = normalize_chunk(chunk)
        keys.update(n[KEY_COLS + [TIME_COL]].itertuples(index=False, name=None))
    return keys


def summarize_only(path, other_keys):
    by_month = Counter()
    by_layer = Counter()
    total = 0
    after = 0
    before_or_equal = 0
    invalid = 0
    for chunk in pd.read_csv(path, usecols=USE_COLS, dtype=str, low_memory=False, chunksize=CHUNK):
        n = normalize_chunk(chunk)
        keys = list(n[KEY_COLS + [TIME_COL]].itertuples(index=False, name=None))
        mask = pd.Series([k not in other_keys for k in keys], index=n.index)
        if not mask.any():
            continue
        u = n.loc[mask]
        total += len(u)
        by_month.update(u["_MONTH"].tolist())
        by_layer.update(u["LAYER"].tolist())
        invalid += int(u["_TS"].isna().sum())
        valid_ts = u["_TS"].dropna()
        after += int((valid_ts > CUTOFF).sum())
        before_or_equal += int((valid_ts <= CUTOFF).sum())
    return {
        "total": total,
        "by_month": by_month,
        "by_layer": by_layer,
        "after": after,
        "before_or_equal": before_or_equal,
        "invalid": invalid,
    }


def top_items(counter_obj, limit=None):
    items = sorted(counter_obj.items(), key=lambda kv: (-kv[1], kv[0]))
    if limit is not None:
        items = items[:limit]
    return ", ".join(f"{k}:{v}" for k, v in items) if items else "none"


def concentration_text(res):
    valid = res["after"] + res["before_or_equal"]
    if valid == 0:
        return f"after_2026-02=no_valid_timestamps (invalid:{res['invalid']})"
    pct = 100.0 * res["after"] / valid
    concentrated = "YES" if pct >= 80 else ("MIXED" if pct >= 50 else "NO")
    return f"after_2026-02={concentrated} ({res['after']}/{valid}={pct:.1f}%, invalid:{res['invalid']})"

keys1 = build_key_set(f1)
keys2 = build_key_set(f2)
res1 = summarize_only(f1, keys2)
res2 = summarize_only(f2, keys1)

print("Normalized key: LOT, WAFER_ID, LAYER, SUBENTITY, normalized INSPECT_TIME(%Y-%m-%d %H:%M:%S)")
for label, res in (("only_in_file1", res1), ("only_in_file2", res2)):
    print(f"{label} total={res['total']} {concentration_text(res)}")
    print(f"  by_month: {top_items(res['by_month'])}")
    print(f"  by_layer: {top_items(res['by_layer'])}")
