import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class Config:
    """Configuration class for all file paths and processing parameters"""
    # File paths
    ELWC_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\2025-12-22 185 days ALL_CHAMBERS ELWC.csv"
    DP_FAIL_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_PUMPDOWN_FAILS.csv"
    LEAK_RATE_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_CHLEAK.csv"
    LEAK_BY_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\LEAKBY\processed_mfc_leak_data.csv"
    SPC_MONITOR_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\SPC_MONS\SPC_SS.csv"
    FILE1_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M5CL_NCDD.csv"
    FILE2_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\8M6CL_NCDD.csv"
    PARTS_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\PLT\PLT_CURRENTLY_INSTALLED.csv"
    PILOT_DATES_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\BE_AME_PILOT_TURN_ON_DATES.csv"
    OUTPUT_PATH: str = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_NCDD_PST_WITH_ELWC_LOOKBACKS.csv"
    
    # Processing parameters
    RECIPE_GROUPS: List[str] = None
    TIME_WINDOWS: List[int] = None
    PART_TYPES: List[str] = None
    PILOT_COLUMNS: List[str] = None
    LEAK_BY_GASES: List[str] = None
    SPC_MONITOR_TYPES: List[str] = None
    TOLERANCE: float = 1e-10
    
    def __post_init__(self):
        if self.RECIPE_GROUPS is None:
            self.RECIPE_GROUPS = ['MONTW', '8GAB', '8THA', '8GOB', '8PIL', '8SIF', 
                                 '0GAB', '0THA', '0GOB', '0PIL', '0SIF']
        if self.TIME_WINDOWS is None:
            self.TIME_WINDOWS = [4, 12, 36]
        if self.PART_TYPES is None:
            self.PART_TYPES = ['PLSCR', 'SLD', 'LNRCAT', 'LNRTSG', 'SLVCAT', 'HUB', 'LID', 'SNZZL']
        if self.PILOT_COLUMNS is None:
            self.PILOT_COLUMNS = ["CCMR2", "ICCR2", "GF", "CV", "SRCIP"]
        if self.LEAK_BY_GASES is None:
            # Exclude BCL3, AR_LO, and SiCL4 as requested
            self.LEAK_BY_GASES = ['AR', 'C4F8_IGI', 'CF4', 'CH3F', 'CH4', 'CHF3', 'CL2', 'CL2_HI', 
                                 'COS', 'H2', 'HBr', 'HBR', 'HE', 'N2_HI', 'N2_LO', 'NF3', 'O2', 'O2_IGI']
        if self.SPC_MONITOR_TYPES is None:
            self.SPC_MONITOR_TYPES = ['ADDED_CLUSTERS', 'ADDED_CLUSTER_AREA', 'LARGE_ADDERS', 'TOTAL_ADDERS']


