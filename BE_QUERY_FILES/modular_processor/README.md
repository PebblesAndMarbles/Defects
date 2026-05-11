# Modular Defect Data Processor - Developer Guide

A modularized system for processing semiconductor defect data with ELWC lookbacks, leak rates, pump failures, defect trends, and SPC monitoring.

## 🎯 Quick Context Guide for New Chats

When starting a new chat for modifications, share this information in order of priority:

### Essential Context (Always Share)
1. **Brief description** of what you want to add/modify
2. **Core config** - `core/config.py` (shows all settings and data paths)
3. **Target processor** - The specific processor you want to modify

### Conditional Context (Share if Relevant)

| **If you want to...** | **Share these files** |
|----------------------|----------------------|
| Add new trend columns | `processors/defect_processor.py` + `core/column_manager.py` |
| Modify defect trends | `processors/defect_trends_processor.py` + `core/config.py` |
| Add new data source | `core/base_processors.py` + target processor |
| Modify ELWC logic | `processors/elwc_processor.py` |
| Add SPC features | `processors/spc_processor.py` |
| Change data validation | `core/utils.py` |
| Add new processor type | `core/base_processors.py` + `processors/defect_processor.py` |

## 📋 New Chat Template

```
CONTEXT: Modularized Defect Data Processor
GOAL: [Describe what you want to add/modify]

CURRENT STRUCTURE:
- Core infrastructure: config.py, base_processors.py, utils.py, column_manager.py
- Processors: defect_processor.py (main), elwc_processor.py, spc_processor.py, etc.
- Main entry: main.py

TARGET: [Which processor/module needs changes]

RELEVANT FILES:
[Paste the specific files mentioned in the table above]

REQUIREMENTS:
- [Any specific requirements or constraints]
- [Performance considerations]
- [Data compatibility needs]
```

## 🏗️ Project Structure

```
modular_processor/
├── main.py                         # Main execution script
├── README.md                       # This file
├── core/                           # Core infrastructure
│   ├── __init__.py
│   ├── config.py                  # Configuration management
│   ├── base_processors.py         # Base processor classes
│   ├── utils.py                   # Utility functions
│   └── column_manager.py          # Column management utilities
└── processors/                    # Data processors
    ├── __init__.py
    ├── defect_processor.py        # Main orchestrator
    ├── defect_trends_processor.py # Enhanced defect trend analysis (fleet + chamber)
    ├── elwc_processor.py          # ELWC lookback calculations
    ├── elwc2_processor.py         # ELWC2 production utilization (layer-specific + all-product)
    ├── leak_processors.py         # Leak rate and leak by data
    ├── pump_processor.py          # Dry pump failure data
    └── spc_processor.py           # SPC monitor time-based lookbacks
```

## 🔧 Common Modification Patterns

### Pattern 1: Adding New Trend Columns
**Files to share:**
- `processors/defect_processor.py` (specifically the `add_basic_columns` method)
- `core/column_manager.py` (if using helper functions)

**Example context:**
```
GOAL: Add rolling average columns for NCDD values over 7, 14, 30 day windows

TARGET: defect_processor.py - add_basic_columns method

REQUIREMENTS:
- Calculate rolling averages by SUBENTITY
- Handle missing data gracefully
- Add to final column ordering
```

### Pattern 2: Adding New Data Source
**Files to share:**
- `core/base_processors.py` (base classes)
- `processors/defect_processor.py` (integration point)
- `core/config.py` (new file paths)

### Pattern 3: Modifying Existing Processor
**Files to share:**
- Target processor file (e.g., `processors/spc_processor.py`)
- `core/config.py` (if new settings needed)

### Pattern 4: Modifying Defect Trends
**Files to share:**
- `processors/defect_trends_processor.py` (trend calculations)
- `core/config.py` (lookback windows, defect columns)

**Example context:**
```
GOAL: Modify defect trend lookback windows from [5,10,15] to [7,14,30] days

TARGET: defect_trends_processor.py + config.py

REQUIREMENTS:
- Update TREND_LOOKBACK_DAYS in config
- Ensure trend calculations handle new windows
- Validate coverage with longer lookbacks
```


## 🎯 Enhanced Defect Trends Processor

### Key Features (Added January 2026)
- **Dual-scope analysis**: Fleet-wide AND chamber-specific trend calculations with multi-chamber lot support
- **Comprehensive metrics**: Rate, absolute counts, and measured wafer counts (MWAF)
- **Expanding window fallback**: Uses available history when insufficient data for full lookback
- **Dynamic configuration**: Supports any lookback periods and defect types via config
- **Intelligent column ordering**: Prioritized by scope → period → metric type → defect type
- **Multi-chamber lot handling**: Separate trend calculations for each lot-chamber combination

