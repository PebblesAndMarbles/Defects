import pandas as pd
import PyUber

conn = PyUber.connect("D1D_PROD_YAS_1278")
try:
    q = """
    SELECT
        s.INSPECTION_TIME,
        s.LOT_ID,
        s.LAYER_ID,
        s.PROCESS_EQUIP_ID,
        s.INSPECT_EQUIP_ID,
        s.RECIPE_KEY,
        ir.RECIPE_ID,
        ir.RECIPE_OID,
        ir.RECIPE_VERSION,
        ir.DEVICE,
        ir.INSPECT_EQUIP_ID AS IR_INSPECT_EQUIP_ID,
        ir.LAYER_ID AS IR_LAYER_ID
    FROM UDB.INSP_WAFER_SUMMARY s
    LEFT JOIN UDB.INSP_RECIPE ir
      ON ir.RECIPE_KEY = s.RECIPE_KEY
    WHERE s.INSPECTION_TIME >= SYSDATE - 7
      AND s.LAYER_ID = '6OX450GTO_M025_PST'
      AND s.PROCESS_EQUIP_ID = 'GTO111_PC1'
      AND s.INSPECT_EQUIP_ID = 'UDE415'
      AND s.LOT_ID = 'D619TNV0'
    ORDER BY s.INSPECTION_TIME DESC
    """
    df = pd.read_sql(q, conn)
finally:
    conn.close()

print(df.head(20).to_string(index=False))
print("rows:", len(df))
