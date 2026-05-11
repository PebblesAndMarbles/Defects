# -*- coding: utf-8 -*-
"""
Created on Sun Dec  8 14:19:16 2024

@author: tbatson
ELWC Batch Query - Multi-Day Pull for Multiple Chambers
"""

# Configuration - Set the number of days to pull data for
DAYS_TO_PULL = 1

def ELWC_batch_query():
    import pandas as pd
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_rows', None)
    
    import PyUber
    import warnings
    warnings.filterwarnings('ignore')
    
    from datetime import datetime
    now = datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    
    # Chamber list
    chambers_list = [
        'AME401_PM1', 'AME401_PM2', 'AME401_PM3',
        'AME403_PM1', 'AME403_PM2', 'AME403_PM3', 'AME403_PM4', 'AME403_PM5', 'AME403_PM6',
        'AME409_PM1', 'AME409_PM2', 'AME409_PM3', 'AME409_PM4', 'AME409_PM5', 'AME409_PM6',
        'AME411_PM1', 'AME411_PM2', 'AME411_PM3', 'AME411_PM4',
        'AME417_PM1', 'AME417_PM2', 'AME417_PM3', 'AME417_PM4', 'AME417_PM5', 'AME417_PM6',
        'AME419_PM3', 'AME419_PM4', 'AME419_PM5', 'AME419_PM6',
        'AME421_PM1', 'AME421_PM2', 'AME421_PM3', 'AME421_PM4', 'AME421_PM5', 'AME421_PM6',
        'AME423_PM1', 'AME423_PM2', 'AME423_PM3', 'AME423_PM4', 'AME423_PM5', 'AME423_PM6',
        'AME425_PM1', 'AME425_PM2', 'AME425_PM3', 'AME425_PM4', 'AME425_PM5', 'AME425_PM6',
        'AME427_PM1', 'AME427_PM2', 'AME427_PM3', 'AME427_PM4', 'AME427_PM5', 'AME427_PM6'
    ]

    # chambers_list = [
    # 'AME404_PM1', 'AME404_PM2',
    # 'AME406_PM1', 'AME406_PM2', 'AME406_PM3', 'AME406_PM4', 'AME406_PM5', 'AME406_PM6',
    # 'AME408_PM1', 'AME408_PM2', 'AME408_PM3', 'AME408_PM4', 'AME408_PM5', 'AME408_PM6',
    # 'AME410_PM2'
    # ]
    
    # Create IN clause for SQL query
    chambers_str = "', '".join(chambers_list)
    
    print(f"Fetching {DAYS_TO_PULL} days of data for {len(chambers_list)} chambers...")
    
    query = f"""
    /*BEGIN SQL*/
    SELECT 
              CASE WHEN  wch.operation  = 8288 THEN '>>'  
                   WHEN  wch.operation  = 116398 THEN '[]' 
                   WHEN wch.operation = 8289 THEN '[]' 
                   ELSE '--' END AS WT
             ,wch.wafer AS wafer
             ,e.entity AS entity
             ,wch.subentity AS subentity
             ,wch.lot AS lot
             ,wch.slot AS slot
             ,wch.operation AS oper
             ,To_Char(wch.start_time,'yyyy-mm-dd hh24:mi:ss') AS start_date
             ,wch.state AS state
             ,lwr.recipe AS seq_recipe
             ,lrc.oper_short_desc AS oper_short_desc
             ,lwr.recipe AS wafer_recipe
             ,leh.product AS lot_product
             ,Replace(Replace(Replace(Replace(Replace(Replace(p.product_description,',',';'),chr(9),' '),chr(10),' '),chr(13),' '),chr(34),''''),chr(7),' ') AS product_description
    FROM 
    F_LotEntityHist leh
    INNER JOIN
    F_WaferChamberHist wch
    ON leh.runkey = wch.runkey
    INNER JOIN F_Entity e ON e.facility NOT IN ('Test','Intel')
    AND e.entity = wch.entity
    AND e.entity = leh.entity
    INNER JOIN F_Lot_Wafer_Recipe lwr ON lwr.recipe_id=wch.wafer_chamber_recipe_id
    INNER JOIN F_Lot_Run_card lrc ON lrc.lotoperkey = wch.lotoperkey
    INNER JOIN F_Product p ON p.product=lrc.product AND p.facility = lrc.facility AND p.latest_version = 'Y'
    WHERE
                  wch.start_time >= SYSDATE - {DAYS_TO_PULL}
     AND      leh.entity Like 'AME%' 
     AND      wch.subentity IN ('{chambers_str}')
    ORDER BY
               wch.subentity, wch.start_time DESC
    /*END SQL*/
    """
    
    # Execute query
    df = pd.read_sql(query, PyUber.connect('D1D_PROD_XEUS_LOCAL'))
    
    print(f"Retrieved {len(df)} records")
    
    # Debug: Check what columns we actually got
    print(f"Columns in dataframe: {list(df.columns)}")
    
    # Check if we have the expected columns
    if 'SUBENTITY' in df.columns:
        subentity_col = 'SUBENTITY'
    elif 'subentity' in df.columns:
        subentity_col = 'subentity'
    else:
        print("ERROR: No subentity column found!")
        print("Available columns:", df.columns.tolist())
        return df
    
    # Save combined file to network directory
    csvwritefile = f'\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\{date_string} {DAYS_TO_PULL} days ALL_CHAMBERS ELWC.csv'
    df.to_csv(csvwritefile, index=False)
    
    print(f"Combined file saved: {csvwritefile}")
    
    # Display summary information
    unique_chambers = df[subentity_col].unique()
    print(f"Chambers found in data: {sorted(unique_chambers)}")
    
    for chamber in chambers_list:
        chamber_df = df[df[subentity_col] == chamber]
        if not chamber_df.empty:
            print(f"Found {len(chamber_df)} records for {chamber}")
        else:
            print(f"No data found for {chamber}")
    
    # Open the combined file
    # import os
    # os.startfile(csvwritefile)
    
    return df

# Execute the function
if __name__ == "__main__":
    df = ELWC_batch_query()
    print(f"\nTotal records retrieved: {len(df)}")
    if len(df) > 0:
        subentity_col = 'SUBENTITY' if 'SUBENTITY' in df.columns else 'subentity'
        print(f"Chambers with data: {df[subentity_col].nunique()}")
        print(f"Date range: {df['START_DATE' if 'START_DATE' in df.columns else 'start_date'].min()} to {df['START_DATE' if 'START_DATE' in df.columns else 'start_date'].max()}")