### Generated Columns (Example: 8, 11, 17 day lookbacks)
```
CH_BP_08_RATE, CH_SP_08_RATE, CH_NC_08_RATE, CH_BP_08, CH_SP_08, CH_NC_08, CH_08_MWAF,
CH_BP_11_RATE, CH_SP_11_RATE, CH_NC_11_RATE, CH_BP_11, CH_SP_11, CH_NC_11, CH_11_MWAF,
CH_BP_17_RATE, CH_SP_17_RATE, CH_NC_17_RATE, CH_BP_17, CH_SP_17, CH_NC_17, CH_17_MWAF,
FL_BP_08_RATE, FL_SP_08_RATE, FL_NC_08_RATE, FL_BP_08, FL_SP_08, FL_NC_08, FL_08_MWAF,
FL_BP_11_RATE, FL_SP_11_RATE, FL_NC_11_RATE, FL_BP_11, FL_SP_11, FL_NC_11, FL_11_MWAF,
FL_BP_17_RATE, FL_SP_17_RATE, FL_NC_17_RATE, FL_BP_17, FL_SP_17, FL_NC_17, FL_17_MWAF
```

### Performance Metrics
- **Coverage**: 96.6% chamber trend coverage with proper multi-chamber lot handling
- **Scalability**: Processes 8,462 wafers in ~1.5 minutes
- **Data quality**: Only 3.4% NULL values (early lots with no history)

### Configuration Options
```python
# In core/config.py
TREND_LOOKBACK_DAYS = [8, 11, 17]  # Configurable lookback periods
TREND_DEFECT_COLS = ['ZERO_NCDD', 'ZERO_BEEP', 'ZERO_SMP']  # Defect types
TREND_USE_EXPANDING_WINDOW = True  # Enable expanding window fallback
TREND_MIN_HISTORY_LOTS = 1  # Minimum historical lots required
```

### Column Naming Convention
- **Scope**: `CH_` (chamber-specific) or `FL_` (fleet-wide)
- **Defect**: `BP` (BEEP), `SP` (SMP), `NC` (combined NCDD)
- **Period**: `08`, `11`, `17` (zero-padded lookback days)
- **Metric**: `_RATE` (defect rate), empty (absolute count), `_MWAF` (measured wafers)


## 🎯 Enhanced Defect Trends Processor

### Key Features (Added January 2026)
- **Dual-scope analysis**: Fleet-wide AND chamber-specific trend calculations with multi-chamber lot support
- **Comprehensive metrics**: Rate, absolute counts, and measured wafer counts (MWAF)
- **Chamber-to-fleet ratios**: Rate and defective count ratios for performance comparison
- **Expanding window fallback**: Uses available history when insufficient data for full lookback
- **Dynamic configuration**: Supports any lookback periods and defect types via config
- **Intelligent column ordering**: Prioritized by scope → period → metric type → defect type

### Generated Columns (Example: 8, 11, 17 day lookbacks)
```
# Chamber Trends
CH_BP_08_RATE, CH_SP_08_RATE, CH_NC_08_RATE, CH_BP_08, CH_SP_08, CH_NC_08, CH_08_MWAF,
CH_BP_11_RATE, CH_SP_11_RATE, CH_NC_11_RATE, CH_BP_11, CH_SP_11, CH_NC_11, CH_11_MWAF,
CH_BP_17_RATE, CH_SP_17_RATE, CH_NC_17_RATE, CH_BP_17, CH_SP_17, CH_NC_17, CH_17_MWAF,

# Fleet Trends
FL_BP_08_RATE, FL_SP_08_RATE, FL_NC_08_RATE, FL_BP_08, FL_SP_08, FL_NC_08, FL_08_MWAF,
FL_BP_11_RATE, FL_SP_11_RATE, FL_NC_11_RATE, FL_BP_11, FL_SP_11, FL_NC_11, FL_11_MWAF,
FL_BP_17_RATE, FL_SP_17_RATE, FL_NC_17_RATE, FL_BP_17, FL_SP_17, FL_NC_17, FL_17_MWAF

# Chamber-to-Fleet Ratios
CF_BP_08_RRAT, CF_SP_08_RRAT, CF_NC_08_RRAT, CF_BP_08_DRAT, CF_SP_08_DRAT, CF_NC_08_DRAT,
CF_BP_11_RRAT, CF_SP_11_RRAT, CF_NC_11_RRAT, CF_BP_11_DRAT, CF_SP_11_DRAT, CF_NC_11_DRAT,
CF_BP_17_RRAT, CF_SP_17_RRAT, CF_NC_17_RRAT, CF_BP_17_DRAT, CF_SP_17_DRAT, CF_NC_17_DRAT
```

