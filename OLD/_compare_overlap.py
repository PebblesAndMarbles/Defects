import pandas as pd
from pandas.util import hash_pandas_object

f1 = r"8M5CL_8M6CL_EXTENDED.csv"
f2 = r"outputs\\wafer\\8M5CL_8M6CL_EXTENDED.csv"
cols1 = list(pd.read_csv(f1, nrows=0).columns)
cols2 = list(pd.read_csv(f2, nrows=0).columns)
common = [c for c in cols1 if c in set(cols2)]


def hashes(path):
    out = set()
    for chunk in pd.read_csv(path, chunksize=50000, low_memory=False, dtype=str):
        h = hash_pandas_object(chunk.reindex(columns=common, fill_value='').fillna(''), index=False)
        out.update(int(x) for x in h.values)
    return out

h1 = hashes(f1)
h2 = hashes(f2)
print(f"unique_keys_file1={len(h1)} unique_keys_file2={len(h2)} shared={len(h1 & h2)} only_file1={len(h1 - h2)} only_file2={len(h2 - h1)}")