class DataUtils:
    """Utility functions for common data processing tasks"""
    
    @staticmethod
    def safe_datetime_convert(df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Safely convert column to datetime with error handling"""
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors='coerce')
        return df
    
    @staticmethod
    def filter_by_entity_and_time(df: pd.DataFrame, entity: str, end_time, 
                                  entity_col: str = 'SUBENTITY', 
                                  time_col: str = 'START_DATETIME') -> pd.DataFrame:
        """Common pattern for filtering by entity and time"""
        return df[(df[entity_col] == entity) & (df[time_col] <= end_time)]
    
    @staticmethod
    def progress_apply(df: pd.DataFrame, func, desc: str = "Processing", **kwargs):
        """Apply function with progress bar"""
        try:
            from tqdm import tqdm
            tqdm.pandas(desc=desc)
            return df.progress_apply(func, **kwargs)
        except ImportError:
            logging.warning("tqdm not available, using regular apply")
            return df.apply(func, **kwargs)
    
    @staticmethod
    def classify_sum_ncdd(value: float) -> str:
        """Classify SUM_NCDD values into categories"""
        if pd.isna(value):
            return 'UNKNOWN'
        elif value == 0:
            return 'ZERO'
        elif 0 < value < 0.02:
            return 'BSL'
        else:  # value >= 0.02
            return 'HIGHFLIER'


class ProcessorBase:
    """Base class for all data processors"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def safe_load_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """Safely load CSV with error handling"""
        try:
            df = pd.read_csv(file_path)
            self.logger.info(f"Successfully loaded {file_path}: {df.shape}")
            return df
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {e}")
            return None
    
    def validate_required_columns(self, df: pd.DataFrame, required_cols: List[str]) -> bool:
        """Validate that required columns exist"""
        if df is None:
            return False
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            self.logger.error(f"Missing required columns: {missing}")
            return False
        return True


class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, name: str) -> bool:
        """Basic dataframe validation"""
        if df is None or df.empty:
            logging.error(f"{name} is empty or None")
            return False
        logging.info(f"{name} validation passed: {df.shape}")
        return True
    
    @staticmethod
    def validate_time_columns(df: pd.DataFrame, time_cols: List[str]) -> bool:
        """Validate time columns are properly formatted"""
        for col in time_cols:
            if col in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df[col]):
                    logging.warning(f"Column {col} is not datetime type")
                    return False
        return True


class RecipeClassifier:
    """Recipe classification utilities"""
    
    @staticmethod
    def get_technology(oper_short_desc: str) -> str:
        """Determine technology from operation description"""
        if pd.isna(oper_short_desc) or len(str(oper_short_desc)) < 4:
            return 'UNKNOWN'
        fourth_char = str(oper_short_desc)[3]
        return {'8': '1278', '0': '1280'}.get(fourth_char, 'UNKNOWN')
    
    @staticmethod
    def classify_recipe_group(seq_recipe: str, technology: str, is_test_wafer: bool) -> str:
        """Classify recipe into groups"""
        if pd.isna(seq_recipe):
            return 'OTHER'
        
        recipe_str = str(seq_recipe).upper()
        
        # MONTW: Monitors and test wafers
        if (recipe_str.startswith(('M_', 'C_')) or 
            'TEACH' in recipe_str or is_test_wafer):
            return 'MONTW'
        
        # Product wafers by technology
        if not is_test_wafer:
            return RecipeClassifier._classify_product_recipe(recipe_str, technology)
        
        return 'OTHER'
    
    @staticmethod
    def _classify_product_recipe(recipe_str: str, technology: str) -> str:
        """Classify product recipes by technology"""
        recipe_mapping = {
            '1278': {
                ('GABON', 'CHALBI'): '8GAB',
                ('THAR',): '8THA',
                ('GOBI',): '8GOB',
                ('PIL',): '8PIL'
            },
            '1280': {
                ('GABON', 'CHALBI'): '0GAB',
                ('THAR',): '0THA',
                ('GOBI',): '0GOB',
                ('PIL',): '0PIL'
            }
        }
        
        if recipe_str.startswith('S_'):
            return f"{technology[-1]}SIF"  # '8SIF' or '0SIF'
        
        for keywords, group in recipe_mapping.get(technology, {}).items():
            if any(keyword in recipe_str for keyword in keywords):
                return group
        
        return 'OTHER'


class SPCMonitorProcessor(ProcessorBase):
    """SPC surf scan particle monitor data processor"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.spc_df = None
        self.chamber_monitor_data = {}
    
    def load_data(self) -> bool:
        """Load SPC monitor data"""
        self.logger.info("Loading SPC surf scan particle monitor data...")
        self.spc_df = self.safe_load_csv(self.config.SPC_MONITOR_PATH)
        
        if self.spc_df is None:
            return False
        
        # Updated required columns to include MA6 and MA9
        if not self.validate_required_columns(self.spc_df, ['SUBENTITY', 'DATE', 'SIZE', 'VALUE', 'MA3', 'MA6', 'MA9']):
            return False
        
        self.logger.info(f"SPC Monitor DataFrame shape: {self.spc_df.shape}")
        
        # Convert date column to datetime
        self.spc_df = DataUtils.safe_datetime_convert(self.spc_df, 'DATE')
        
        # Show monitor type distribution
        self._show_monitor_distribution()
        
        # Prepare lookup data
        self._prepare_lookup_data()
        
        return True
    
    def _show_monitor_distribution(self):
        """Show monitor type distribution in the data"""
        self.logger.info(f"\nSPC Monitor type distribution:")
        size_counts = self.spc_df['SIZE'].value_counts()
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            count = size_counts.get(monitor_type, 0)
            self.logger.info(f"  {monitor_type}: {count} measurements")
        
        # Show chamber coverage
        unique_chambers = self.spc_df['SUBENTITY'].nunique()
        self.logger.info(f"\nUnique chambers with SPC monitor data: {unique_chambers}")
    
    def _prepare_lookup_data(self):
        """Prepare data for efficient lookups by chamber and monitor type"""
        self.logger.info("Preparing SPC monitor lookup data...")
        
        # Sort by SUBENTITY, SIZE, and DATE for efficient lookup
        self.spc_df = self.spc_df.sort_values(['SUBENTITY', 'SIZE', 'DATE'])
        
        # Create chamber-monitor type grouped data for efficient lookup
        for chamber in self.spc_df['SUBENTITY'].unique():
            chamber_data = self.spc_df[self.spc_df['SUBENTITY'] == chamber]
            self.chamber_monitor_data[chamber] = {}
            
            for monitor_type in self.config.SPC_MONITOR_TYPES:
                monitor_data = chamber_data[chamber_data['SIZE'] == monitor_type].copy()
                if not monitor_data.empty:
                    self.chamber_monitor_data[chamber][monitor_type] = monitor_data
    
    def get_most_recent_monitor_values(self, subentity: str, subentity_end_time, monitor_type: str, debug: bool = False) -> Tuple[float, float, float, float]:
        """Get the most recent monitor values (raw VALUE, MA3, MA6, MA9) for a specific monitor type"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan, np.nan, np.nan, np.nan
        
        # Check if chamber has data for this monitor type
        if subentity not in self.chamber_monitor_data:
            if debug:
                self.logger.debug(f"No SPC monitor data found for chamber {subentity}")
            return np.nan, np.nan, np.nan, np.nan
        
        if monitor_type not in self.chamber_monitor_data[subentity]:
            if debug:
                self.logger.debug(f"No {monitor_type} data found for chamber {subentity}")
            return np.nan, np.nan, np.nan, np.nan
        
        monitor_data = self.chamber_monitor_data[subentity][monitor_type]
        
        if debug:
            self.logger.debug(f"SPC monitor measurements found for {subentity} {monitor_type}: {len(monitor_data)}")
        
        # Filter for measurements before or at the subentity end time
        valid_measurements = monitor_data[monitor_data['DATE'] <= subentity_end_time]
        
        if debug:
            self.logger.debug(f"Valid measurements (before {subentity_end_time}): {len(valid_measurements)}")
            if len(valid_measurements) > 0:
                self.logger.debug(f"Latest valid measurement time: {valid_measurements['DATE'].max()}")
        
        if valid_measurements.empty:
            if debug:
                self.logger.debug(f"No {monitor_type} measurements before {subentity_end_time}")
            return np.nan, np.nan, np.nan, np.nan
        
        # Get the most recent measurement
        most_recent = valid_measurements.loc[valid_measurements['DATE'].idxmax()]
        raw_value = most_recent['VALUE']
        ma3_value = most_recent['MA3']
        ma6_value = most_recent['MA6']
        ma9_value = most_recent['MA9']
        
        if debug:
            self.logger.debug(f"Most recent {monitor_type} measurement time: {most_recent['DATE']}")
            self.logger.debug(f"{monitor_type} raw value: {raw_value}")
            self.logger.debug(f"{monitor_type} MA3 value: {ma3_value}")
            self.logger.debug(f"{monitor_type} MA6 value: {ma6_value}")
            self.logger.debug(f"{monitor_type} MA9 value: {ma9_value}")
        
        return raw_value, ma3_value, ma6_value, ma9_value
    
    def add_spc_monitor_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add SPC monitor data to the main dataframe"""
        if not self.load_data():
            self.logger.error("Failed to load SPC monitor data")
            return dt
        
        # Initialize new columns for each monitor type (raw, MA3, MA6, MA9)
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            dt[monitor_type] = np.nan
            dt[f'{monitor_type}_MA3'] = np.nan
            dt[f'{monitor_type}_MA6'] = np.nan
            dt[f'{monitor_type}_MA9'] = np.nan
        
        # Test with sample data
        self._test_spc_monitor_lookup(dt)
        
        # Process all rows
        self._process_all_spc_monitors(dt)
        
        # Show summary
        self._show_spc_monitor_summary(dt)
        
        return dt
    
    def _test_spc_monitor_lookup(self, dt: pd.DataFrame):
        """Test SPC monitor lookup with sample data"""
        self.logger.info("\n=== TESTING SPC MONITOR LOOKUP ===")
        
        # Try to find rows with subentities that have SPC monitor data
        test_subentities = list(self.chamber_monitor_data.keys())[:3]
        test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        
        if test_rows.empty:
            test_rows = dt.head(3)
        
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            
            # Test a few monitor types
            test_monitors = ['ADDED_CLUSTERS', 'TOTAL_ADDERS']
            for monitor_type in test_monitors:
                raw_value, ma3_value, ma6_value, ma9_value = self.get_most_recent_monitor_values(subentity, subentity_end_time, monitor_type, debug=True)
                if pd.isna(raw_value):
                    self.logger.info(f"  {monitor_type}: NaN (no measurement found)")
                else:
                    self.logger.info(f"  {monitor_type}: {raw_value} (MA3: {ma3_value}, MA6: {ma6_value}, MA9: {ma9_value})")
        
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_spc_monitors(self, dt: pd.DataFrame):
        """Process SPC monitor measurements for all rows"""
        self.logger.info("Processing SPC monitor measurements for all defect scans...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            # Get monitor values for each type
            for monitor_type in self.config.SPC_MONITOR_TYPES:
                raw_value, ma3_value, ma6_value, ma9_value = self.get_most_recent_monitor_values(subentity, subentity_end_time, monitor_type, debug=False)
                dt.at[idx, monitor_type] = raw_value
                dt.at[idx, f'{monitor_type}_MA3'] = ma3_value
                dt.at[idx, f'{monitor_type}_MA6'] = ma6_value
                dt.at[idx, f'{monitor_type}_MA9'] = ma9_value
        
        self.logger.info("SPC monitor processing complete!")
    
    def _show_spc_monitor_summary(self, dt: pd.DataFrame):
        """Show SPC monitor processing summary"""
        self.logger.info(f"\nSPC Monitor Summary:")
        
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            raw_col = monitor_type
            ma3_col = f'{monitor_type}_MA3'
            ma6_col = f'{monitor_type}_MA6'
            ma9_col = f'{monitor_type}_MA9'
            
            raw_non_null = dt[raw_col].notna().sum()
            ma3_non_null = dt[ma3_col].notna().sum()
            ma6_non_null = dt[ma6_col].notna().sum()
            ma9_non_null = dt[ma9_col].notna().sum()
            total_count = len(dt)
            
            self.logger.info(f"{raw_col} - Non-null values: {raw_non_null}/{total_count} ({raw_non_null/total_count*100:.1f}%)")
            self.logger.info(f"{ma3_col} - Non-null values: {ma3_non_null}/{total_count} ({ma3_non_null/total_count*100:.1f}%)")
            self.logger.info(f"{ma6_col} - Non-null values: {ma6_non_null}/{total_count} ({ma6_non_null/total_count*100:.1f}%)")
            self.logger.info(f"{ma9_col} - Non-null values: {ma9_non_null}/{total_count} ({ma9_non_null/total_count*100:.1f}%)")
            
            if raw_non_null > 0:
                valid_raw = dt[dt[raw_col].notna()][raw_col]
                self.logger.info(f"  {raw_col} Range: {valid_raw.min():.4f} to {valid_raw.max():.4f}")
                self.logger.info(f"  {raw_col} Mean: {valid_raw.mean():.4f}")
                
                # Show non-zero count
                non_zero_count = (valid_raw > 0).sum()
                if non_zero_count > 0:
                    self.logger.info(f"  {raw_col} Non-zero values: {non_zero_count} ({non_zero_count/raw_non_null*100:.1f}%)")
class LeakByProcessor(ProcessorBase):
    """Gas-specific leak by measurement processor"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.leak_by_df = None
        self.chamber_gas_data = {}
    
    def load_data(self) -> bool:
        """Load leak by data"""
        self.logger.info("Loading gas-specific leak by data...")
        self.leak_by_df = self.safe_load_csv(self.config.LEAK_BY_PATH)
        
        if self.leak_by_df is None:
            return False
        
        if not self.validate_required_columns(self.leak_by_df, ['SUBENTITY', 'TIME', 'GAS', 'LEAK_BY']):
            return False
        
        self.logger.info(f"Leak by DataFrame shape: {self.leak_by_df.shape}")
        
        # Convert time column to datetime
        self.leak_by_df = DataUtils.safe_datetime_convert(self.leak_by_df, 'TIME')
        
        # Show gas distribution
        self._show_gas_distribution()
        
        # Prepare lookup data
        self._prepare_lookup_data()
        
        return True
    
    def _show_gas_distribution(self):
        """Show gas distribution in the data"""
        self.logger.info(f"\nGas distribution in leak by data:")
        gas_counts = self.leak_by_df['GAS'].value_counts()
        for gas in self.config.LEAK_BY_GASES:
            count = gas_counts.get(gas, 0)
            self.logger.info(f"  {gas}: {count} measurements")
        
        # Show chamber coverage
        unique_chambers = self.leak_by_df['SUBENTITY'].nunique()
        self.logger.info(f"\nUnique chambers with leak by data: {unique_chambers}")
    
    def _prepare_lookup_data(self):
        """Prepare data for efficient lookups by chamber and gas"""
        self.logger.info("Preparing leak by lookup data...")
        
        # Sort by SUBENTITY, GAS, and TIME for efficient lookup
        self.leak_by_df = self.leak_by_df.sort_values(['SUBENTITY', 'GAS', 'TIME'])
        
        # Create chamber-gas grouped data for efficient lookup
        for chamber in self.leak_by_df['SUBENTITY'].unique():
            chamber_data = self.leak_by_df[self.leak_by_df['SUBENTITY'] == chamber]
            self.chamber_gas_data[chamber] = {}
            
            for gas in self.config.LEAK_BY_GASES:
                gas_data = chamber_data[chamber_data['GAS'] == gas].copy()
                if not gas_data.empty:
                    self.chamber_gas_data[chamber][gas] = gas_data
    
    def get_most_recent_leak_by(self, subentity: str, subentity_end_time, gas: str, debug: bool = False) -> float:
        """Get the most recent leak by measurement for a specific gas"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan
        
        # Check if chamber has data for this gas
        if subentity not in self.chamber_gas_data:
            if debug:
                self.logger.debug(f"No leak by data found for chamber {subentity}")
            return np.nan
        
        if gas not in self.chamber_gas_data[subentity]:
            if debug:
                self.logger.debug(f"No {gas} data found for chamber {subentity}")
            return np.nan
        
        gas_data = self.chamber_gas_data[subentity][gas]
        
        if debug:
            self.logger.debug(f"Leak by measurements found for {subentity} {gas}: {len(gas_data)}")
        
        # Filter for measurements before or at the subentity end time
        valid_measurements = gas_data[gas_data['TIME'] <= subentity_end_time]
        
        if debug:
            self.logger.debug(f"Valid measurements (before {subentity_end_time}): {len(valid_measurements)}")
            if len(valid_measurements) > 0:
                self.logger.debug(f"Latest valid measurement time: {valid_measurements['TIME'].max()}")
        
        if valid_measurements.empty:
            if debug:
                self.logger.debug(f"No {gas} measurements before {subentity_end_time}")
            return np.nan
        
        # Get the most recent measurement
        most_recent = valid_measurements.loc[valid_measurements['TIME'].idxmax()]
        leak_by_value = most_recent['LEAK_BY']
        
        if debug:
            self.logger.debug(f"Most recent {gas} measurement time: {most_recent['TIME']}")
            self.logger.debug(f"{gas} leak by value: {leak_by_value}")
        
        return leak_by_value
    
    def add_leak_by_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add gas-specific leak by data to the main dataframe"""
        if not self.load_data():
            self.logger.error("Failed to load leak by data")
            return dt
        
        # Initialize new columns for each gas
        for gas in self.config.LEAK_BY_GASES:
            dt[f'LB_{gas}'] = np.nan
        
        # Test with sample data
        self._test_leak_by_lookup(dt)
        
        # Process all rows
        self._process_all_leak_by(dt)
        
        # Show summary
        self._show_leak_by_summary(dt)
        
        return dt
    
    def _test_leak_by_lookup(self, dt: pd.DataFrame):
        """Test leak by lookup with sample data"""
        self.logger.info("\n=== TESTING LEAK BY LOOKUP ===")
        
        # Try to find rows with subentities that have leak by data
        test_subentities = list(self.chamber_gas_data.keys())[:3]
        test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        
        if test_rows.empty:
            test_rows = dt.head(3)
        
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            
            # Test a few gases
            test_gases = ['AR', 'CF4', 'CL2']
            for gas in test_gases:
                leak_by_value = self.get_most_recent_leak_by(subentity, subentity_end_time, gas, debug=True)
                if pd.isna(leak_by_value):
                    self.logger.info(f"  LB_{gas}: NaN (no measurement found)")
                else:
                    self.logger.info(f"  LB_{gas}: {leak_by_value}")
        
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_leak_by(self, dt: pd.DataFrame):
        """Process leak by measurements for all rows"""
        self.logger.info("Processing leak by measurements for all defect scans...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            # Get leak by values for each gas
            for gas in self.config.LEAK_BY_GASES:
                leak_by_value = self.get_most_recent_leak_by(subentity, subentity_end_time, gas, debug=False)
                dt.at[idx, f'LB_{gas}'] = leak_by_value
        
        self.logger.info("Leak by processing complete!")
    
    def _show_leak_by_summary(self, dt: pd.DataFrame):
        """Show leak by processing summary"""
        self.logger.info(f"\nLeak By Summary:")
        
        for gas in self.config.LEAK_BY_GASES:
            col_name = f'LB_{gas}'
            non_null_count = dt[col_name].notna().sum()
            total_count = len(dt)
            
            self.logger.info(f"{col_name} - Non-null values: {non_null_count}/{total_count} ({non_null_count/total_count*100:.1f}%)")
            
            if non_null_count > 0:
                valid_values = dt[dt[col_name].notna()][col_name]
                self.logger.info(f"  Range: {valid_values.min():.4f} to {valid_values.max():.4f}")
                self.logger.info(f"  Mean: {valid_values.mean():.4f}")
                
                # Show non-zero count
                non_zero_count = (valid_values > 0).sum()
                if non_zero_count > 0:
                    self.logger.info(f"  Non-zero values: {non_zero_count} ({non_zero_count/non_null_count*100:.1f}%)")


class ELWCProcessor(ProcessorBase):
    """ELWC data processor for lookback calculations"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.elwc_df = None
        self.chamber_data = {}
    
    def load_and_preprocess(self) -> bool:
        """Load and preprocess ELWC data"""
        self.logger.info("=== ELWC LOOKBACK PROCESSING (Updated for Test Wafer Logic) ===")
        
        # Load ELWC dataset
        self.elwc_df = self.safe_load_csv(self.config.ELWC_PATH)
        if self.elwc_df is None:
            return False
        
        if not self.validate_required_columns(self.elwc_df, ['START_DATE', 'LOT', 'OPER_SHORT_DESC', 'SEQ_RECIPE']):
            return False
        
        # Preprocess ELWC data
        self.logger.info("Preprocessing ELWC data...")
        
        # Convert START_DATE to datetime
        self.elwc_df = DataUtils.safe_datetime_convert(self.elwc_df, 'START_DATE')
        self.elwc_df['START_DATETIME'] = self.elwc_df['START_DATE']
        
        # Identify test wafers
        self.elwc_df['IS_TEST_WAFER'] = self.elwc_df['LOT'].astype(str).str.contains('T', na=False)
        
        # Determine technology
        self.elwc_df['TECHNOLOGY'] = DataUtils.progress_apply(
            self.elwc_df, 
            lambda row: RecipeClassifier.get_technology(row['OPER_SHORT_DESC']),
            desc="Determining technology",
            axis=1
        )
        
        # Classify recipe groups
        self.elwc_df['RECIPE_GROUP'] = DataUtils.progress_apply(
            self.elwc_df,
            lambda row: RecipeClassifier.classify_recipe_group(
                row['SEQ_RECIPE'], row['TECHNOLOGY'], row['IS_TEST_WAFER']
            ),
            desc="Classifying recipe groups",
            axis=1
        )
        
        # Show statistics
        self._show_preprocessing_stats()
        
        # Sort and group data
        self._prepare_lookup_data()
        
        return True
    
    def _show_preprocessing_stats(self):
        """Show preprocessing statistics"""
        self.logger.info(f"\nRecipe group distribution in ELWC data:")
        self.logger.info(f"{self.elwc_df['RECIPE_GROUP'].value_counts()}")
        
        self.logger.info(f"\nTest wafer statistics:")
        self.logger.info(f"Total test wafers (LOT contains 'T'): {self.elwc_df['IS_TEST_WAFER'].sum()}")
        self.logger.info(f"Total product wafers: {(~self.elwc_df['IS_TEST_WAFER']).sum()}")
    
    def _prepare_lookup_data(self):
        """Prepare data for efficient lookups"""
        self.logger.info("Sorting ELWC data...")
        self.elwc_df = self.elwc_df.sort_values(['SUBENTITY', 'START_DATETIME']).reset_index(drop=True)
        
        # Create chamber-grouped data
        self.logger.info("Creating chamber-grouped lookup tables...")
        try:
            from tqdm import tqdm
            chamber_iterator = tqdm(self.elwc_df['SUBENTITY'].unique(), desc="Grouping by chamber")
        except ImportError:
            chamber_iterator = self.elwc_df['SUBENTITY'].unique()
        
        for chamber in chamber_iterator:
            self.chamber_data[chamber] = self.elwc_df[self.elwc_df['SUBENTITY'] == chamber].copy()
    
    def find_elwc_match(self, wafer_id: str, operation: str, debug: bool = False) -> Tuple[Optional[str], Optional[datetime]]:
        """Find matching ELWC row for wafer_id and operation"""
        matches = self.elwc_df[(self.elwc_df['WAFER'] == wafer_id) & (self.elwc_df['OPER'] == operation)]
        
        if matches.empty:
            if debug:
                self.logger.debug(f"No ELWC match found for {wafer_id}, {operation}")
            return None, None
        
        # If multiple matches, take the most recent one
        if len(matches) > 1:
            if debug:
                self.logger.debug(f"Multiple ELWC matches found ({len(matches)}), taking most recent")
            match = matches.loc[matches['START_DATETIME'].idxmax()]
        else:
            match = matches.iloc[0]
        
        if debug:
            self.logger.debug(f"ELWC match: {match['SUBENTITY']} at {match['START_DATETIME']}")
        
        return match['SUBENTITY'], match['START_DATETIME']
    
    def calculate_lookbacks(self, wafer_id: str, operation: str, debug: bool = False) -> Dict[str, float]:
        """Calculate lookback metrics for a specific wafer/operation"""
        # Find matching row in ELWC data
        subentity, reference_time = self.find_elwc_match(wafer_id, operation, debug)
        
        if subentity is None:
            return {f'{group}_{window}HRS': np.nan 
                   for group in self.config.RECIPE_GROUPS 
                   for window in self.config.TIME_WINDOWS}
        
        # Get chamber-specific historical data
        if subentity not in self.chamber_data:
            if debug:
                self.logger.debug(f"No chamber data for {subentity}")
            return {f'{group}_{window}HRS': np.nan 
                   for group in self.config.RECIPE_GROUPS 
                   for window in self.config.TIME_WINDOWS}
        
        chamber_history = self.chamber_data[subentity]
        results = {}
        
        for window_hours in self.config.TIME_WINDOWS:
            lookback_time = reference_time - timedelta(hours=window_hours)
            
            # Filter chamber history for this time window
            time_mask = ((chamber_history['START_DATETIME'] >= lookback_time) & 
                        (chamber_history['START_DATETIME'] < reference_time))
            window_data = chamber_history[time_mask]
            
            if debug and window_hours == 4:  # Only debug first window
                self.logger.debug(f"{window_hours}hr window: {len(window_data)} total wafers")
                self.logger.debug(f"Test wafers in window: {window_data['IS_TEST_WAFER'].sum()}")
                self.logger.debug(f"Product wafers in window: {(~window_data['IS_TEST_WAFER']).sum()}")
            
            # Count wafers by recipe group
            for group in self.config.RECIPE_GROUPS:
                count = len(window_data[window_data['RECIPE_GROUP'] == group])
                results[f'{group}_{window_hours}HRS'] = count
                
                if debug and window_hours == 4 and count > 0:
                    self.logger.debug(f"{group}: {count} wafers")
        
        return results
    
    def add_elwc_lookbacks(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add ELWC lookback metrics to the defect dataframe"""
        start_time = datetime.now()
        
        if not self.load_and_preprocess():
            self.logger.error("Failed to load ELWC data")
            return dt
        
        # Initialize new columns
        self.logger.info("Initializing lookback columns...")
        for group in self.config.RECIPE_GROUPS:
            for window in self.config.TIME_WINDOWS:
                dt[f'{group}_{window}HRS'] = np.nan
        
        # Test with first few rows
        self._test_lookback_calculations(dt)
        
        # Process all rows
        self._process_all_lookbacks(dt)
        
        # Show summary
        self._show_lookback_summary(dt, start_time)
        
        return dt
    
    def _test_lookback_calculations(self, dt: pd.DataFrame):
        """Test lookback calculations with sample data"""
        self.logger.info("\n=== TESTING LOOKBACK CALCULATIONS ===")
        test_rows = dt.head(3)
        for idx in test_rows.index:
            row = dt.loc[idx]
            wafer_id = row['WAFER_ID']
            operation = row['OPERATION']
            
            self.logger.info(f"\nTesting row {idx}: {wafer_id}, {operation}")
            results = self.calculate_lookbacks(wafer_id, operation, debug=True)
            
            # Show sample results
            sample_cols = [f'{group}_4HRS' for group in self.config.RECIPE_GROUPS[:4]]
            for col in sample_cols:
                self.logger.info(f"  {col}: {results[col]}")
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_lookbacks(self, dt: pd.DataFrame):
        """Process lookbacks for all rows"""
        self.logger.info("Calculating lookbacks for defect data...")
        
        successful_matches = 0
        failed_matches = 0
        
        try:
            from tqdm import tqdm
            iterator = tqdm(dt.index, desc="Processing defect rows")
        except ImportError:
            iterator = dt.index
        
        for idx in iterator:
            row = dt.loc[idx]
            wafer_id = row['WAFER_ID']
            operation = row['OPERATION']
            
            results = self.calculate_lookbacks(wafer_id, operation, debug=False)
            
            # Update defect dataframe with results
            for col, value in results.items():
                dt.at[idx, col] = value
            
            # Track success/failure
            if pd.isna(list(results.values())[0]):
                failed_matches += 1
            else:
                successful_matches += 1
        
        self.logger.info(f"\nLookback processing complete!")
        self.logger.info(f"Successful ELWC matches: {successful_matches}")
        self.logger.info(f"Failed matches (set to NaN): {failed_matches}")
    
    def _show_lookback_summary(self, dt: pd.DataFrame, start_time: datetime):
        """Show summary statistics for lookback processing"""
        self.logger.info(f"\nLookback column statistics:")
        sample_cols = [f'{group}_{window}HRS' 
                      for group in self.config.RECIPE_GROUPS[:4] 
                      for window in self.config.TIME_WINDOWS[:2]]
        
        for col in sample_cols:
            non_null_count = dt[col].notna().sum()
            if non_null_count > 0:
                mean_val = dt[col].mean()
                max_val = dt[col].max()
                self.logger.info(f"{col}: {non_null_count} non-null, mean={mean_val:.1f}, max={max_val}")
            else:
                self.logger.info(f"{col}: All NaN")
        
        total_time = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"ELWC lookback processing completed in {total_time/60:.1f} minutes")


class DryPumpProcessor(ProcessorBase):
    """Dry pump failure data processor"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.dp_fail_df = None
    
    def load_data(self) -> bool:
        """Load dry pump failure data"""
        self.logger.info("Loading dry pump failure data...")
        self.dp_fail_df = self.safe_load_csv(self.config.DP_FAIL_PATH)
        
        if self.dp_fail_df is None:
            return False
        
        if not self.validate_required_columns(self.dp_fail_df, ['SUBENTITY', 'DP_FAIL_TIME']):
            return False
        
        # Show basic info
        self.logger.info(f"DP Fail DataFrame shape: {self.dp_fail_df.shape}")
        self.logger.info(f"Unique subentities with DP failures: {self.dp_fail_df['SUBENTITY'].nunique()}")
        
        # Convert time column to datetime
        self.dp_fail_df = DataUtils.safe_datetime_convert(self.dp_fail_df, 'DP_FAIL_TIME')
        
        # Sort by SUBENTITY and DP_FAIL_TIME for efficient lookup
        self.dp_fail_df = self.dp_fail_df.sort_values(['SUBENTITY', 'DP_FAIL_TIME'])
        
        return True
    
    def get_hours_since_failure(self, subentity: str, subentity_end_time, debug: bool = False) -> float:
        """Get hours since most recent dry pump failure"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan
        
        # Filter DP fail data for this subentity
        entity_dp_data = self.dp_fail_df[self.dp_fail_df['SUBENTITY'] == subentity].copy()
        
        if debug:
            self.logger.debug(f"DP failures found for {subentity}: {len(entity_dp_data)}")
        
        if entity_dp_data.empty:
            if debug:
                self.logger.debug(f"No DP failure data found for {subentity}")
            return np.nan
        
        # Filter for failures before or at the subentity end time
        valid_failures = entity_dp_data[entity_dp_data['DP_FAIL_TIME'] <= subentity_end_time]
        
        if debug:
            self.logger.debug(f"Valid failures (before {subentity_end_time}): {len(valid_failures)}")
            if len(valid_failures) > 0:
                self.logger.debug(f"Latest valid failure time: {valid_failures['DP_FAIL_TIME'].max()}")
        
        if valid_failures.empty:
            if debug:
                self.logger.debug(f"No failures before {subentity_end_time}")
            return np.nan
        
        # Get the most recent failure
        most_recent_fail_time = valid_failures['DP_FAIL_TIME'].max()
        
        # Calculate hours difference
        time_diff = subentity_end_time - most_recent_fail_time
        hours_since_fail = time_diff.total_seconds() / 3600.0
        
        if debug:
            self.logger.debug(f"Most recent failure time: {most_recent_fail_time}")
            self.logger.debug(f"Hours since failure: {hours_since_fail:.2f}")
        
        return hours_since_fail
    
    def add_dp_fail_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add dry pump failure data to the main dataframe"""
        if not self.load_data():
            self.logger.error("Failed to load dry pump data")
            return dt
        
        # Initialize new column with NaN
        dt['DP_FAIL_HRS'] = np.nan
        
        # Test with sample data
        self._test_dp_failure_lookup(dt)
        
        # Process all rows
        self._process_all_dp_failures(dt)
        
        # Show summary
        self._show_dp_failure_summary(dt)
        
        return dt
    
    def _test_dp_failure_lookup(self, dt: pd.DataFrame):
        """Test DP failure lookup with sample data"""
        self.logger.info("\n=== TESTING DP FAILURE LOOKUP ===")
        
        # Try to find rows with subentities that have DP failures
        test_subentities = self.dp_fail_df['SUBENTITY'].unique()[:3]
        test_rows = dt[dt['SUBENTITY'].isin(test_subentities)].head(3)
        
        if test_rows.empty:
            test_rows = dt.head(3)
        
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            hours_since_fail = self.get_hours_since_failure(subentity, subentity_end_time, debug=True)
            
            if pd.isna(hours_since_fail):
                self.logger.info(f"Result - Hours since DP fail: NaN (no failure found)")
            else:
                self.logger.info(f"Result - Hours since DP fail: {hours_since_fail:.2f}")
        
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_dp_failures(self, dt: pd.DataFrame):
        """Process DP failures for all rows"""
        self.logger.info("Processing DP failure times for all defect scans...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            hours_since_fail = self.get_hours_since_failure(subentity, subentity_end_time, debug=False)
            dt.at[idx, 'DP_FAIL_HRS'] = hours_since_fail
        
        self.logger.info("DP failure processing complete!")
    
    def _show_dp_failure_summary(self, dt: pd.DataFrame):
        """Show DP failure processing summary"""
        self.logger.info(f"\nDP Failure Summary:")
        self.logger.info(f"DP_FAIL_HRS - Non-null values: {dt['DP_FAIL_HRS'].notna().sum()}/{len(dt)}")
        self.logger.info(f"DP_FAIL_HRS - Null values (no failure found): {dt['DP_FAIL_HRS'].isna().sum()}/{len(dt)}")
        
        if dt['DP_FAIL_HRS'].notna().sum() > 0:
            valid_values = dt[dt['DP_FAIL_HRS'].notna()]['DP_FAIL_HRS']
            self.logger.info(f"DP_FAIL_HRS - Range (valid values): {valid_values.min():.2f} to {valid_values.max():.2f} hours")
            self.logger.info(f"DP_FAIL_HRS - Mean (valid values): {valid_values.mean():.2f} hours")
            self.logger.info(f"DP_FAIL_HRS - Median (valid values): {valid_values.median():.2f} hours")


class LeakRateProcessor(ProcessorBase):
    """Leak rate data processor"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.leak_df = None
    
    def load_data(self) -> bool:
        """Load leak rate data"""
        self.logger.info("Loading leak rate data...")
        self.leak_df = self.safe_load_csv(self.config.LEAK_RATE_PATH)
        
        if self.leak_df is None:
            return False
        
        if not self.validate_required_columns(self.leak_df, ['SUBENTITY', 'Time']):
            return False
        
        self.logger.info(f"Leak rate DataFrame shape: {self.leak_df.shape}")
        
        # Convert time column to datetime
        self.leak_df = DataUtils.safe_datetime_convert(self.leak_df, 'Time')
        
        # Sort by SUBENTITY and Time for efficient lookup
        self.leak_df = self.leak_df.sort_values(['SUBENTITY', 'Time'])
        
        return True
    
    def get_most_recent_rates(self, subentity: str, subentity_end_time, debug: bool = False) -> Tuple[float, float]:
        """Get the most recent leak rate measurements"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return np.nan, np.nan
        
        # Filter leak data for this subentity
        entity_leak_data = self.leak_df[self.leak_df['SUBENTITY'] == subentity].copy()
        
        if debug:
            self.logger.debug(f"Leak measurements found for {subentity}: {len(entity_leak_data)}")
        
        if entity_leak_data.empty:
            if debug:
                self.logger.debug(f"No leak data found for {subentity}")
            return np.nan, np.nan
        
        # Filter for measurements before or at the subentity end time
        valid_measurements = entity_leak_data[entity_leak_data['Time'] <= subentity_end_time]
        
        if debug:
            self.logger.debug(f"Valid measurements (before {subentity_end_time}): {len(valid_measurements)}")
            if len(valid_measurements) > 0:
                self.logger.debug(f"Latest valid measurement time: {valid_measurements['Time'].max()}")
        
        if valid_measurements.empty:
            if debug:
                self.logger.debug(f"No measurements before {subentity_end_time}")
            return np.nan, np.nan
        
        # Get the most recent measurement
        most_recent = valid_measurements.loc[valid_measurements['Time'].idxmax()]
        
        # Extract leak rates
        raw_leak_rate = most_recent.get('Leak rate', np.nan)
        smooth_leak_rate = most_recent.get('LRSMOOTH', np.nan)
        
        # Handle blank/empty values in LRSMOOTH
        if pd.isna(smooth_leak_rate) or str(smooth_leak_rate).strip() == '':
            smooth_leak_rate = np.nan
        
        if debug:
            self.logger.debug(f"Most recent measurement time: {most_recent['Time']}")
            self.logger.debug(f"Raw leak rate: {raw_leak_rate}")
            self.logger.debug(f"Smooth leak rate: {smooth_leak_rate}")
        
        return raw_leak_rate, smooth_leak_rate
    
    def add_leak_rate_data(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add leak rate data to the main dataframe"""
        if not self.load_data():
            self.logger.error("Failed to load leak rate data")
            return dt
        
        # Initialize new columns
        dt['RAW_LEAK_RATE'] = np.nan
        dt['SMOOTH_LEAK_RATE'] = np.nan
        
        # Test with sample data
        self._test_leak_rate_lookup(dt)
        
        # Process all rows
        self._process_all_leak_rates(dt)
        
        # Show summary
        self._show_leak_rate_summary(dt)
        
        return dt
    
    def _test_leak_rate_lookup(self, dt: pd.DataFrame):
        """Test leak rate lookup with sample data"""
        self.logger.info("\n=== TESTING LEAK RATE LOOKUP ===")
        test_rows = dt.head(3)
        for idx in test_rows.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            self.logger.info(f"\nRow {idx}: {subentity} at {subentity_end_time}")
            raw_rate, smooth_rate = self.get_most_recent_rates(subentity, subentity_end_time, debug=True)
            self.logger.info(f"Result - Raw: {raw_rate}, Smooth: {smooth_rate}")
        self.logger.info("=== END TEST ===\n")
    
    def _process_all_leak_rates(self, dt: pd.DataFrame):
        """Process leak rates for all rows"""
        self.logger.info("Processing leak rates for all defect scans...")
        
        for idx in dt.index:
            if idx % 100 == 0:
                self.logger.info(f"Processing row {idx}/{len(dt)}")
            
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            raw_rate, smooth_rate = self.get_most_recent_rates(subentity, subentity_end_time, debug=False)
            
            dt.at[idx, 'RAW_LEAK_RATE'] = raw_rate
            dt.at[idx, 'SMOOTH_LEAK_RATE'] = smooth_rate
        
        self.logger.info("Leak rate processing complete!")
    
    def _show_leak_rate_summary(self, dt: pd.DataFrame):
        """Show leak rate processing summary"""
        self.logger.info(f"\nLeak Rate Summary:")
        self.logger.info(f"RAW_LEAK_RATE - Non-null values: {dt['RAW_LEAK_RATE'].notna().sum()}/{len(dt)}")
        if dt['RAW_LEAK_RATE'].notna().sum() > 0:
            self.logger.info(f"RAW_LEAK_RATE - Range: {dt['RAW_LEAK_RATE'].min():.4f} to {dt['RAW_LEAK_RATE'].max():.4f}")
        
        self.logger.info(f"SMOOTH_LEAK_RATE - Non-null values: {dt['SMOOTH_LEAK_RATE'].notna().sum()}/{len(dt)}")
        if dt['SMOOTH_LEAK_RATE'].notna().sum() > 0:
            self.logger.info(f"SMOOTH_LEAK_RATE - Range: {dt['SMOOTH_LEAK_RATE'].min():.4f} to {dt['SMOOTH_LEAK_RATE'].max():.4f}")


class DefectDataProcessor(ProcessorBase):
    """Main defect data processor that orchestrates all processing steps"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.elwc_processor = ELWCProcessor(config)
        self.dp_processor = DryPumpProcessor(config)
        self.leak_processor = LeakRateProcessor(config)
        self.leak_by_processor = LeakByProcessor(config)
        self.spc_monitor_processor = SPCMonitorProcessor(config)  # NEW!
    
    def load_base_data(self) -> pd.DataFrame:
        """Load and combine base defect data"""
        self.logger.info("Loading and concatenating data files...")
        
        df1 = self.safe_load_csv(self.config.FILE1_PATH)
        df2 = self.safe_load_csv(self.config.FILE2_PATH)
        
        if df1 is None or df2 is None:
            raise ValueError("Failed to load base data files")
        
        dt = pd.concat([df1, df2], ignore_index=True)
        self.logger.info(f"Combined dataframe shape: {dt.shape}")
        
        return dt
    
    def clean_and_rename_columns(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Clean and rename columns"""
        self.logger.info("Cleaning and renaming columns...")
        
        # Delete columns containing 'SORTER'
        cols_to_delete = [col for col in dt.columns if 'SORTER' in col]
        if cols_to_delete:
            dt = dt.drop(columns=cols_to_delete)
        
        # Columns to keep
        cols2keep = ["WAFER", "WAFER_ID", "LAYER"]
        
        # Create rename mapping for exact matches
        rename_map = {
            "DEFECT@WAFER@CLASS_NCDD@BEEP": "BEEP_NCDD",
            "DEFECT@WAFER@CLASS_NCDD@SMALL_PARTICLE": "SMP_NCDD",
            "ACTUAL_LOT@DEFECT": "LOT",
            "INSPECTION_TIME@DEFECT": "INSPECT_TIME",
            "INSPECTION_TOOL@DEFECT": "INSPECT_TOOL",
            "PRODUCT@STARTS": "PRODUCT"
        }
        
        # Flexible patterns that might differ between 8M5 and 8M6
        flexible_patterns = {
            "LOT": "LOT7",
            "ENTITY": "ENTITY",
            "SLOT": "SLOT",
            "SUBENTITY": "SUBENTITY",
            "OPERATION_NUMBER": "OPERATION",
            "RECIPE@NTSC": "RECIPE",
            "END_TIME@CHAMBER": "SUBENTITY_END_TIME",
            "PROCESS_ORDER": "P_ORDER",
            "FullPMCounter": "FULLPM",
            "FullPMRFCounter": "FULLPM_RF",
            "MiniPMCounter": "MINIPM",
            "MiniPMRFCounter": "MINIPM_RF",
            "SSCounter": "CNTR_SS",
            "PRIOR_LOT_RECIPE": "PL_RECIPE",
            "PRIOR_TIME_BETWEEN": "PT_BTWN",
            "TIME@PRIOR_LOT": "PL_TIME",
            "PROCESS_TIME@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UPT_12HRS",
            "N_WAFERS@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UNW_12HRS",
            "PERCENT_UTILIZATION@BATCH_SUBENTITY_UTILIZATION@12HOURS": "UP_12HRS"
        }
        
        # Process flexible patterns FIRST
        for pattern, new_name in flexible_patterns.items():
            matching_cols = [col for col in dt.columns if col.startswith(pattern)]
            
            if matching_cols:
                dt[new_name] = None
                
                # Copy data from all matching columns, prioritizing non-null values
                for col in matching_cols:
                    mask = dt[new_name].isna() & dt[col].notna()
                    dt.loc[mask, new_name] = dt.loc[mask, col]
                
                # Drop the original columns
                dt = dt.drop(columns=matching_cols)
                cols2keep.append(new_name)
        
        # THEN process exact matches
        for key, new_name in rename_map.items():
            if key in dt.columns:
                dt = dt.rename(columns={key: new_name})
                cols2keep.append(new_name)
        
        # Delete columns not in cols2keep
        final_cols_to_delete = [col for col in dt.columns if col not in cols2keep]
        if final_cols_to_delete:
            dt = dt.drop(columns=final_cols_to_delete)
        
        self.logger.info("Column renaming and cleanup complete!")
        return dt
    
    def add_pilot_status(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add pilot status columns"""
        self.logger.info("Adding pilot status columns...")
        
        # Load pilot turn-on dates
        pilot_on_time_df = self.safe_load_csv(self.config.PILOT_DATES_PATH)
        if pilot_on_time_df is None:
            self.logger.error("Failed to load pilot dates")
            return dt
        
        # Convert time columns to datetime
        time_column_name = "SUBENTITY_END_TIME"
        subentity_column_name = "SUBENTITY"
        
        if time_column_name in dt.columns:
            dt = DataUtils.safe_datetime_convert(dt, time_column_name)
        
        for col in self.config.PILOT_COLUMNS:
            if col in pilot_on_time_df.columns:
                pilot_on_time_df = DataUtils.safe_datetime_convert(pilot_on_time_df, col)
        
        # Create pilot status columns
        self.logger.info("Creating pilot status columns...")
        for col_to_create in self.config.PILOT_COLUMNS:
            dt[col_to_create] = "OFF"  # Initialize all as OFF
            
            for i in dt.index:
                current_subentity = dt.loc[i, subentity_column_name]
                current_data_time = dt.loc[i, time_column_name]
                
                # Skip if subentity or time is null
                if pd.isna(current_subentity) or pd.isna(current_data_time):
                    continue
                
                # Find matching subentity in pilot data
                matching_rows = pilot_on_time_df[pilot_on_time_df['SUBENTITY'] == current_subentity]
                
                if not matching_rows.empty and col_to_create in pilot_on_time_df.columns:
                    apc_time = matching_rows.iloc[0][col_to_create]
                    
                    if pd.isna(apc_time):
                        dt.loc[i, col_to_create] = "OFF"
                    elif apc_time >= current_data_time:
                        dt.loc[i, col_to_create] = "OFF"
                    else:
                        dt.loc[i, col_to_create] = "ON"
        
        # Create PILOT_STATUS column
        dt['PILOT_STATUS'] = dt.apply(self._create_pilot_status, axis=1)
        
        return dt
    
    def _create_pilot_status(self, row) -> str:
        """Create pilot status based on individual pilot columns"""
        # Check SRCIP first - if ON, return only "SRCIP"
        if row['SRCIP'] == "ON":
            return "SRCIP"
        
        # Otherwise, use the original logic
        if row['CCMR2'] == "OFF" and row['ICCR2'] == "OFF":
            base_status = "POR"
        elif row['CCMR2'] == "ON" and row['ICCR2'] == "OFF":
            base_status = "CCMR2"
        elif row['CCMR2'] == "OFF" and row['ICCR2'] == "ON":
            base_status = "ICCR2"
        elif row['CCMR2'] == "ON" and row['ICCR2'] == "ON":
            base_status = "CCMR2+ICCR2"
        else:
            base_status = "ERROR"
        
        # Add CV and/or GF suffixes
        cv_suffix = "+CV" if row['CV'] == "ON" else ""
        gf_suffix = "+GF" if row['GF'] == "ON" else ""
        
        return base_status + cv_suffix + gf_suffix
    
    def add_basic_columns(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add basic calculated columns"""
        self.logger.info("Creating basic calculated columns...")
        
        # Create SUM_NCDD column
        dt['SUM_NCDD'] = pd.to_numeric(dt['BEEP_NCDD'], errors='coerce').fillna(0) + \
                         pd.to_numeric(dt['SMP_NCDD'], errors='coerce').fillna(0)
        
        # Create STATUS column as categorical (existing logic)
        dt['STATUS'] = pd.Categorical(
            dt['SUM_NCDD'].apply(lambda x: 'BSL' if x < 0.02 else 'HIGHFLIER'),
            categories=['BSL', 'HIGHFLIER']
        )
        
        # Create CLASS column with three categories (NEW!)
        dt['CLASS'] = pd.Categorical(
            dt['SUM_NCDD'].apply(DataUtils.classify_sum_ncdd),
            categories=['ZERO', 'BSL', 'HIGHFLIER', 'UNKNOWN']
        )
        
        return dt
    
    def add_recoat_status(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Add recoat status columns"""
        self.logger.info("Loading parts info and adding RECOAT status columns...")
        
        parts_df = self.safe_load_csv(self.config.PARTS_PATH)
        if parts_df is None:
            self.logger.error("Failed to load parts data")
            return dt
        
        self.logger.info(f"Parts DataFrame shape: {parts_df.shape}")
        
        # Convert date columns to datetime
        parts_df = DataUtils.safe_datetime_convert(parts_df, 'PART_INSTALL_DATE')
        parts_df = DataUtils.safe_datetime_convert(parts_df, 'PART_REMOVE_DATE')
        
        # Initialize RECOAT status columns
        for part_type in self.config.PART_TYPES:
            dt[part_type] = 'NOTFOUND'
        
        # Process each row to determine RECOAT status
        self._process_recoat_status(dt, parts_df)
        
        # Create final RECOAT column
        dt['RECOAT'] = dt.apply(self._determine_final_recoat, axis=1)
        
        # Show summary
        self._show_recoat_summary(dt)
        
        return dt
    
    def _get_recoat_status_by_part(self, subentity: str, subentity_end_time, part_type: str, 
                                   parts_df: pd.DataFrame, debug: bool = False) -> str:
        """Get RECOAT status for a specific PART type"""
        if pd.isna(subentity_end_time) or pd.isna(subentity):
            if debug:
                self.logger.debug(f"Missing subentity or time: {subentity}, {subentity_end_time}")
            return 'NOTFOUND'
        
        # Filter parts data for this subentity and PART type
        entity_parts = parts_df[
            (parts_df['ENTITY'] == subentity) & 
            (parts_df['PART'] == part_type)
        ].copy()
        
        if debug:
            self.logger.debug(f"Entity parts found for {part_type}: {len(entity_parts)}")
        
        if entity_parts.empty:
            return 'NOTFOUND'
        
        matching_parts = []
        
        # Check currently installed parts first
        currently_installed = entity_parts[
            (entity_parts['CURRENTLY_INSTALLED'] == True) | 
            (entity_parts['CURRENTLY_INSTALLED'] == 'TRUE') |
            (entity_parts['CURRENTLY_INSTALLED'] == 'True')
        ]
        
        for _, part in currently_installed.iterrows():
            if pd.notna(part['PART_INSTALL_DATE']) and subentity_end_time > part['PART_INSTALL_DATE']:
                matching_parts.append(part)
        
        # Check previously installed parts
        previously_installed = entity_parts[
            (entity_parts['CURRENTLY_INSTALLED'] == False) | 
            (entity_parts['CURRENTLY_INSTALLED'] == 'FALSE') |
            (entity_parts['CURRENTLY_INSTALLED'] == 'False')
        ]
        
        for _, part in previously_installed.iterrows():
            if (pd.notna(part['PART_INSTALL_DATE']) and 
                pd.notna(part['PART_REMOVE_DATE']) and
                part['PART_INSTALL_DATE'] < subentity_end_time < part['PART_REMOVE_DATE']):
                matching_parts.append(part)
        
        if len(matching_parts) == 0:
            return 'NOTFOUND'
        elif len(matching_parts) == 1:
            # Special handling for LID - return INSTALL_COUNT instead of RECOAT
            if part_type == 'LID':
                install_count = matching_parts[0]['INSTALL_COUNT']
                return install_count if pd.notna(install_count) else 'MISSING'
            
            # Original logic for all other part types
            recoat_val = str(matching_parts[0]['RECOAT'])
            if recoat_val.upper() == 'TRUE':
                return 'True'
            elif recoat_val.upper() == 'FALSE':
                return 'False'
            else:
                return recoat_val
        else:
            # Special handling for LID - return most recent INSTALL_COUNT
            if part_type == 'LID':
                most_recent_part = max(matching_parts, key=lambda x: x['PART_INSTALL_DATE'] if pd.notna(x['PART_INSTALL_DATE']) else pd.Timestamp.min)
                install_count = most_recent_part['INSTALL_COUNT']
                return install_count if pd.notna(install_count) else 'MISSING'
            
            # Original logic for all other part types
            recoat_values = [part['RECOAT'] for part in matching_parts]
            
            if any(str(val).upper() == 'TRUE' for val in recoat_values):
                return 'True'
            elif any(str(val).upper() == 'MISSING' for val in recoat_values):
                return 'MISSING'
            elif all(str(val).upper() == 'FALSE' for val in recoat_values):
                return 'False'
            else:
                return 'MULTIPLE'
    
    def _process_recoat_status(self, dt: pd.DataFrame, parts_df: pd.DataFrame):
        """Process RECOAT status for each defect scan"""
        self.logger.info("Processing RECOAT status for each defect scan...")
        
        for idx in dt.index:
            row = dt.loc[idx]
            subentity = row['SUBENTITY']
            subentity_end_time = row['SUBENTITY_END_TIME']
            
            for part_type in self.config.PART_TYPES:
                recoat_status = self._get_recoat_status_by_part(
                    subentity, subentity_end_time, part_type, parts_df, debug=False
                )
                dt.at[idx, part_type] = recoat_status
    
    def _determine_final_recoat(self, row) -> bool:
        """Determine final RECOAT status"""
        recoat_values = [row[part_type] for part_type in self.config.PART_TYPES]
        return any(str(val).upper() == 'TRUE' for val in recoat_values)
    
    def _show_recoat_summary(self, dt: pd.DataFrame):
        """Show RECOAT processing summary"""
        self.logger.info(f"\nRECOAT Summary:")
        self.logger.info(f"Final RECOAT column: {dt['RECOAT'].value_counts()}")
        for part_type in self.config.PART_TYPES:
            self.logger.info(f"{part_type}: {dt[part_type].value_counts().to_dict()}")
    

    def _finalize_dataframe(self, dt: pd.DataFrame) -> pd.DataFrame:
        """Finalize dataframe with proper column ordering and sorting"""
        # Sort by SUBENTITY_END_TIME with most recent first
        dt = dt.sort_values('SUBENTITY_END_TIME', ascending=False)
        
        # Define desired column order
        elwc_lookback_cols = [f'{group}_{window}HRS' 
                             for group in self.config.RECIPE_GROUPS
                             for window in self.config.TIME_WINDOWS]
        
        leak_by_cols = [f'LB_{gas}' for gas in self.config.LEAK_BY_GASES]
        
        # SPC Monitor columns (raw, MA3, MA6, MA9)
        spc_monitor_cols = []
        for monitor_type in self.config.SPC_MONITOR_TYPES:
            spc_monitor_cols.extend([monitor_type, f'{monitor_type}_MA3', f'{monitor_type}_MA6', f'{monitor_type}_MA9'])
        
        desired_order = [
            'LOT', 'WAFER_ID', 'PRODUCT', 'LAYER', 'SUBENTITY', 'OPERATION','RECIPE', 
            'SUBENTITY_END_TIME','PILOT_STATUS',  'SUM_NCDD', 'STATUS', 'CLASS',  'INSPECT_TIME', 
            'INSPECT_TOOL', 'BEEP_NCDD', 'SMP_NCDD', 'ENTITY', 'LOT7', 'WAFER', 'SLOT', 'P_ORDER',
            'CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP', 'FULLPM', 'FULLPM_RF', 'MINIPM', 'MINIPM_RF', 
            'CNTR_SS', 'PL_RECIPE', 'PT_BTWN', 'PL_TIME', 'UPT_12HRS', 'UNW_12HRS', 'UP_12HRS'
        ] + self.config.PART_TYPES + ['RECOAT', 'RAW_LEAK_RATE', 'SMOOTH_LEAK_RATE', 'DP_FAIL_HRS'] + leak_by_cols + spc_monitor_cols + elwc_lookback_cols
        
        # Reorder columns
        existing_priority_cols = [col for col in desired_order if col in dt.columns]
        remaining_cols = [col for col in dt.columns if col not in desired_order]
        dt = dt[existing_priority_cols + remaining_cols]
        
        return dt
    
    def process(self) -> pd.DataFrame:
        """Main processing pipeline"""
        try:
            # Load and process base data
            dt = self.load_base_data()
            dt = self.clean_and_rename_columns(dt)
            dt = self.add_pilot_status(dt)
            dt = self.add_basic_columns(dt)
            dt = self.add_recoat_status(dt)
            
            # Add external data sources
            dt = self.leak_processor.add_leak_rate_data(dt)
            dt = self.dp_processor.add_dp_fail_data(dt)
            dt = self.leak_by_processor.add_leak_by_data(dt)
            dt = self.spc_monitor_processor.add_spc_monitor_data(dt)  # NEW!
            dt = self.elwc_processor.add_elwc_lookbacks(dt)
            
            # Finalize
            dt = self._finalize_dataframe(dt)
            
            self.logger.info("Processing complete!")
            self.logger.info(f"Final dataframe shape: {dt.shape}")
            
            return dt
            
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise


def main():
    """Main execution function with proper error handling"""
    try:
        # Install tqdm if not already available
        try:
            from tqdm import tqdm
        except ImportError:
            print("Installing tqdm for progress bars...")
            import subprocess
            subprocess.check_call(["pip", "install", "tqdm"])
        
        # Initialize configuration
        config = Config()
        
        # Process data
        processor = DefectDataProcessor(config)
        result_df = processor.process()
        
        # Save results
        result_df.to_csv(config.OUTPUT_PATH, index=False)
        logging.info(f"Processed data saved to: {config.OUTPUT_PATH}")
        
        # Show final summary
        logging.info(f"\nFinal enhanced dataframe shape: {result_df.shape}")
        
        # Show CLASS column distribution (NEW!)
        logging.info(f"\nCLASS column distribution:")
        logging.info(f"{result_df['CLASS'].value_counts()}")
        
        # Show sample of new SPC monitor columns (updated to include MA6 and MA9)
        spc_monitor_cols = [col for col in result_df.columns if any(monitor in col for monitor in ['ADDED_CLUSTERS', 'TOTAL_ADDERS'])]
        if spc_monitor_cols:
            logging.info(f"\nSample of SPC monitor columns (including MA6 and MA9):")
            logging.info(f"{result_df[['WAFER_ID', 'SUBENTITY'] + spc_monitor_cols[:8]].head()}")  # Show more columns
        
        # Show sample of leak by columns
        leak_by_cols = [col for col in result_df.columns if col.startswith('LB_')]
        if leak_by_cols:
            logging.info(f"\nSample of leak by columns:")
            logging.info(f"{result_df[['WAFER_ID', 'SUBENTITY'] + leak_by_cols[:6]].head()}")
        
        # Show sample of ELWC lookback columns
        elwc_cols = [col for col in result_df.columns if any(group in col for group in ['MONTW', '8GAB', '0GAB'])]
        if elwc_cols:
            logging.info(f"\nSample of ELWC lookback columns:")
            logging.info(f"{result_df[['WAFER_ID', 'OPERATION', 'SUBENTITY'] + elwc_cols[:6]].head()}")
        
        return result_df
        
    except Exception as e:
        logging.error(f"Main processing failed: {e}")
        raise


if __name__ == "__main__":
    main()
