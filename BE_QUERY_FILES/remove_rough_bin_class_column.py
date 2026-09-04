"""
Remove ROUGH_BIN_CLASS column from DEFECT_COORDINATES_EXTENDED.csv
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_config import PIPELINE_PATHS

csv_path = PIPELINE_PATHS.defect_coordinates_csv

print(f"Loading CSV: {csv_path}")
df = pd.read_csv(csv_path, low_memory=False)
original_cols = len(df.columns)
original_rows = len(df)

print(f"  Original: {original_rows} rows, {original_cols} columns")

if "ROUGH_BIN_CLASS" not in df.columns:
    print("  ROUGH_BIN_CLASS column not found — nothing to remove")
    exit(0)

# Remove ROUGH_BIN_CLASS column
df = df.drop(columns=["ROUGH_BIN_CLASS"])
print(f"  Removed ROUGH_BIN_CLASS column")
print(f"  Updated: {len(df)} rows, {len(df.columns)} columns")

# Write back
df.to_csv(csv_path, index=False)
print(f"  ✓ Wrote to {csv_path}")
