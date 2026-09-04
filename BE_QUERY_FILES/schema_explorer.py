"""
Minimal schema explorer to check what columns are available in INSP_DEFECT table.
This queries the database metadata to list all available columns.
"""

import PyUber
import pandas as pd

DATABASE = "D1D_PROD_YAS_1278"

def explore_insp_defect_schema():
    """Query the USER_TAB_COLUMNS view to list all columns in INSP_DEFECT table."""
    conn = PyUber.connect(DATABASE)
    
    # Query Oracle's metadata to get all columns for INSP_DEFECT
    sql = """
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    DATA_LENGTH, 
    NULLABLE
FROM user_tab_columns
WHERE TABLE_NAME = 'INSP_DEFECT'
ORDER BY COLUMN_ID
"""
    
    print("=" * 80)
    print(f"INSP_DEFECT Table Schema ({DATABASE})")
    print("=" * 80)
    
    df = pd.read_sql(sql, conn)
    print(df.to_string(index=False))
    print(f"\nTotal columns: {len(df)}")
    
    # Check specifically for size-related columns
    size_keywords = ['SIZE', 'WIDTH', 'HEIGHT', 'AREA', 'DIAMETER', 'RADIUS', 'LENGTH']
    size_cols = df[df['COLUMN_NAME'].str.contains('|'.join(size_keywords), case=False, na=False)]
    
    if not size_cols.empty:
        print("\n" + "=" * 80)
        print("Size-related columns found:")
        print("=" * 80)
        print(size_cols.to_string(index=False))
    else:
        print("\nNo size-related columns found in INSP_DEFECT table.")
    
    # Sample a few rows to see what data is available
    print("\n" + "=" * 80)
    print("Sample INSP_DEFECT rows (first 5):")
    print("=" * 80)
    sample_sql = "SELECT * FROM udb.INSP_DEFECT WHERE ROWNUM <= 5"
    sample_df = pd.read_sql(sample_sql, conn)
    print(sample_df.to_string())
    
    conn.close()

if __name__ == "__main__":
    explore_insp_defect_schema()
