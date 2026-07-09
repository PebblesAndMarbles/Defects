import pandas as pd
import PyUber

from surf_scan_elwc_pm_pilot import EVENT_RECIPE_MAP


def main() -> None:
    ch = pd.read_csv(
        "outputs/surf_scan/SS_METRICS_ELWC_PM_PILOT_60D.csv",
        usecols=["PRIMARY_EQUIP"],
    )["PRIMARY_EQUIP"].dropna().unique().tolist()
    ch = sorted(set(ch))
    chamber_in = ", ".join(["'{}'".format(c) for c in ch])
    recipes = sorted(set(EVENT_RECIPE_MAP.values()))
    recipe_in = ", ".join(["'{}'".format(r) for r in recipes])

    conn = PyUber.connect("D1D_PROD_XEUS_GAJT")
    try:
        q1 = f"""
select count(*) as CNT
from F_LotEntityHist leh
join F_WaferChamberHist wch on leh.runkey = wch.runkey
join F_Entity e on e.facility not in ('Test','Intel') and e.entity = wch.entity and e.entity = leh.entity
where wch.start_time >= sysdate - 67
  and leh.entity like 'AME%'
  and wch.subentity in ({chamber_in})
"""
        q2 = f"""
select count(*) as CNT
from F_LotEntityHist leh
join F_WaferChamberHist wch on leh.runkey = wch.runkey
join F_Entity e on e.facility not in ('Test','Intel') and e.entity = wch.entity and e.entity = leh.entity
join F_Lot_Wafer_Recipe lwr on lwr.recipe_id = wch.wafer_chamber_recipe_id
where wch.start_time >= sysdate - 67
  and leh.entity like 'AME%'
  and wch.subentity in ({chamber_in})
  and lwr.recipe in ({recipe_in})
"""
        q3 = f"""
select lwr.recipe as RECIPE, count(*) as CNT
from F_LotEntityHist leh
join F_WaferChamberHist wch on leh.runkey = wch.runkey
join F_Entity e on e.facility not in ('Test','Intel') and e.entity = wch.entity and e.entity = leh.entity
join F_Lot_Wafer_Recipe lwr on lwr.recipe_id = wch.wafer_chamber_recipe_id
where wch.start_time >= sysdate - 67
  and leh.entity like 'AME%'
  and wch.subentity in ({chamber_in})
group by lwr.recipe
order by CNT desc
fetch first 20 rows only
"""

        c1 = int(pd.read_sql(q1, conn).iloc[0, 0])
        c2 = int(pd.read_sql(q2, conn).iloc[0, 0])
        top = pd.read_sql(q3, conn)
    finally:
        conn.close()

    print({"no_recipe_filter": c1, "with_recipe_filter": c2})
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
