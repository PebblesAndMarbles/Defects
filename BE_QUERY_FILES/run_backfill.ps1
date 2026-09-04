#!/usr/bin/env python3
"""Run backfill of workweek columns"""
import sys
import subprocess

result = subprocess.run([
    r'c:\Users\tbatson\My Programs\SQLPathFinder3\Python3\python.exe',
    r'\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\BACKFILL_WORKWEEK_COLUMNS.py'
], capture_output=False)

sys.exit(result.returncode)
