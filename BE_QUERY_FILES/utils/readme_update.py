"""
Script to update README.md with SPC expanding window removal and strict time boundaries
"""

from pathlib import Path

def update_readme_with_spc_strict_windows():
    """Update README.md with SPC strict time window functionality"""
    
    # Target directory
    target_dir = Path(r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\modular_processor")
    readme_path = target_dir / "README.md"
    
    # Read existing README as lines
    with open(readme_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Convert to list of strings (remove newlines)
    content_lines = [line.rstrip('\n') for line in lines]
    
    # Update specific sections
    for i, line in enumerate(content_lines):
        
        # Update version number
        if "**Version**: 1.5.4 (Enhanced Defect Trends + Multi-Chamber Fix + NCDD Naming + Ratios + ELWC2 + SPC Time-Based Lookbacks + Chamber-Level Aggregations + Lot-Level Output + Lot-Level ZERO Columns)" in line:
            content_lines[i] = "**Version**: 1.5.5 (Enhanced Defect Trends + Multi-Chamber Fix + NCDD Naming + Ratios + ELWC2 + SPC Strict Time Windows + Chamber-Level Aggregations + Lot-Level Output + Lot-Level ZERO Columns)"
        
        # Update SPC section title to reflect strict windows
        if "## 🔬 SPC Monitor Time-Based Lookbacks" in line:
            content_lines[i] = "## 🔬 SPC Monitor Strict Time Windows"
        
        # Update SPC key features to remove expanding window references
        if "- **Expanding window fallback**: Uses all available history when insufficient recent data" in line:
            content_lines[i] = "- **Strict time boundaries**: Only uses measurements within specified lookback windows"
        
        # Update SPC behavior description
        if "- **Smart fallback logic**: Expands to full history when lookback window is empty" in line:
            content_lines[i] = "- **Honest NaN handling**: Returns NaN for averages when no measurements exist in window"
    
    # Find and update the SPC lookback logic section
    for i, line in enumerate(content_lines):
        if "### SPC Lookback Logic" in line:
            # Replace the entire logic section
            logic_section = [
                "### SPC Lookback Logic (Updated January 2026)",
                "",
                "**Strict Time Window Approach**:",
                "1. **Define lookback window**: `reference_time - lookback_days` to `reference_time`",
                "2. **Filter measurements**: Only include SPC measurements within exact time window",
                "3. **Calculate metrics**:",
                "   - **Count**: Number of unique measurement events (not size records)",
                "   - **Average**: Mean of particle values within window",
                "4. **Handle empty windows**:",
                "   - **Counts**: Set to 0 (no measurements in window)",
                "   - **Averages**: Set to NaN (cannot calculate average)",
                "   - **No expanding window**: No fallback to historical data",
                "",
                "**Key Improvements**:",
                "- **Accurate counts**: CH_SS_5_N = 0 when no measurements in 5-day window",
                "- **Honest averages**: CH_SS_5_TA = NaN when no data to average",
                "- **Predictable behavior**: Lookback windows mean exactly what they specify",
                "- **No inflation**: Removed bug that counted 84 instead of 0",
                "",
                "**Example Scenario**:",
                "```",
                "Reference time: 2025-11-25 06:12:32",
                "5-day lookback: 2025-11-20 06:12:32 to 2025-11-25 06:12:32",
                "Last SPC measurement: 2025-11-19 12:01:47 (outside window)",
                "",
                "Results:",
                "CH_SS_5_N: 0      # Correct: no measurements in 5-day window",
                "CH_SS_5_TA: NaN   # Correct: no data to average",
                "CH_SS_DAYS: 6.26  # Correct: days since last measurement",
                "```",
                "",
            ]
            
            # Find the end of the current logic section and replace it
            end_idx = i + 1
            while end_idx < len(content_lines) and not content_lines[end_idx].startswith("###") and not content_lines[end_idx].startswith("##"):
                end_idx += 1
            
            content_lines = content_lines[:i] + logic_section + content_lines[end_idx:]
            break
    
    # Update the SPC data requirements section
    for i, line in enumerate(content_lines):
        if "### SPC Data Requirements" in line:
            # Add note about data coverage requirements
            for j in range(i+1, min(i+15, len(content_lines))):
                if "- Particle sizes: TOTAL_ADDERS, LARGE_ADDERS, ADDED_CLUSTERS, ADDED_CLUSTER_AREA" in content_lines[j]:
                    new_requirements = [
                        "- **Data coverage**: SPC dataset must extend beyond longest lookback window",
                        "- **No expanding window**: Insufficient coverage results in NaN values",
                        "- **Recommendation**: Ensure SPC data goes back further than max lookback days",
                    ]
                    content_lines = content_lines[:j+1] + new_requirements + content_lines[j+1:]
                    break
            break
    
    # Update the SPC column examples to show NaN handling
    for i, line in enumerate(content_lines):
        if "CH_SS_5_TA: 2.34    # Chamber average TOTAL_ADDERS (5-day)" in line:
            content_lines[i] = "CH_SS_5_TA: 2.34    # Chamber average TOTAL_ADDERS (5-day), NaN if no data"
        
        if "CH_SS_5_N: 12       # Count of measurements (5-day)" in line:
            content_lines[i] = "CH_SS_5_N: 12       # Count of measurements (5-day), 0 if no data"
        
        if "FL_SS_5_TA: 1.89    # Fleet average TOTAL_ADDERS (5-day)" in line:
            content_lines[i] = "FL_SS_5_TA: 1.89    # Fleet average TOTAL_ADDERS (5-day), NaN if no data"
    
    # Add new section about the bug fix
    for i, line in enumerate(content_lines):
        if "## 🎯 Lot-Level ZERO Columns" in line:
            # Insert bug fix section before lot-level columns
            bug_fix_section = [
                "",
                "## 🐛 SPC Bug Fix (January 2026)",
                "",
                "### Issue Resolved",
                "**Problem**: Expanding window logic was inflating SPC counts and providing misleading averages",
                "",
                "**Example of the bug**:",
                "```",
                "Expected: CH_SS_5_N = 0 (no measurements in 5-day window)",
                "Actual:   CH_SS_5_N = 84 (all historical measurements counted)",
                "",
                "Expected: CH_SS_5_TA = NaN (no data to average)",
                "Actual:   CH_SS_5_TA = 2.008 (average of all 84 historical measurements)",
                "```",
                "",
                "### Root Cause",
                "- **Expanding window fallback**: When no measurements found in time window, used ALL historical data",
                "- **Count inflation**: Counted individual size records instead of unique measurement events",
                "- **Misleading averages**: Historical averages presented as recent trends",
                "",
                "### Solution Implemented",
                "1. **Removed expanding window logic**: Strict adherence to time boundaries",
                "2. **Fixed count calculation**: Count unique measurement events, not size records",
                "3. **Honest NaN values**: Show NaN when insufficient data instead of historical fallback",
                "4. **Data coverage strategy**: Ensure SPC dataset extends beyond longest lookback",
                "",
                "### Impact",
                "- **Accurate counts**: CH_SS_{n}_N now reflects true measurement frequency",
                "- **Reliable averages**: CH_SS_{n}_TA only includes data from specified time window",
                "- **Predictable behavior**: Lookback windows work as expected",
                "- **Better data quality**: NaN values indicate genuine data sparsity",
                "",
                "### Validation",
                "```python",
                "# Test case that revealed the bug:",
                "Reference: 2025-11-25 06:12:32",
                "5-day window: 2025-11-20 to 2025-11-25",
                "Last measurement: 2025-11-19 (outside window)",
                "",
                "Before fix: CH_SS_5_N = 84, CH_SS_5_TA = 2.008",
                "After fix:  CH_SS_5_N = 0,  CH_SS_5_TA = NaN",
                "```",
                "",
            ]
            content_lines = content_lines[:i] + bug_fix_section + content_lines[i:]
            break
    
    # Update the main processing flow to mention strict windows
    for i, line in enumerate(content_lines):
        if "4. **SPC Monitor Integration**: Time-based lookbacks with expanding window fallback" in line:
            content_lines[i] = "4. **SPC Monitor Integration**: Strict time-based lookbacks with accurate counting"
    
    # Update any remaining expanding window references
    for i, line in enumerate(content_lines):
        if "expanding window" in line.lower() and "spc" in line.lower():
            if "removed" not in line.lower() and "bug" not in line.lower():
                content_lines[i] = line.replace("expanding window", "strict time window")
    
    # Update the technical implementation notes
    for i, line in enumerate(content_lines):
        if "### Technical Implementation" in line:
            # Look for SPC-related technical notes and update them
            for j in range(i+1, min(i+20, len(content_lines))):
                if "- **SPC expanding windows**:" in content_lines[j]:
                    content_lines[j] = "- **SPC strict windows**: No fallback logic, exact time boundary enforcement"
                    break
                elif "SPC lookbacks use expanding window when insufficient data" in content_lines[j]:
                    content_lines[j] = "SPC lookbacks use strict time boundaries, return NaN when insufficient data"
                    break
    
    # Write updated README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(content_lines))
    
    print("✅ README.md updated successfully with SPC strict time windows")
    print("🐛 Added: Comprehensive bug fix documentation")
    print("🔍 Updated: SPC lookback logic explanation")
    print("📊 Added: Before/after examples showing the fix")
    print("⚡ Updated: Data requirements for strict windows")
    print("🎯 Updated: Column examples with NaN handling")
    print("🚀 Updated: Version 1.5.5 with SPC strict time window fixes")
    print("💡 Added: Validation examples and impact assessment")
    print("🔧 Updated: Technical implementation notes")

if __name__ == "__main__":
    update_readme_with_spc_strict_windows()