### Performance Metrics
- **Coverage**: 96.6% chamber trend coverage with proper multi-chamber lot handling
- **Scalability**: Processes 8,462 wafers in ~1.5 minutes
- **Data quality**: Only 3.4% NULL values (early lots with no history)
- **Total columns**: 60 trend + ratio columns per dataset

### Configuration Options
```python
# In core/config.py
TREND_LOOKBACK_DAYS = [8, 11, 17]  # Configurable lookback periods
TREND_DEFECT_COLS = ['ZERO_NCDD', 'ZERO_BEEP', 'ZERO_SMP']  # Defect types
TREND_USE_EXPANDING_WINDOW = True  # Enable expanding window fallback
TREND_MIN_HISTORY_LOTS = 1  # Minimum historical lots required
```

### Column Naming Convention
- **Scope**: `CH_` (chamber-specific), `FL_` (fleet-wide), `CF_` (chamber-to-fleet ratio)
- **Defect**: `BP` (BEEP), `SP` (SMP), `NC` (combined NCDD)
- **Period**: `08`, `11`, `17` (zero-padded lookback days)
- **Metric**: `_RATE` (defect rate), `_RRAT` (rate ratio), `_DRAT` (defective ratio), `_MWAF` (measured wafers)

### Ratio Column Interpretation
- **RRAT (Rate Ratio)**: Chamber defect rate ÷ Fleet defect rate
  - `> 1.0`: Chamber performing worse than fleet average
  - `< 1.0`: Chamber performing better than fleet average
  - `= 0.0`: Fleet rate is zero (no fleet defects in period)
- **DRAT (Defective Ratio)**: Chamber defective count ÷ Fleet defective count
  - Indicates chamber's contribution to overall fleet defects
  - Useful for identifying high-impact problem chambers

### ML-Ready Features
- **NaN handling**: NaN values only when no historical data exists
- **MWAF context**: Measured wafer counts provide data quality context
- **Ratio features**: Enable chamber performance comparison in models
- **Layer-specific**: Trends calculated separately by layer for data integrity



## 🎯 Chamber-Level Aggregation Columns

### Key Features (Added January 2026)
- **S_SCAN**: Wafer count per LOT + LAYER + SUBENTITY combination (more granular than N_SCAN)
- **S_ORDER**: Average process order (P_ORDER) per LOT + LAYER + SUBENTITY combination
- **Defect rates**: Chamber-specific defect rates for BEEP, SMP, and NCDD by LOT + LAYER + SUBENTITY
- **Multi-chamber lot support**: Separate metrics for each chamber when lots run across multiple chambers

### Generated Columns
```
# Wafer counts and process order
N_SCAN,     # Wafers per LOT + LAYER (existing)
S_SCAN,     # Wafers per LOT + LAYER + SUBENTITY (new)
S_ORDER,    # Average P_ORDER per LOT + LAYER + SUBENTITY (new)

# Defect rates per LOT + LAYER + SUBENTITY
BP_RATE,    # BEEP defect rate (proportion of ZERO_BEEP = False)
SP_RATE,    # SMP defect rate (proportion of ZERO_SMP = False)
NC_RATE,    # NCDD defect rate (proportion of ZERO_NCDD = False)

# Lot-level ZERO columns (based on rate columns)
ZERO_BEEP_LOT,  # True when BP_RATE = 0 (no BEEP defects in LOT+LAYER+SUBENTITY)
ZERO_SMP_LOT,   # True when SP_RATE = 0 (no SMP defects in LOT+LAYER+SUBENTITY)
ZERO_NCDD_LOT,  # True when NC_RATE = 0 (no NCDD defects in LOT+LAYER+SUBENTITY)
```

### Use Cases
- **Multi-chamber lot analysis**: Compare performance across chambers for same lot
- **Chamber-specific defect rates**: Identify problematic chambers within lots
- **Process order analysis**: Understand wafer processing sequence effects
- **Granular aggregations**: More precise than lot-level, less noisy than wafer-level
- **Lot-level defect-free analysis**: Identify LOT+LAYER+SUBENTITY groups with zero defects

### Example Interpretation
```
LOT=ABC123, LAYER=8M5CL, SUBENTITY=AME409_PM4:
- S_SCAN=4     # 4 wafers from this lot ran on this chamber
- S_ORDER=12.5 # Average P_ORDER was 12.5 for these 4 wafers
- BP_RATE=0.5  # 2 out of 4 wafers had BEEP defects (ZERO_BEEP=False)
- SP_RATE=0.25 # 1 out of 4 wafers had SMP defects
- NC_RATE=0.75 # 3 out of 4 wafers had NCDD defects
- ZERO_BEEP_LOT=False  # At least one wafer in group had BEEP defects
- ZERO_SMP_LOT=True   # No wafers in group had SMP defects
- ZERO_NCDD_LOT=False # At least one wafer in group had NCDD defects
```




