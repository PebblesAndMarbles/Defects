#!/usr/bin/env python3
"""Audit column names across EDI, NCDD_EDI, and production CSVs"""

import pandas as pd
from pathlib import Path

wd = Path('.')

print('=== 8M5CL_EDI.csv columns ===')
edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_EDI.csv', nrows=1, low_memory=False)
edi_cols = list(edi_5.columns)
print(edi_cols[:20])
print()

print('=== 8M5CL_NCDD_EDI.csv columns ===')
ncdd_edi_5 = pd.read_csv('BE_QUERY_FILES/8M5CL_NCDD_EDI.csv', nrows=1, low_memory=False)
ncdd_edi_cols = list(ncdd_edi_5.columns)
print(ncdd_edi_cols[:20])
print()

print('=== 8M5CL_8M6CL_EXTENDED.csv columns ===')
prod = pd.read_csv('outputs/wafer/8M5CL_8M6CL_EXTENDED.csv', nrows=1, low_memory=False)
prod_cols = list(prod.columns)
print(prod_cols[:20])

print('\n=== JOIN KEY VERIFICATION ===')
if 'INSPECT_TIME' in prod_cols:
    print('✓ Production has INSPECT_TIME')
else:
    print('✗ Production missing INSPECT_TIME')
    
if 'INSPECTION_TIME@DEFECT' in edi_cols:
    print('✓ EDI has INSPECTION_TIME@DEFECT')
else:
    print('✗ EDI missing INSPECTION_TIME@DEFECT')
    
if 'WAFER_ID' in prod_cols and 'WAFER_ID' in edi_cols:
    print('✓ Both have WAFER_ID')
else:
    print('✗ WAFER_ID mismatch')
    
if 'LAYER' in prod_cols and 'LAYER' in edi_cols:
    print('✓ Both have LAYER')
else:
    print('✗ LAYER mismatch')

print('\n=== PROPOSED JOIN KEY ===')
print('WAFER_ID + INSPECTION_TIME@DEFECT (→ INSPECT_TIME) + LAYER')
