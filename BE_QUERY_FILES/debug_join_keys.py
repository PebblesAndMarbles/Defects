#!/usr/bin/env python3
"""Debug why join keys aren't matching"""

import pandas as pd
from pathlib import Path

wd = Path("\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE")

# Load just enough to understand structure
edi = pd.read_csv(wd / "BE_QUERY_FILES\\8M5CL_EDI.csv", nrows=5, low_memory=False)
prod = pd.read_csv(wd / "outputs\\wafer\\8M5CL_8M6CL_EXTENDED.csv", nrows=5, low_memory=False)

print("=== EDI Columns (time-related) ===")
for col in edi.columns:
    if any(x in col.upper() for x in ['TIME', 'LOT', 'WAFER', 'LAYER']):
        print(f"  {col}")

print("\n=== Production Columns (time-related) ===")
for col in prod.columns:
    if any(x in col.upper() for x in ['TIME', 'LOT', 'WAFER', 'LAYER']):
        print(f"  {col}")

print("\n=== Sample EDI row (LOT, WAFER_ID, LAYER, INSPECTION_TIME@DEFECT) ===")
try:
    print(edi[['LOT', 'WAFER_ID', 'LAYER', 'INSPECTION_TIME@DEFECT']].iloc[0].to_dict())
except KeyError as e:
    print(f"KeyError: {e}")
    print("Available columns:", edi.columns.tolist()[:10])

print("\n=== Sample Production row (LOT, WAFER_ID, LAYER, INSPECT_TIME) ===")
try:
    print(prod[['LOT', 'WAFER_ID', 'LAYER', 'INSPECT_TIME']].iloc[0].to_dict())
except KeyError as e:
    print(f"KeyError: {e}")
    print("Available columns:", prod.columns.tolist()[:10])

# Check if both datasets have 8M5CL data
print(f"\n=== EDI 8M5CL rows: {(edi['LAYER']=='8M5CL').sum()} ===")
print(f"=== Production 8M5CL rows: {(prod['LAYER']=='8M5CL').sum()} ===")

# Show actual LOT/WAFER combinations
print("\n=== EDI unique LOT/WAFER/LAYER combinations ===")
print(edi[['LOT', 'WAFER_ID', 'LAYER']].drop_duplicates().head())

print("\n=== Production unique LOT/WAFER/LAYER combinations ===")
print(prod[['LOT', 'WAFER_ID', 'LAYER']].drop_duplicates().head())

# Check for data overlap
edi_keys = set(zip(edi['LOT'], edi['WAFER_ID'], edi['LAYER']))
prod_keys = set(zip(prod['LOT'], prod['WAFER_ID'], prod['LAYER']))
overlap = edi_keys & prod_keys
print(f"\n=== Key overlap (LOT+WAFER+LAYER only) ===")
print(f"EDI unique: {len(edi_keys)}, Prod unique: {len(prod_keys)}, Matched: {len(overlap)}")
if overlap:
    print("Sample matched:", list(overlap)[:3])