## 🐛 SPC Bug Fix (January 2026)

### Issue Resolved
**Problem**: Expanding window logic was inflating SPC counts and providing misleading averages

**Example of the bug**:
```
Expected: CH_SS_5_N = 0 (no measurements in 5-day window)
Actual:   CH_SS_5_N = 84 (all historical measurements counted)

Expected: CH_SS_5_TA = NaN (no data to average)
Actual:   CH_SS_5_TA = 2.008 (average of all 84 historical measurements)
```

### Root Cause
- **Expanding window fallback**: When no measurements found in time window, used ALL historical data
- **Count inflation**: Counted individual size records instead of unique measurement events
- **Misleading averages**: Historical averages presented as recent trends

### Solution Implemented
1. **Removed expanding window logic**: Strict adherence to time boundaries
2. **Fixed count calculation**: Count unique measurement events, not size records
3. **Honest NaN values**: Show NaN when insufficient data instead of historical fallback
4. **Data coverage strategy**: Ensure SPC dataset extends beyond longest lookback

### Impact
- **Accurate counts**: CH_SS_{n}_N now reflects true measurement frequency
- **Reliable averages**: CH_SS_{n}_TA only includes data from specified time window
- **Predictable behavior**: Lookback windows work as expected
- **Better data quality**: NaN values indicate genuine data sparsity

### Validation
```python
# Test case that revealed the bug:
Reference: 2025-11-25 06:12:32
5-day window: 2025-11-20 to 2025-11-25
Last measurement: 2025-11-19 (outside window)

Before fix: CH_SS_5_N = 84, CH_SS_5_TA = 2.008
After fix:  CH_SS_5_N = 0,  CH_SS_5_TA = NaN
```

## 🎯 Lot-Level ZERO Columns

### Key Features (Added January 2026)
- **Group-level defect detection**: Identifies LOT+LAYER+SUBENTITY groups with zero defects
- **Rate-based logic**: Uses defect rate columns (BP_RATE, SP_RATE, NC_RATE) for classification
- **Complementary to wafer-level**: Provides aggregated view alongside individual wafer ZERO columns
- **Higher zero percentages**: Groups are more likely to be defect-free than individual wafers

### Generated Columns
```
ZERO_BEEP_LOT   # True when BP_RATE = 0 (no BEEP defects in entire group)
ZERO_SMP_LOT    # True when SP_RATE = 0 (no SMP defects in entire group)
ZERO_NCDD_LOT   # True when NC_RATE = 0 (no NCDD defects in entire group)
```

### Logic Comparison
| **Column Type** | **Scope** | **True When** |
|----------------|-----------|---------------|
| `ZERO_BEEP` | Individual wafer | This wafer has no BEEP defects |
| `ZERO_BEEP_LOT` | LOT+LAYER+SUBENTITY | No wafers in group have BEEP defects |
| `ZERO_SMP` | Individual wafer | This wafer has no SMP defects |
| `ZERO_SMP_LOT` | LOT+LAYER+SUBENTITY | No wafers in group have SMP defects |
| `ZERO_NCDD` | Individual wafer | This wafer has no NCDD defects |
| `ZERO_NCDD_LOT` | LOT+LAYER+SUBENTITY | No wafers in group have NCDD defects |

### Use Cases
- **Chamber performance analysis**: Identify chambers consistently producing defect-free groups
- **Lot quality assessment**: Find lots with chambers that produced zero defects
- **Process optimization**: Target process conditions that yield defect-free groups
- **ML feature engineering**: Group-level defect-free indicators for modeling

### Expected Statistics
```
# Lot-level ZERO columns typically have higher True percentages
# because entire groups are more likely to be defect-free than individual wafers

Example comparison:
ZERO_BEEP: 76.2% True (individual wafers)
ZERO_BEEP_LOT: 85%+ True (LOT+LAYER+SUBENTITY groups)
```

## 🎯 Lot-Level CSV Output

### Key Features (Added January 2026)
- **Dual output**: Generates both wafer-level and lot-level CSV files
- **Intelligent grouping**: Groups by LAYER, LOT, SUBENTITY combinations
- **Most recent selection**: Uses latest SUBENTITY_END_TIME per group
- **Column preservation**: Retains all columns from selected wafer
- **Configurable**: Can be enabled/disabled via configuration flag

### Output Files
```
# Wafer-level output (existing)
8M5CL_8M6CL_2025.csv        # One row per wafer

# Lot-level output (new)
8M5CL_8M6CL_2025_LOT.csv    # One row per LOT+LAYER+SUBENTITY combination
```

