"""
FLEET RATE CALCULATION ANALYSIS
================================

Question: Are BEEP_FLEET_RATE and SMP_FLEET_RATE filtered by device-level sample size
          (keeping only devices with >= 10 wafers), or are they calculated from ALL records
          in the sample period?

ANSWER: FLEET rates are calculated from ALL records - they are NOT filtered by min_samples.
=========================================================================

EXPLANATION:

1. FLEET RATE CALCULATION (TIME_BIN_AGGREGATOR.py, lines 135-154)
   
   Location: calculate_fleet_baselines_with_elwc() function
   
   For each period and layer:
   
       layer_data = period_data[period_data['LAYER'] == layer]
       
       beep_defective = (layer_data['ZERO_BEEP'] == False).sum()
       smp_defective = (layer_data['ZERO_SMP'] == False).sum()
       total_wafers = len(layer_data)
       
       BEEP_FLEET_RATE = beep_defective / total_wafers
       SMP_FLEET_RATE = smp_defective / total_wafers
   
   This uses period_data which contains ALL records for the layer in that time period,
   BEFORE any device-level filtering.

2. FLOW SEQUENCE (TIME_BIN_AGGREGATOR.py, lines 249-275)
   
   Step 1: Calculate fleet baselines from ALL data (line 249)
           fleet_baselines = calculate_fleet_baselines_with_elwc(df, elwc_df, periods, n_days)
   
           This happens FIRST, using ALL records regardless of device-level sample size
   
   Step 2: Filter device-layer rows by min_samples (lines 268-271)
           
           for _, combo in device_layer_combos.iterrows():
               device = combo['DEVICE']
               layer = combo['LAYER']
               group_df = df[(df['DEVICE'] == device) & (df['LAYER'] == layer)]
               
               for period_start, period_end in periods:
                   period_data = group_df[...]
                   
                   if len(period_data) < min_samples:  # <-- SKIP if device-level < 10
                       continue

   KEY INSIGHT: The fleet baseline is calculated BEFORE checking min_samples.
                So even if a specific device has < 10 wafers, it is INCLUDED in the
                fleet calculation, and then device rows are filtered out afterwards.

3. IMPLICATION FOR DATA INTERPRETATION
   
   Row = Device X, Layer 8M5CL, Week 1, Sample Size = 5 wafers
   
   Status: This row would be SKIPPED (< 10 min_samples)
   
   Row = Device Y, Layer 8M5CL, Week 1, Sample Size = 25 wafers
   
   BEEP_FLEET_RATE for this row = (total BEEP defects in all devices, layer 8M5CL, week 1) 
                                  / (total wafers all devices, layer 8M5CL, week 1)
   
   This INCLUDES the 5 wafers from Device X in the fleet calculation,
   even though Device X's own row was filtered out.

4. IS THIS CORRECT?
   
   YES - This is the desired behavior for fleet benchmarking:
   
   ✓ Device-level results are only shown when sufficiently sampled (>= 10)
   ✓ Fleet baseline reflects TRUE fleet-wide performance (all wafers)
   ✓ Not biased by selecting only high-sample-count devices
   ✓ Allows fair comparison: "Device Y's 25 wafers vs fleet (including low-sample devices)"

5. VERIFICATION
   
   To confirm this behavior, check:
   
   a) Fleet CSV output columns:
      - SAMPLE_SIZE: Shows device-level wafer count (will be >= min_samples for rows in output)
      - FLEET_WAFERS: Shows total fleet wafers used for baseline calc
                     (Should be >= SAMPLE_SIZE, typically much higher)
      - BEEP_FLEET_RATE: Fleet-wide rate (from all wafers, not filtered)
   
   b) Expected relationship:
      FLEET_WAFERS > SAMPLE_SIZE for most rows
      (because fleet includes all devices, not just those with sufficient data)
   
   c) Sample size distribution:
      Some devices may have sample sizes like: 5, 8, 12, 25, 30
      But fleet baselines consistently use same FLEET_WAFERS value for given period-layer
      (because all raw data is included, regardless of individual device sample size)

CONCLUSION:
===========
BEEP_FLEET_RATE and SMP_FLEET_RATE are genuinely calculated based on ALL records 
within the sample period for that layer. They are NOT filtered by device-level 
min_samples threshold. This ensures fleet metrics represent true fleet performance
while device metrics are thresholded for statistical significance.
"""

print(__doc__)
