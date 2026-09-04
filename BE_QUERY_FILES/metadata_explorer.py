"""
Comprehensive INSP_DEFECT metadata explorer.

Shows available source columns, data types, and sample values to help identify
useful metadata inputs for downstream VLM-assisted analysis.
"""

import PyUber
import pandas as pd

DATABASE = "D1D_PROD_YAS_1278"

def explore_full_schema():
    """Comprehensive exploration of INSP_DEFECT table."""
    conn = PyUber.connect(DATABASE)
    
    # Get schema information
    print("=" * 100)
    print(f"INSP_DEFECT Table - Comprehensive Metadata Explorer ({DATABASE})")
    print("=" * 100)
    
    # Sample a larger set to understand data availability
    sample_sql = "SELECT * FROM udb.INSP_DEFECT WHERE ROWNUM <= 100"
    df = pd.read_sql(sample_sql, conn)
    
    print(f"\nTotal sample rows: {len(df)}")
    print(f"Total columns: {len(df.columns)}\n")
    
    # Categorize columns for better understanding
    categories = {
        'Identification': ['DEFECT_ID', 'WAFER_KEY', 'INSPECTION_TIME', 'INSPECTION_TYPE'],
        
        'Position (Raw)': ['INDEX_X', 'INDEX_Y', 'WAFER_X', 'WAFER_Y', 'WAFER_Z'],
        
        'Size/Morphology': ['SIZE_X', 'SIZE_Y', 'SIZE_D', 'SIZE_Z', 'AREA', 'CELLSIZE'],
        
        'Optical Properties': ['INTENSITY', 'CONTRAST', 'POLARITY', 'CHANNEL_ID'],
        
        'Classification': [
            'ROUGH_BIN_CLASS', 'CLASS_NUMBER', 'AUTOMATED_OPTICAL_CLASS',
            'MANUAL_OPTICAL_CLASS', 'MANUAL_SEM_CLASS', 'AUTOMATED_ONLINE_SEM_CLASS',
            'AUTOMATED_OFFLINE_SEM_CLASS', 'AUTOMATED_OFFLINE_OPT_CLASS', 'FA_CLASS',
            'DBCLASS', 'DBGROUP', 'RETICLECLASS', 'KPCBIN'
        ],
        
        'Pattern/Process Info': [
            'PATTERN_KEY', 'SOURCE_DEFECT_ID', 'SOURCE_LAYER', 'SOURCE_LAYER_EXT',
            'SOURCE_RETICLE', 'SOURCE_RETICLE_DEFECT_ID', 'MACRO_SIG_ID',
            'REPEATER_ID', 'REGION_ID', 'ZONEID', 'IDR_ID', 'IDR_TYPE'
        ],
        
        'Criticality/Risk': [
            'KILL_RATIO', 'KILL_RATIO_VARIANCE', 'CRITICAL_AREA',
            'CAREAREAGROUPCODE', 'DBCRITICALITYINDEX', 'LINECOMPLEXITY',
            'DCIRANGE', 'EBRLINE', 'EBBPATTERNDENSITY'
        ],
        
        'Defect Classification/Quality': [
            'ADDER', 'PROPERTY_FLAG', 'REVIEW_SAMPLE_FLAG', 'SAMPLE_BIN_ID',
            'BENIGNCLASS', 'PRINTINGDEFECT', 'EVENTTYPE', 'PCI'
        ],
        
        'Imaging': ['IMAGES', 'FUDA1', 'FUDA2', 'FUDA3', 'FUDA4', 'FUDA5',
                   'TEST_ID', 'SEEDWINDOW_PATTERN_DENSITY', 'PERSPECTIVE'],
    }
    
    # Display categorized column info
    for category, cols in categories.items():
        available_cols = [c for c in cols if c in df.columns]
        if available_cols:
            print(f"\n{'=' * 100}")
            print(f"  {category.upper()}")
            print(f"{'=' * 100}")
            for col in available_cols:
                dtype = df[col].dtype
                non_null = df[col].notna().sum()
                null_pct = (1 - non_null / len(df)) * 100
                
                # Get sample values (non-null)
                samples = df[col].dropna().unique()[:3]
                sample_str = ", ".join(str(s)[:50] for s in samples) if len(samples) > 0 else "NO DATA"
                
                print(f"  {col:<40} dtype={str(dtype):<12} non-null={non_null:4d} ({100-null_pct:5.1f}%)  samples: {sample_str}")
    
    # Find columns that aren't in any category
    all_categorized = set()
    for cols in categories.values():
        all_categorized.update(cols)
    uncategorized = [c for c in df.columns if c not in all_categorized]
    
    if uncategorized:
        print(f"\n{'=' * 100}")
        print(f"  UNCATEGORIZED COLUMNS")
        print(f"{'=' * 100}")
        for col in uncategorized:
            dtype = df[col].dtype
            non_null = df[col].notna().sum()
            null_pct = (1 - non_null / len(df)) * 100
            samples = df[col].dropna().unique()[:3]
            sample_str = ", ".join(str(s)[:50] for s in samples) if len(samples) > 0 else "NO DATA"
            print(f"  {col:<40} dtype={str(dtype):<12} non-null={non_null:4d} ({100-null_pct:5.1f}%)  samples: {sample_str}")
    
    # Summary stats
    print(f"\n{'=' * 100}")
    print("SUMMARY FOR DOWNSTREAM VLM INPUT SELECTION")
    print(f"{'=' * 100}")
    print(f"\nCandidate source columns for downstream VLM analysis:")
    print(f"  Spatial: INDEX_X, INDEX_Y, WAFER_X, WAFER_Y (position)")
    print(f"  Size: SIZE_X, SIZE_Y, SIZE_D, AREA (morphology; SIZE_Z excluded from production due to zero-only behavior)")
    print(f"  Optical: INTENSITY, CONTRAST, POLARITY, CHANNEL_ID (appearance)")
    print(f"  Classification: MANUAL_OPTICAL_CLASS, FA_CLASS (ground truth labels)")
    print(f"  Pattern Context: PATTERN_KEY, MACRO_SIG_ID, REPEATER_ID (position in pattern)")
    print(f"  Risk: KILL_RATIO, CRITICAL_AREA (defect impact)")
    
    conn.close()

if __name__ == "__main__":
    explore_full_schema()