### Grouping Logic
- **Primary grouping**: `['LAYER', 'LOT', 'SUBENTITY']`
- **Selection criteria**: Most recent `SUBENTITY_END_TIME` within each group
- **Fallback**: If timestamp missing, uses last row per group
- **Data preservation**: All columns retained from selected wafer

### Use Cases
- **Lot-level analysis**: Analyze performance at lot granularity
- **Multi-chamber lot tracking**: One record per chamber that processed the lot
- **Reduced data volume**: Smaller dataset for high-level trend analysis
- **Chamber utilization**: Track which chambers processed which lots

### Performance Impact
```
Example reduction: 307 wafer-level rows → 116 lot-level rows
- Unique layers: 2 (8M5CL, 8M6CL)
- Unique lots: 62
- Unique subentities: 39 chambers
- Processing time: ~14 seconds additional
```

### Configuration
```python
# In core/config.py
ENABLE_LOT_LEVEL_OUTPUT: bool = True
LOT_LEVEL_OUTPUT_PATH = r"path\to\output\LOT.csv"
```


## 🎯 Lot-Level CSV Output

### Key Features (Added January 2026)
- **Dual output**: Generates both wafer-level and lot-level CSV files
- **Intelligent grouping**: Groups by LAYER, LOT, SUBENTITY combinations
- **Most recent selection**: Uses latest SUBENTITY_END_TIME per group
- **Column preservation**: Retains all columns from selected wafer
- **Configurable**: Can be enabled/disabled via configuration flag

### Output Files
```
# Wafer-level output (existing)
8M5CL_8M6CL_2025.csv        # One row per wafer

# Lot-level output (new)
8M5CL_8M6CL_2025_LOT.csv    # One row per LOT+LAYER+SUBENTITY combination
```

### Grouping Logic
- **Primary grouping**: `['LAYER', 'LOT', 'SUBENTITY']`
- **Selection criteria**: Most recent `SUBENTITY_END_TIME` within each group
- **Fallback**: If timestamp missing, uses last row per group
- **Data preservation**: All columns retained from selected wafer

### Use Cases
- **Lot-level analysis**: Analyze performance at lot granularity
- **Multi-chamber lot tracking**: One record per chamber that processed the lot
- **Reduced data volume**: Smaller dataset for high-level trend analysis
- **Chamber utilization**: Track which chambers processed which lots

### Performance Impact
```
Example reduction: 307 wafer-level rows → 116 lot-level rows
- Unique layers: 2 (8M5CL, 8M6CL)
- Unique lots: 62
- Unique subentities: 39 chambers
- Processing time: ~14 seconds additional
```

### Configuration
```python
# In core/config.py
ENABLE_LOT_LEVEL_OUTPUT: bool = True
LOT_LEVEL_OUTPUT_PATH = r"path\to\output\LOT.csv"
```

## 🎯 ELWC2 Production Utilization Processor

### Key Features (Added January 2026)
- **Layer-specific wafer counts (NWAF)**: Counts wafers matching specific layer patterns (8M5CL, 8M6CL)
- **All-product wafer counts (AWAF)**: Counts all production wafers (excluding MONTW)
- **Chamber and fleet metrics**: Both CH_ and FL_ variants for comprehensive analysis
- **Configurable lookback periods**: Uses `ELWC2_LOOKBACKS` in days instead of hours
- **Optimized caching**: O(1) wafer lookups and pre-sorted chamber/fleet data
- **Precise layer detection**: Uses 'M5'/'MT5' and 'M6'/'MT6' patterns for accurate classification
- **Predictive features**: Excludes current lot for ML model compatibility

### Generated Columns (Example: 1, 3, 7, 14, 30 day lookbacks)
```
# Layer-Specific Wafer Counts (NWAF)
CH_01_NWAF, FL_01_NWAF,  # 1-day lookback
CH_03_NWAF, FL_03_NWAF,  # 3-day lookback
CH_07_NWAF, FL_07_NWAF,  # 7-day lookback
CH_14_NWAF, FL_14_NWAF,  # 14-day lookback
CH_30_NWAF, FL_30_NWAF,  # 30-day lookback

# All-Product Wafer Counts (AWAF)
CH_01_AWAF, FL_01_AWAF,  # 1-day lookback
CH_03_AWAF, FL_03_AWAF,  # 3-day lookback
CH_07_AWAF, FL_07_AWAF,  # 7-day lookback
CH_14_AWAF, FL_14_AWAF,  # 14-day lookback
CH_30_AWAF, FL_30_AWAF,  # 30-day lookback
```

### Performance Metrics
- **Coverage**: 100% successful matches (8,284/8,284 wafers)
- **Processing time**: ~12.4 minutes for 8,284 wafers
- **Layer detection accuracy**: 88,956 8M5CL + 85,660 8M6CL wafers identified
- **Data quality**: No NULL values, all lookbacks successfully calculated

