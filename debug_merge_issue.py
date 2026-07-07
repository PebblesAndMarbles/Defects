"""Debug script to analyze the merge issue in production CSVs"""
import pandas as pd

wafer_dir = r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\wafer'

print("=" * 80)
print("PRODUCTION CSV CORRUPTION ANALYSIS")
print("=" * 80)

for fname in ['8M5CL_8M6CL_EXTENDED_60DAY.csv', '8M5CL_8M6CL_EXTENDED.csv']:
    csv_path = f'{wafer_dir}/{fname}'
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"\n{fname}")
        print(f"  Total rows: {len(df):,}")
        
        # Count problematic rows
        unknown_count = (df["CLASS_BEEP"] == "UNKNOWN").sum()
        edi_only_ncdd_null = ((df["BEEP_NCDD"].isna()) & (df["BEEP_EDI"].notna())).sum()
        
        print(f"  CLASS_BEEP=UNKNOWN rows: {unknown_count:,}")
        print(f"  Rows: BEEP_NCDD null AND BEEP_EDI valid: {edi_only_ncdd_null:,}")
        print(f"  Match: {unknown_count == edi_only_ncdd_null}")
        
        # Columns to delete
        problem_cols = ['STATUS_EDI', 'CLASS_EDI', 'ZERO_EDI', 
                       'STATUS_BEEP_EDI', 'CLASS_BEEP_EDI', 'ZERO_BEEP_EDI',
                       'STATUS_SMP_EDI', 'CLASS_SMP_EDI', 'ZERO_SMP_EDI']
        existing_problem_cols = [c for c in problem_cols if c in df.columns]
        print(f"  Columns to delete (existing): {len(existing_problem_cols)}")
        for col in existing_problem_cols:
            print(f"    - {col}")
            
        # Sample UNKNOWN row
        if unknown_count > 0:
            unknown_row = df[df["CLASS_BEEP"] == "UNKNOWN"].iloc[0]
            print(f"\n  Sample UNKNOWN row:")
            print(f"    WAFER_ID: {unknown_row['WAFER_ID']}")
            print(f"    BEEP_NCDD: {unknown_row['BEEP_NCDD']}")
            print(f"    BEEP_EDI: {unknown_row['BEEP_EDI']}")
            print(f"    SMP_NCDD: {unknown_row['SMP_NCDD']}")
            print(f"    SMP_EDI: {unknown_row['SMP_EDI']}")
            
    except Exception as e:
        print(f"\n  ERROR reading {fname}: {e}")

print("\n" + "=" * 80)
print("DIAGNOSIS: EDI-only rows are being included with null NCDD metrics")
print("=" * 80)
print("\nROOT CAUSE:")
print("  The NCDD_EDI source CSVs contain separate rows for:")
print("  1. NCDD rows: BEEP_NCDD and SMP_NCDD have values, EDI columns are null")
print("  2. EDI rows:  BEEP_EDI and SMP_EDI have values, NCDD columns are null")
print("\nThe merge_and_dedup_raw_sources() function dedupes by wafer key only,")
print("which loses the NCDD row when the EDI row comes last in the sort order.")
print("\nRESOLVE BY:")
print("  Option A: Restore pre-pipeline CSVs + fix merge logic to intelligently")
print("           combine NCDD and EDI rows on same wafer")
print("  Option B: Keep current CSVs, delete problem columns and UNKNOWN rows,")
print("           then fix pipeline to process sources correctly")
