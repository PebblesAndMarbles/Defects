#!/usr/bin/env python3
"""
Phase 2, Step 7: Validate match rate and investigate mismatches.

This script:
1. Loads 05b_pilot_matched_wafers.csv from Step 5-6.
2. Computes match-rate metric and categorizes results.
3. Surfaces mismatches for review.
4. Produces validation report.
5. **Decision gate**: If match rate >= 95%, proceed to Phase 3. Otherwise, halt.

Depends on:
    - Phase 2, Steps 5-6 completed (05b_pilot_matched_wafers.csv)
"""

import sys
import csv
from pathlib import Path
from typing import Dict, List
import datetime


def load_matched_wafers(csv_path: Path) -> List[Dict]:
    """Load matched wafers CSV."""
    results = []
    
    if not csv_path.exists():
        print(f"[ERROR] Matched wafers CSV not found: {csv_path}")
        sys.exit(1)
    
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            results = list(reader)
        print(f"[OK] Loaded {len(results)} rows from {csv_path.name}")
        return results
    except Exception as e:
        print(f"[ERROR] Failed to load CSV: {e}")
        sys.exit(1)


def analyze_matches(data: List[Dict]) -> Dict:
    """
    Analyze match results.
    
    Returns:
        Dict with keys: total, ok, mismatch, no_data, match_rate,
        mismatches_by_alias, mismatches_by_wafer.
    """
    total = len(data)
    ok = sum(1 for row in data if row.get("MATCH_STATUS") == "OK")
    mismatch = sum(1 for row in data if row.get("MATCH_STATUS") == "MISMATCH")
    no_data = sum(1 for row in data if row.get("MATCH_STATUS") not in ["OK", "MISMATCH"])
    
    match_rate = (ok / total * 100) if total > 0 else 0
    
    # Mismatches by alias
    mismatches_by_alias = {}
    mismatches_by_wafer = {}
    
    for row in data:
        if row.get("MATCH_STATUS") == "MISMATCH":
            alias = row.get("ALIAS", "UNKNOWN")
            wafer = row.get("WAFER_ID", "UNKNOWN")
            
            mismatches_by_alias[alias] = mismatches_by_alias.get(alias, 0) + 1
            mismatches_by_wafer[wafer] = mismatches_by_wafer.get(wafer, 0) + 1
    
    return {
        "total": total,
        "ok": ok,
        "mismatch": mismatch,
        "no_data": no_data,
        "match_rate": match_rate,
        "mismatches_by_alias": mismatches_by_alias,
        "mismatches_by_wafer": mismatches_by_wafer,
    }


