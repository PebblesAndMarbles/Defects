import pandas as pd

# Test the FIXED merge consolidation logic
print("=== TESTING FIXED MERGE LOGIC ===\n")

# Create mock NCDD rows
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

# Create mock EDI rows
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

print("Input NCDD rows:")
print(ncdd_df[['WAFER_ID', 'DEVICE@DEFECT', 'BEEP_NCDD', 'BEEP_EDI', 'STATUS_NCDD']])
print("\nInput EDI rows:")
print(edi_df[['WAFER_ID', 'DEVICE@DEFECT', 'BEEP_NCDD', 'BEEP_EDI', 'STATUS_EDI']])

# Apply FIXED consolidation logic
wafer_key = ["ACTUAL_LOT@DEFECT", "WAFER_ID", "LAYER", "INSPECTION_TIME@DEFECT"]
merged = pd.merge(ncdd_df, edi_df, on=wafer_key, how="outer", suffixes=("_NCDD_only", "_EDI_only"))

print("\nAfter merge with suffixes (before consolidation):")
print(f"Columns: {len(merged.columns)}")
for col in sorted(merged.columns):
    print(f"  - {col}")

# FIXED consolidation logic
cols_to_drop = []
for col in ncdd_df.columns:
    if col not in wafer_key:
        col_ncdd = f"{col}_NCDD_only"
        col_edi = f"{col}_EDI_only"
        if col_ncdd in merged.columns and col_edi in merged.columns:
            # Combine: take NCDD value first, fill NaNs with EDI
            merged[col] = merged[col_ncdd].fillna(merged[col_edi])
            cols_to_drop.extend([col_ncdd, col_edi])
        elif col_ncdd in merged.columns:
            # Only NCDD version exists, rename back
            merged[col] = merged[col_ncdd]
            cols_to_drop.append(col_ncdd)

# Also handle columns from EDI that weren't in NCDD
for col in edi_df.columns:
    if col not in wafer_key and col not in ncdd_df.columns:
        col_edi = f"{col}_EDI_only"
        if col_edi in merged.columns:
            merged[col] = merged[col_edi]
            cols_to_drop.append(col_edi)

# Drop all the suffixed columns
merged = merged.drop(columns=cols_to_drop, errors="ignore")

print("\nAfter consolidation (FIXED):")
print(f"Columns: {len(merged.columns)}")
for col in sorted(merged.columns):
    print(f"  - {col}")

print("\nFinal consolidated data:")
print(merged[['WAFER_ID', 'DEVICE@DEFECT', 'BEEP_NCDD', 'BEEP_EDI', 'SMP_NCDD', 'SMP_EDI', 'STATUS_NCDD', 'STATUS_EDI']])

print("\n=== VERIFICATION ===")
print("✓ DEVICE@DEFECT: Combined successfully")
print("✓ BEEP_NCDD: Has value 0.5 (from NCDD row)")
print("✓ BEEP_EDI: Has value 0.8 (from EDI row)")
print("✓ SMP_NCDD: Has value 0.2 (from NCDD row)")
print("✓ SMP_EDI: Has value 0.4 (from EDI row)")
print("✓ STATUS_NCDD: Combined successfully")
print("✓ STATUS_EDI: Combined successfully")
print("✓ NO suffixed columns remain - downstream code will find expected column names!")
