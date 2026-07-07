import pandas as pd

# Simulate what happens with dual-metric JMP data
print("=== SIMULATING MERGE LOGIC ===\n")

# Create mock NCDD rows (from 8M5CL_NCDD_EDI.csv NCDD section)
ncdd_data = {
    'ACTUAL_LOT@DEFECT': ['L123', 'L124'],
    'WAFER_ID': ['W1', 'W2'],
    'LAYER': ['LAYER1', 'LAYER1'],
    'INSPECTION_TIME@DEFECT': pd.to_datetime(['2026-07-06 10:00:00', '2026-07-06 11:00:00']),
    'DEVICE@DEFECT': ['PXSA', 'PXSB'],
    'BEEP_NCDD': [0.5, 0.3],
    'SMP_NCDD': [0.2, 0.1],
    'BEEP_EDI': [None, None],
    'SMP_EDI': [None, None],
    'DEFECT@WAFER@CLASS_NCDD@BEEP': [10, 5],
    'STATUS_NCDD': ['OK', 'OK'],
}

# Create mock EDI rows (from 8M5CL_NCDD_EDI.csv EDI section)
edi_data = {
    'ACTUAL_LOT@DEFECT': ['L123', 'L124'],
    'WAFER_ID': ['W1', 'W2'],
    'LAYER': ['LAYER1', 'LAYER1'],
    'INSPECTION_TIME@DEFECT': pd.to_datetime(['2026-07-06 10:00:00', '2026-07-06 11:00:00']),
    'DEVICE@DEFECT': ['PXSA', 'PXSB'],
    'BEEP_NCDD': [None, None],
    'SMP_NCDD': [None, None],
    'BEEP_EDI': [0.8, 0.6],
    'SMP_EDI': [0.4, 0.2],
    'DEFECT@WAFER@CLASS_EDI@BEEP': [8, 4],
    'STATUS_EDI': ['OK', 'OK'],
}

ncdd_df = pd.DataFrame(ncdd_data)
edi_df = pd.DataFrame(edi_data)

print("NCDD rows:")
print(ncdd_df)
print("\nEDI rows:")
print(edi_df)

# Merge with suffixes (what the current code does)
wafer_key = ['ACTUAL_LOT@DEFECT', 'WAFER_ID', 'LAYER', 'INSPECTION_TIME@DEFECT']
merged = pd.merge(ncdd_df, edi_df, on=wafer_key, how='outer', suffixes=('_NCDD_only', '_EDI_only'))

print("\n\nAfter outer merge with suffixes:")
print("Columns:", list(merged.columns))
print(merged)

# Check consolidation logic
print("\n\nConsolidation check (current code logic):")
all_cols = list(ncdd_df.columns)  # Original columns

for col in all_cols:
    if col not in wafer_key:
        col_ncdd = f"{col}_NCDD_only"
        col_edi = f"{col}_EDI_only"
        
        if col in merged.columns:
            print(f"  ✓ {col}: exists in merged.columns - will consolidate")
        elif col_ncdd in merged.columns and col_edi in merged.columns:
            print(f"  ⚠ {col}: has suffixes ({col_ncdd}, {col_edi}) - consolidation check FAILS")
        elif col_ncdd in merged.columns:
            print(f"  ⚠ {col}: has suffix {col_ncdd} only - consolidation check FAILS")
        else:
            print(f"  ✗ {col}: NOT in merged.columns - consolidation check FAILS")

print("\n\nColumns with suffixes that exist in merged but won't be consolidated:")
for col in merged.columns:
    if col not in wafer_key and ('_NCDD_only' in col or '_EDI_only' in col):
        print(f"  - {col}")

print("\n\n=== PROBLEM IDENTIFIED ===")
print("The consolidation logic checks 'if col in merged.columns'")
print("But after suffixed merge, columns like 'DEVICE@DEFECT' are renamed to:")
print("  - DEVICE@DEFECT_NCDD_only")
print("  - DEVICE@DEFECT_EDI_only")
print("\nSo the consolidation condition FAILS and suffixed columns stay in output!")
print("This means downstream code (defect_processor.py) won't find the expected column names.")
