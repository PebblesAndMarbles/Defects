# -*- coding: utf-8 -*-
"""
PLT Counter Reset Analysis Query - RAW Data Only
Author: tbatson
"""

import pandas as pd
import PyUber
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.max_rows', None)


def plt_analysis(days_back=1095, allowed_entities=None, output_dir=None):
    """
    Get raw PLT data for specified entities and lookback period
    
    Parameters:
    - days_back: How many days back to search (default: 1095)
    - allowed_entities: Optional list of entity names to include
    - output_dir: Optional directory for CSV output
    """
    
    # Define the specific entities you want to include
    # full_entity_list = [
    #     'AME401_PM1', 'AME401_PM2', 'AME401_PM3',
    #     'AME403_PM1', 'AME403_PM2', 'AME403_PM3', 'AME403_PM4', 'AME403_PM5', 'AME403_PM6',
    #     'AME409_PM1', 'AME409_PM2', 'AME409_PM3', 'AME409_PM4', 'AME409_PM5', 'AME409_PM6',
    #     'AME411_PM1', 'AME411_PM2', 'AME411_PM3', 'AME411_PM4',
    #     'AME417_PM1', 'AME417_PM2', 'AME417_PM3', 'AME417_PM4', 'AME417_PM5', 'AME417_PM6',
    #     'AME419_PM3', 'AME419_PM4', 'AME419_PM5', 'AME419_PM6',
    #     'AME421_PM1', 'AME421_PM2', 'AME421_PM3', 'AME421_PM4', 'AME421_PM5', 'AME421_PM6',
    #     'AME423_PM1', 'AME423_PM2', 'AME423_PM3', 'AME423_PM4', 'AME423_PM5', 'AME423_PM6',
    #     'AME425_PM1', 'AME425_PM2', 'AME425_PM3', 'AME425_PM4', 'AME425_PM5', 'AME425_PM6',
    #     'AME427_PM1', 'AME427_PM2', 'AME427_PM3', 'AME427_PM4', 'AME427_PM5', 'AME427_PM6'
    # ]
    if allowed_entities is None:
        allowed_entities = ['AME417_PM5']
    
    # Define qualified IPNs
    qual_ipns = [633020697, 633020698, 500726510, 633020700, 633020701, 500726511, 
                 633020703, 633020704, 500322123, 633020706, 633020707, 500726514, 
                 633020709, 633020710, 500726515, 633020712, 500322180, 633020958, 
                 633020715, 633020716, 500726517, 633020718, 633020966]
    
    # Get current date for file naming
    now = datetime.now()
    date_string = now.strftime("%Y-%m-%d")
    
    ipn_list = ','.join(map(str, qual_ipns))
    
    # Create entity filter for SQL query
    entity_sql_filter = "'" + "','".join(allowed_entities) + "'"
    
    # Main query: Get PLT data
    query = f"""
    SELECT 
        cr.ENTITY,
        cr.PART_SERIAL_NUMBER,
        cr.PART_INSTALL_DATE,
        cr.ACTION_DATE AS INSTALL_ACTION_DATE,
        cr.PART_COUNTER_VALUE AS INSTALL_COUNTER_VALUE,
        cr.ACTION_TYPE,
        cr.ACTION AS INSTALL_ACTION,
        cr.STATUS,
        cr.ATTRIBUTE_NAME,
        cr.ATTRIBUTE_VALUE,
        cr.ATTRIBUTE_DELTA,
        cr.COUNTER_CATEGORY_VALUE,
        cr.COUNTER_OFFSET_VALUE,
        cr.TXN_DATE,
        cr.NEXT_TXN_DATE,
        cr.EAH_LOAD_DATE,
        cr.LOAD_DATE,
        cr.PLT_ENTITY,
        cr.PART_REMOVE_DATE,
        cr.COUNTER_INIT_VALUE,
        cr.INIT_COUNTER,
        cr.SECURITY_CODE,
        ta.IPN,
        ta.IPN_DESCRIPTION
    FROM F_PLT_COUNTER_RESET_HIST cr
    LEFT JOIN F_PLT_SN_TOOL_ACTIONS ta
        ON cr.ENTITY = ta.ENTITY 
        AND cr.PART_SERIAL_NUMBER = ta.PART_SERIAL_NUMBER
        AND ta.IPN IN ({ipn_list})
    WHERE cr.PART_INSTALL_DATE >= TRUNC(SYSDATE) - {days_back}
        AND cr.ENTITY IN ({entity_sql_filter})
        AND cr.ACTION_TYPE = 'C'
        AND cr.ATTRIBUTE_NAME = 'FullPMRFCounter'
        AND ta.IPN IS NOT NULL
    ORDER BY cr.ENTITY, cr.PART_SERIAL_NUMBER, cr.PART_INSTALL_DATE
    """

    df = pd.read_sql(query, PyUber.connect('D1D_PROD_XEUS'))
    
    if df.empty:
        return pd.DataFrame()
    
    

    # Save raw data to CSV with RAW suffix
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    entity_suffix = allowed_entities[0] if len(allowed_entities) == 1 else f'{len(allowed_entities)}entities'
    csv_file = output_dir / f'{date_string}_PLT_{entity_suffix}_{days_back}days_RAW.csv'
    df.to_csv(csv_file, index=False)
    
    return df

# Run the analysis
if __name__ == "__main__":
    result = plt_analysis(days_back=365, allowed_entities=['AME417_PM5'])