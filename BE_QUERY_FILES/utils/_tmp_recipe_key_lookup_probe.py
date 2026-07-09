import pandas as pd
import PyUber

conn = PyUber.connect("D1D_PROD_YAS_1278")
try:
    q = """
    SELECT owner, table_name, column_name
    FROM all_tab_columns
    WHERE owner = 'UDB'
      AND (
        column_name IN ('RECIPE_KEY', 'RECIPE_ID', 'NAME')
        OR table_name LIKE '%RECIPE%'
      )
    ORDER BY table_name, column_name
    """
    df = pd.read_sql(q, conn)
finally:
    conn.close()

print(df.to_string(index=False))
