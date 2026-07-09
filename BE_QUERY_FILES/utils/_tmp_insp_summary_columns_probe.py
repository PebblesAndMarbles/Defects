import pandas as pd
import PyUber

conn = PyUber.connect("D1D_PROD_YAS_1278")
try:
    df = pd.read_sql(
        """
        SELECT column_name
        FROM all_tab_columns
        WHERE owner = 'UDB'
          AND table_name = 'INSP_WAFER_SUMMARY'
        ORDER BY column_id
        """,
        conn,
    )
finally:
    conn.close()

mask = df["COLUMN_NAME"].str.contains(
    "RECIPE|LAYER|EQUIP|LOT|STEP|SLOT|INSPECT|PROCESS",
    case=False,
    regex=True,
)
print(df[mask].to_string(index=False))