### Configuration Options
```python
# In core/config.py
ENABLE_ELWC2 = True  # Enable/disable ELWC2 processor
ELWC2_LOOKBACKS = [1, 3, 7, 14, 30]  # Lookback periods in DAYS
```

### Column Naming Convention
- **Scope**: `CH_` (chamber-specific) or `FL_` (fleet-wide)
- **Period**: `01`, `03`, `07`, `14`, `30` (zero-padded lookback days)
- **Metric**: `_NWAF` (layer-specific wafer count) or `_AWAF` (all-product wafer count)

### Layer Detection Logic
- **8M5CL**: Operations containing 'M5' or 'MT5' patterns
- **8M6CL**: Operations containing 'M6' or 'MT6' patterns
- **Technology filter**: Only 1278 technology wafers (4th char = '8')
- **Production filter**: Excludes MONTW (test/monitor wafers)

### Use Cases
- **Chamber utilization analysis**: Compare chamber vs fleet production levels
- **Layer-specific trends**: Track specific layer activity over time
- **ML feature engineering**: Predictive features for defect modeling
- **Production planning**: Historical utilization patterns for scheduling

### Data Sources
- **Source**: Same ELWC dataset as original ELWC processor
- **Wafer identification**: Uses WAFER + OPERATION matching
- **Time reference**: Uses START_DATETIME from ELWC data
- **Chamber mapping**: Uses SUBENTITY for chamber-specific calculations


## 🎯 SPC Monitor Time-Based Lookback Processor

### Key Features (Updated January 2026)
- **Time-based lookbacks**: Replaced MA3/MA6/MA9 point-based averages with configurable day-based lookbacks
- **Chamber and fleet metrics**: Both CH_ and FL_ variants for comprehensive surface scan analysis
- **Automated classification**: Applies existing control limits to chamber averages (4-level for TA/LA, 3-level for AC/CA)
- **Expanding window fallback**: Uses available history when insufficient data for full lookback period
- **Optimized caching**: Pre-sorted chamber/fleet data for efficient time-window filtering
- **Measurement recency tracking**: Single CH_SS_DAYS column (eliminates redundant size-specific columns)
- **Surface scan grouping**: Groups by SUBENTITY and SIZE within lookback windows

### Generated Columns (Example: 5, 10, 15 day lookbacks)
```
# Chamber-Specific Metrics (with classification)
CH_SS_5_TA, CH_SS_5_TA_CLASS,    # Total Adders average + classification
CH_SS_5_LA, CH_SS_5_LA_CLASS,    # Large Adders average + classification
CH_SS_5_AC, CH_SS_5_AC_CLASS,    # Added Clusters average + classification
CH_SS_5_CA, CH_SS_5_CA_CLASS,    # Added Cluster Area average + classification
CH_SS_5_N,                       # Chamber measurement count in period

# Fleet-Specific Metrics (averages only, no classification)
FL_SS_5_TA, FL_SS_5_LA, FL_SS_5_AC, FL_SS_5_CA,  # Fleet averages
FL_SS_5_N,                                        # Fleet measurement count

# Measurement Recency
CH_SS_DAYS                       # Days since last SS measurement (any size)
```

### Performance Metrics
- **Coverage**: 100% successful matches (1,075/1,075 wafers)
- **Processing time**: ~54.4 seconds (0.9 minutes) for 1,075 wafers
- **Chamber coverage**: 53 chambers with 15,552 total SS measurements
- **Data quality**: Average 23.3 measurements per 5-day lookback window
- **Date range**: Nov 30, 2024 to Dec 30, 2025

### Control Limit Classifications
```python
# 4-level classification (TOTAL_ADDERS, LARGE_ADDERS)
# 0 = Zero, 1 = Low (≤ centerline), 2 = Medium (≤ upper_limit), 3 = High/OOC

# 3-level classification (ADDED_CLUSTERS, ADDED_CLUSTER_AREA)
# 0 = Zero, 1 = Normal (≤ upper_limit), 2 = High/OOC

# Example distribution (5-day lookback):
# TOTAL_ADDERS: 28.6% Zero, 6.0% Low, 58.6% Medium, 6.9% High/OOC
# LARGE_ADDERS: 40.9% Zero, 7.5% Low, 49.2% Medium, 2.3% High/OOC
# ADDED_CLUSTERS/AREA: 65.3% Zero, 34.6% Normal, 0.1% High/OOC
```

### Configuration Options
```python
# In core/config.py
ENABLE_SPC_MONITOR = True
SPC_LOOKBACKS = [5, 10, 15, 30]  # Lookback periods in DAYS
```