def main():
    """
    Main entry point: validate match rate, produce report, decision gate.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate pilot match rate and surface mismatches."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=95.0,
        help="Match rate threshold (%) to proceed (default: 95.0)"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to 05b CSV (auto-detected if not specified)"
    )
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    
    print("=" * 80)
    print(f"Phase 2, Step 7: Validate Match Rate")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    # Load matched wafers
    print("\n[LOAD] Loading matched wafers...")
    input_csv = args.input
    
    if not input_csv:
        # Find the most recent 05b file
        matching_files = sorted(artifact_dir.glob("05b_pilot_matched_wafers*.csv"))
        if not matching_files:
            print(f"[ERROR] No 05b CSV files found in {artifact_dir}")
            sys.exit(1)
        input_csv = matching_files[-1]
    
    data = load_matched_wafers(input_csv)
    
    # Analyze
    print("\n[ANALYZE] Computing match rate...")
    analysis = analyze_matches(data)
    
    match_rate = analysis["match_rate"]
    threshold = args.threshold
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS:")
    print("=" * 80)
    print(f"Total (wafer, alias) pairs: {analysis['total']}")
    print(f"Successful matches:         {analysis['ok']}")
    print(f"Mismatches:                 {analysis['mismatch']}")
    print(f"No data (WDS errors):       {analysis['no_data']}")
    print(f"\nMatch rate:                 {match_rate:.1f}%")
    print(f"Threshold:                  {threshold:.1f}%")
    print(f"Status:                     {'✓ PASS' if match_rate >= threshold else '✗ FAIL'}")
    
    # Mismatches detail
    if analysis["mismatches_by_alias"]:
        print(f"\nMismatches by alias:")
        for alias in sorted(analysis["mismatches_by_alias"].keys()):
            count = analysis["mismatches_by_alias"][alias]
            print(f"  {alias}: {count}")
    
    if analysis["mismatches_by_wafer"]:
        print(f"\nMismatches by wafer:")
        for wafer in sorted(analysis["mismatches_by_wafer"].keys()):
            count = analysis["mismatches_by_wafer"][wafer]
            print(f"  {wafer}: {count}")
    
    # Write validation report
    print("\n[REPORT] Writing validation report...")
    report_file = artifact_dir / "07_pilot_validation_report.txt"
    
    try:
        with open(report_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("APEX@ENTITY Pilot Validation Report\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Input file: {input_csv}\n")
            f.write(f"Threshold: {threshold}%\n\n")
            
            f.write("RESULTS:\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total (wafer, alias) pairs:       {analysis['total']}\n")
            f.write(f"Successful matches (slot found):  {analysis['ok']}\n")
            f.write(f"Mismatches (no slot match):       {analysis['mismatch']}\n")
            f.write(f"No data (WDS query failed):       {analysis['no_data']}\n")
            f.write(f"\nMatch rate:                       {match_rate:.1f}%\n")
            f.write(f"Threshold:                        {threshold}%\n")
            f.write(f"Status:                           {'✓ PASS' if match_rate >= threshold else '✗ FAIL'}\n")
            
            if analysis["mismatches_by_alias"]:
                f.write("\n" + "=" * 80 + "\n")
                f.write("MISMATCHES BY ALIAS:\n")
                f.write("=" * 80 + "\n")
                for alias in sorted(analysis["mismatches_by_alias"].keys()):
                    count = analysis["mismatches_by_alias"][alias]
                    f.write(f"{alias}: {count} mismatch(es)\n")
            
            if analysis["mismatches_by_wafer"]:
                f.write("\n" + "=" * 80 + "\n")
                f.write("MISMATCHES BY WAFER:\n")
                f.write("=" * 80 + "\n")
                for wafer in sorted(analysis["mismatches_by_wafer"].keys()):
                    count = analysis["mismatches_by_wafer"][wafer]
                    f.write(f"{wafer}: {count} mismatch(es)\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("MISMATCH DETAILS:\n")
            f.write("=" * 80 + "\n")
            for row in data:
                if row.get("MATCH_STATUS") == "MISMATCH":
                    f.write(f"\nWafer: {row.get('WAFER_ID')}\n")
                    f.write(f"Alias: {row.get('ALIAS')}\n")
                    f.write(f"Production SUBENTITY: {row.get('PRODUCTION_SUBENTITY')}\n")
                    f.write(f"WDS slot match: Not found\n")
            
            f.write("\n" + "=" * 80 + "\n")
            if match_rate >= threshold:
                f.write("DECISION: ✓ PROCEED\n")
                f.write(f"Match rate {match_rate:.1f}% >= threshold {threshold}%.\n")
                f.write("Approved to proceed to Phase 3 (output design).\n")
            else:
                f.write("DECISION: ✗ HALT\n")
                f.write(f"Match rate {match_rate:.1f}% < threshold {threshold}%.\n")
                f.write("Recommend investigation before proceeding.\n")
        
        print(f"[OK] Report written: {report_file.name}")
    except Exception as e:
        print(f"[ERROR] Failed to write report: {e}")
        sys.exit(1)
    
    # Decision gate
    print("\n" + "=" * 80)
    print("DECISION GATE:")
    print("=" * 80)
    
    if match_rate >= threshold:
        print(f"✓ PROCEED to Phase 3")
        print(f"  Match rate {match_rate:.1f}% is >= threshold {threshold}%.")
        print(f"  Proceed to Phase 3, Step 8 (define output columns).")
        return 0
    else:
        print(f"✗ HALT")
        print(f"  Match rate {match_rate:.1f}% is < threshold {threshold}%.")
        print(f"  Investigate mismatches above before proceeding.")
        print(f"  Review: {report_file.name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
