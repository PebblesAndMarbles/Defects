# -*- coding: utf-8 -*-
"""
Configuration module for defect data processing
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline_config import PIPELINE_PATHS

@dataclass
class Config:
    """Configuration class for all file paths and processing parameters"""
    # File paths
    ELWC_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2025-01-12 420 days ALL_CHAMBERS ELWC.csv"
    DP_FAIL_PATH: str = str(PIPELINE_PATHS.pumpdown_fail_path)
    LEAK_RATE_PATH: str = str(PIPELINE_PATHS.leak_rate_path)
    LEAK_BY_PATH: str = str(PIPELINE_PATHS.leak_by_path)
    SPC_MONITOR_PATH: str = str(PIPELINE_PATHS.spc_monitor_path)
    FILE1_PATH: str = str(PIPELINE_PATHS.merged_m5_csv)
    FILE2_PATH: str = str(PIPELINE_PATHS.merged_m6_csv)
    PARTS_PATH: str = str(PIPELINE_PATHS.parts_path)
    PILOT_DATES_PATH: str = str(PIPELINE_PATHS.pilot_dates_path)
    OUTPUT_PATH: str = str(PIPELINE_PATHS.extended_output_csv)
    
    # NEW: Date range filtering for faster iteration
    ENABLE_DATE_FILTER: bool = False
    START_DATE: Optional[str] = None  # Format: "2024-12-01"
    END_DATE: Optional[str] = None    # Format: "2024-12-31"
    
    # Processor control flags - NEW!
    ENABLE_ELWC: bool = True
    ENABLE_LEAK_RATE: bool = True
    ENABLE_DRY_PUMP: bool = True
    ENABLE_LEAK_BY: bool = True
    ENABLE_SPC_MONITOR: bool = True
    ENABLE_RECOAT: bool = True
    ENABLE_DEFECT_TRENDS: bool = True

    # ELWC2 Configuration
    ENABLE_ELWC2: bool = True  # Enable/disable ELWC2 processor
    ELWC2_LOOKBACKS = [5,10,15,30]  # Lookback periods in DAYS

    # SPC Monitor settings
    ENABLE_SPC_MONITOR: bool = True
    SPC_LOOKBACKS = [5, 10, 15,30]  # Lookback periods in days

    LOT_LEVEL_OUTPUT_PATH: str = str(PIPELINE_PATHS.lot_level_output_csv)
    ENABLE_LOT_LEVEL_OUTPUT: bool = True  # Flag to enable/disable lot-level output
    
    # Processing parameters
    RECIPE_GROUPS: List[str] = None
    TIME_WINDOWS: List[int] = None
    PART_TYPES: List[str] = None 
    PILOT_COLUMNS: List[str] = None
    LEAK_BY_GASES: List[str] = None
    SPC_MONITOR_TYPES: List[str] = None
    TREND_LOOKBACK_DAYS: List[int] = None
    TREND_DEFECT_COLS: List[str] = None
    TOLERANCE: float = 1e-10

    # Defect Trends Analysis Settings
    TREND_TIME_COL: str = 'INSPECT_TIME'
    TREND_LAYER_COL: str = 'LAYER'
    TREND_LOT_COL: str = 'LOT'

    # SIMPLE 3-ITEM DEFECT TYPE CONTROLS (NEW)
    TREND_ENABLE_BEEP = True    # Enable/disable ALL BEEP columns (FL, CH, DEV, ratios)
    TREND_ENABLE_SMP = True     # Enable/disable ALL Small Particle columns  
    TREND_ENABLE_NCDD = False   # Enable/disable ALL NCDD columns

    # In your config file
    TREND_DEVICE_DEFECT_TYPES = {
        'ZERO_BEEP': True,     # Enable device-level BEEP trends
        'ZERO_SMP': True,      # Enable device-level Small Particle trends  
        'ZERO_NCDD': False     # Disable device-level NCDD trends (example)
    }

    def __post_init__(self):
        # Convert date strings to datetime objects if provided
        if self.START_DATE:
            self.start_datetime = pd.to_datetime(self.START_DATE)
        else:
            self.start_datetime = None
            
        if self.END_DATE:
            self.end_datetime = pd.to_datetime(self.END_DATE)
        else:
            self.end_datetime = None
        
        if self.RECIPE_GROUPS is None:
            # Add 8MT5 to the recipe groups list
            self.RECIPE_GROUPS = ['MONTW', '8GAB', '8THA', '8GOB', '8PIL', '8SIF', '8MT5',  # NEW!
                                 '0GAB', '0THA', '0GOB', '0PIL', '0SIF']
        if self.TIME_WINDOWS is None:
            self.TIME_WINDOWS = [4, 12, 24, 48, 72, 96]  # Add 24, 48, 72 hours
        if self.PART_TYPES is None:
            self.PART_TYPES = ['PLSCR', 'SLD', 'LNRCAT', 'LNRTSG', 'SLVCAT', 'HUB', 'LID', 'SNZZL']
        if self.PILOT_COLUMNS is None:
            self.PILOT_COLUMNS = ["CCMR2", "ICCR2", "GF", "CV", "SRCIP", "TS"]
        if self.LEAK_BY_GASES is None:
            # Exclude BCL3, AR_LO, and SiCL4 as requested
            self.LEAK_BY_GASES = ['AR', 'C4F8_IGI', 'CF4', 'CH3F', 'CH4', 'CHF3', 'CL2', 'CL2_HI', 
                                 'COS', 'H2', 'HBr', 'HBR', 'HE', 'N2_HI', 'N2_LO', 'NF3', 'O2', 'O2_IGI']
        if self.SPC_MONITOR_TYPES is None:
            self.SPC_MONITOR_TYPES = ['ADDED_CLUSTERS', 'ADDED_CLUSTER_AREA', 'LARGE_ADDERS', 'TOTAL_ADDERS']
        if self.TREND_LOOKBACK_DAYS is None:
            self.TREND_LOOKBACK_DAYS = [5,10,15,30]
        if self.TREND_DEFECT_COLS is None:
            self.TREND_DEFECT_COLS = ['ZERO_NCDD', 'ZERO_BEEP', 'ZERO_SMP']