### Column Naming Convention
- **Scope**: `CH_` (chamber-specific) or `FL_` (fleet-wide)
- **Period**: `5`, `10`, `15`, `30` (lookback days)
- **Size**: `TA` (Total Adders), `LA` (Large Adders), `AC` (Added Clusters), `CA` (Added Cluster Area)
- **Suffix**: `_CLASS` (classification), `_N` (count), `_DAYS` (recency)

### Key Improvements Over Previous Version
- **Time-based vs Point-based**: Lookbacks use actual time windows instead of fixed number of measurements
- **Fleet context**: Added fleet-wide averages for performance comparison
- **Simplified recency**: Single CH_SS_DAYS column (measurements are simultaneous across sizes)
- **Expanding windows**: Uses available history for early measurements
- **Optimized performance**: Pre-sorted caches for efficient time-window filtering

### Use Cases
- **Chamber performance monitoring**: Compare chamber vs fleet surface scan levels
- **Control chart analysis**: Automated out-of-control detection using existing limits
- **Trend analysis**: Time-based surface scan particle trends
- **ML feature engineering**: Predictive features for defect modeling
- **Process optimization**: Historical surface scan patterns for chamber maintenance

### Data Sources
- **Source**: SPC_SS.csv (preprocessed surface scan measurements)
- **Measurement matching**: Uses SUBENTITY + SUBENTITY_END_TIME for lookbacks
- **Time reference**: Uses DATE from SPC measurements
- **Grouping**: By SUBENTITY (chamber) and SIZE (particle type)

## 🚀 Development Workflow

### Phase 1: Planning (New Chat Start)
1. Share context using template above
2. Get implementation plan and file modifications
3. Validate approach before coding

### Phase 2: Implementation
1. Make changes to suggested files
2. Test individual components if possible
3. Share any errors or unexpected behavior

### Phase 3: Validation (Follow-up Chat)
**Share for validation:**
- Modified files (only the changed parts)
- Test results or error messages
- Sample output showing new functionality

**Validation template:**
```
UPDATE: [Brief description of changes made]

MODIFIED FILES:
- [List files changed]

STATUS: [Working/Error/Partial]

VALIDATION NEEDED:
- [What you want me to check]
- [Any concerns or questions]

[Paste relevant code sections or error messages]
```

## 📁 File Dependency Map

```
main.py
├── core/config.py (settings)
processors/defect_processor.py (orchestrator + lot-level output)
    ├── core/base_processors.py (base classes)
    ├── core/utils.py (utilities)
    ├── core/column_manager.py (column operations)
    ├── processors/defect_trends_processor.py
    ├── processors/elwc_processor.py
    ├── processors/spc_processor.py
    ├── processors/leak_processors.py
    └── processors/pump_processor.py
```

## 🔍 Quick Reference: What File Does What

| **File** | **Purpose** | **When to Modify** |
|----------|-------------|-------------------|
| `core/config.py` | Settings, paths, flags | Adding new data sources, changing behavior |
| `core/base_processors.py` | Base classes, common patterns | Adding new processor types |
| `core/utils.py` | Utility functions | Adding data validation, helper functions |
| `core/column_manager.py` | Column operations | Adding column creation patterns |
| `processors/defect_processor.py` | Main orchestrator | Adding new processing steps, trend columns |
| `processors/defect_trends_processor.py` | Enhanced defect trends (fleet + chamber) | Modifying lookback windows, trend calculations, column ordering |
| `processors/elwc_processor.py` | ELWC lookbacks | Modifying recipe classification, time windows |
| `processors/spc_processor.py` | SPC time-based lookbacks | Modifying lookback periods, control limits, surface scan analysis |
| `processors/leak_processors.py` | Leak rate & leak by | Adding new gas types, leak analysis |
| `processors/pump_processor.py` | Dry pump failures | Modifying failure detection logic |
| `main.py` | Entry point | Changing execution flow, configuration |

## 🎯 Specific Examples

### Example 1: Adding Trend Columns
**New chat context:**
```
GOAL: Add 7-day rolling average of SUM_NCDD by SUBENTITY
TARGET: defect_processor.py - add_basic_columns method
FILES NEEDED: processors/defect_processor.py, core/column_manager.py
```

### Example 2: New SPC Feature
**New chat context:**
```
GOAL: Add control chart violations detection to SPC processor
TARGET: processors/spc_processor.py
FILES NEEDED: processors/spc_processor.py, core/config.py (for thresholds)
```

### Example 3: New Data Source Integration
**New chat context:**
```
GOAL: Add chamber temperature data processor
TARGET: Create new processor + integrate in defect_processor.py
FILES NEEDED: core/base_processors.py, processors/defect_processor.py, core/config.py
```

## ⚡ Efficiency Tips

1. **Start specific**: "Add rolling averages" vs "improve data analysis"
2. **Share minimal context**: Only relevant files, not entire codebase
3. **Use code snippets**: Share specific methods/classes, not whole files
4. **Test incrementally**: Validate small changes before big ones
5. **Document assumptions**: Share any constraints or requirements upfront

## 🛠️ Usage Examples

### Basic Usage
```python
from core.config import Config
from processors.defect_processor import DefectDataProcessor

# Configure processing
config = Config(
    ENABLE_ELWC=True,
    ENABLE_ELWC2=True,
    ENABLE_LEAK_RATE=True,
    ENABLE_DRY_PUMP=True,
    ENABLE_DEFECT_TRENDS=True,
    ENABLE_DATE_FILTER=True,
    START_DATE="2025-11-01",
    END_DATE="2025-12-01"
)

# Process data
processor = DefectDataProcessor(config)
result_df = processor.process()
# Lot-level CSV automatically generated if ENABLE_LOT_LEVEL_OUTPUT=True
# Lot-level CSV automatically generated if ENABLE_LOT_LEVEL_OUTPUT=True
```

### Testing Individual Processors
```python
# Test SPC processor independently
from core.config import Config
from processors.spc_processor import SPCMonitorProcessor

config = Config()
spc_processor = SPCMonitorProcessor(config)
# Test with sample data...
```

## 🔧 Configuration Options

### Processor Control Flags
- `ENABLE_ELWC`: Enable/disable ELWC lookback calculations
- `ENABLE_ELWC2`: Enable/disable ELWC2 production utilization calculations
- `ENABLE_LEAK_RATE`: Enable/disable leak rate processing
- `ENABLE_DRY_PUMP`: Enable/disable dry pump failure analysis
- `ENABLE_LEAK_BY`: Enable/disable gas-specific leak by analysis
- `ENABLE_SPC_MONITOR`: Enable/disable SPC monitor time-based lookbacks
- `ENABLE_RECOAT`: Enable/disable recoat status analysis
- `ENABLE_DEFECT_TRENDS`: Enable/disable defect trend lookback analysis

### Performance Options
- `ENABLE_DATE_FILTER`: Filter data by date range for faster iteration
- `START_DATE` / `END_DATE`: Date range for filtering



### Lot-Level Output Options
- `ENABLE_LOT_LEVEL_OUTPUT`: Enable/disable lot-level CSV output (grouped by LAYER, LOT, SUBENTITY)
- `LOT_LEVEL_OUTPUT_PATH`: File path for lot-level CSV output
### Lot-Level Output Options
- `ENABLE_LOT_LEVEL_OUTPUT`: Enable/disable lot-level CSV output (grouped by LAYER, LOT, SUBENTITY)
- `LOT_LEVEL_OUTPUT_PATH`: File path for lot-level CSV output
### SPC Configuration
- `SPC_LOOKBACKS`: Time-based lookback periods in days (e.g., [5, 10, 15, 30])

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're running from the modular_processor directory
2. **Config Errors**: Check that all file paths in config.py are accessible
3. **Memory Issues**: Use date filtering for large datasets
4. **Double Execution**: Check for duplicate `if __name__ == "__main__":` blocks

### Debug Mode
Add debug logging to any processor:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Data Flow

```
Raw Data Files
     ↓
DefectDataProcessor.load_base_data()
     ↓
DefectDataProcessor.clean_and_rename_columns()
     ↓
DefectDataProcessor.add_pilot_status()
     ↓
DefectDataProcessor.add_basic_columns()
     ↓
DefectTrendsProcessor (if enabled)
     ↓
Individual Processors (ELWC, SPC, Leak, etc.)
     ↓
DefectDataProcessor._finalize_dataframe()
     ↓
Final Wafer-Level Output CSV
     ↓
DefectDataProcessor.create_lot_level_output() (if enabled)
     ↓
Final Lot-Level Output CSV
```

## 🚀 Performance Considerations

- **Date Filtering**: Use `ENABLE_DATE_FILTER` for faster iteration during development
- **Processor Selection**: Disable unused processors with config flags
- **Memory Management**: Large datasets benefit from the built-in batch processing
- **Caching**: Time-based processors use caching for repeated lookups

## 📝 Contributing Guidelines

1. **Follow the modular pattern**: New functionality should extend existing processors or create new ones
2. **Use base classes**: Inherit from `ProcessorBase` or `TimeBasedLookupProcessor`
3. **Update configuration**: Add new settings to `Config` class
4. **Document changes**: Update this README when adding new features
5. **Test incrementally**: Validate changes with small datasets first

---

**Last Updated**: January 2026
**Version**: 1.5.2 (Enhanced Defect Trends + Multi-Chamber Fix + NCDD Naming + Ratios + ELWC2 + SPC Time-Based Lookbacks + Chamber-Level Aggregations)
**Maintainer**: tbatson