#!/usr/bin/env python3
"""
Phase 1, Step 3: Parse and categorize APEX@ENTITY columns.

This script:
1. Reads raw column lists from 02a_raw_columns_<ALIAS>.txt files.
2. Extracts and categorizes fields (top-level, subentity slots, subfields).
3. Validates consistency across all 10 aliases.
4. Produces enriched schema CSV + markdown documentation.

Depends on:
    - Phase 1, Step 2 completed (02a_raw_columns_*.txt artifacts generated)
"""

import sys
import pathlib
import csv
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict, Counter
import datetime


def load_raw_columns(artifact_dir: Path, alias: str) -> List[str]:
    """Load raw column list from 02a_raw_columns_<ALIAS>.txt."""
    file_path = artifact_dir / f"02a_raw_columns_{alias}.txt"
    if not file_path.exists():
        return []
    return file_path.read_text().strip().split("\n")


def parse_column(column_name: str) -> Dict:
    """
    Parse APEX@ENTITY column to extract components.
    
    Example: APEX@ENTITY@E_8M5_HM_ETCH@V6@SUBENTITY_0@BATCH_IDLE
    
    Returns:
        Dict with keys: project, dataset, alias, version, field_path,
        is_top_level, subentity_index, subfield.
    """
    parts = column_name.split("@")
    
    if len(parts) < 5:
        return {"raw": column_name, "error": "Invalid segment count"}
    
    result = {
        "raw": column_name,
        "project": parts[0],
        "dataset": parts[1],
        "alias": parts[2],
        "version": parts[3],
        "field_path": "@".join(parts[4:]),
        "error": None,
    }
    
    # Parse field path
    field_path = result["field_path"]
    
    # Top-level fields (no @ in field_path)
    if "@" not in field_path:
        result["is_top_level"] = True
        result["field"] = field_path
    else:
        # Subentity fields: SUBENTITY_N@SUBFIELD or similar
        result["is_top_level"] = False
        
        # Check for SUBENTITY_N pattern
        match = re.match(r"SUBENTITY_(\d+)@(.+)", field_path)
        if match:
            result["subentity_index"] = int(match.group(1))
            result["subfield"] = match.group(2)
        else:
            result["error"] = f"Unparseable field_path: {field_path}"
    
    return result


def categorize_alias_columns(columns: List[str]) -> Dict:
    """
    Categorize all columns for a single alias.
    
    Returns:
        Dict with:
            - top_level: {field_name: count}
            - subentity_indices: set of N values (0-14)
            - subfields: {subfield_name: count}
            - unparseable: list of column names
    """
    result = {
        "top_level": Counter(),
        "subentity_indices": set(),
        "subfields": Counter(),
        "unparseable": [],
    }
    
    for column in columns:
        parsed = parse_column(column)
        
        if parsed.get("error"):
            result["unparseable"].append(column)
        elif parsed.get("is_top_level"):
            result["top_level"][parsed["field"]] += 1
        else:
            if "subentity_index" in parsed:
                result["subentity_indices"].add(parsed["subentity_index"])
                result["subfields"][parsed["subfield"]] += 1
            else:
                result["unparseable"].append(column)
    
    return result


def validate_consistency(all_alias_categories: Dict[str, Dict]) -> Dict:
    """
    Validate that all aliases have consistent field structure.
    
    Returns:
        Dict with validation results and any deviations.
    """
    validations = {
        "ok": True,
        "deviations": [],
    }
    
    # Extract metadata from first alias as baseline
    baseline_alias = next(iter(all_alias_categories.keys()))
    baseline = all_alias_categories[baseline_alias]
    
    baseline_top_level = set(baseline["top_level"].keys())
    baseline_subfields = set(baseline["subfields"].keys())
    baseline_indices = baseline["subentity_indices"]
    
    print(f"\n[VALIDATE] Using baseline alias: {baseline_alias}")
    print(f"  Top-level fields: {baseline_top_level}")
    print(f"  Subentity indices: {sorted(baseline_indices)}")
    print(f"  Subfields per slot: {baseline_subfields}")
    
    # Check all aliases
    for alias, categories in all_alias_categories.items():
        alias_top_level = set(categories["top_level"].keys())
        alias_subfields = set(categories["subfields"].keys())
        alias_indices = categories["subentity_indices"]
        
        # Top-level mismatch
        if alias_top_level != baseline_top_level:
            validations["ok"] = False
            validations["deviations"].append({
                "alias": alias,
                "type": "top_level_mismatch",
                "baseline": baseline_top_level,
                "actual": alias_top_level,
                "missing": baseline_top_level - alias_top_level,
                "extra": alias_top_level - baseline_top_level,
            })
        
        # Subfield mismatch
        if alias_subfields != baseline_subfields:
            validations["ok"] = False
            validations["deviations"].append({
                "alias": alias,
                "type": "subfield_mismatch",
                "baseline": baseline_subfields,
                "actual": alias_subfields,
                "missing": baseline_subfields - alias_subfields,
                "extra": alias_subfields - baseline_subfields,
            })
        
        # Subentity index mismatch
        if alias_indices != baseline_indices:
            validations["ok"] = False
            validations["deviations"].append({
                "alias": alias,
                "type": "subentity_index_mismatch",
                "baseline": sorted(baseline_indices),
                "actual": sorted(alias_indices),
            })
    
    return validations


def main():
    """
    Main entry point: parse raw columns, categorize, validate, produce schema docs.
    """
    script_dir = Path(__file__).parent
    artifact_dir = script_dir / "artifacts"
    
    print("=" * 80)
    print(f"Phase 1, Step 3: Parse & Categorize APEX@ENTITY Columns")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 80)
    
    if not artifact_dir.exists():
        print(f"[ERROR] Artifact directory not found: {artifact_dir}")
        print("[HINT] Run Phase 1, Step 2 first to generate raw column probes.")
        sys.exit(1)
    
    # Load FULL_FLOW_ALIASES
    FULL_FLOW_ALIASES = [
        "L_8M5_SIARC_DEP", "L_8M5_CHM_DEP", "L_8M5_SED", "E_8M5_HM_ETCH", "W_8M5_HM_CLN",
        "L_8M6_SIARC_DEP", "L_8M6_CHM_DEP", "L_8M6_SED", "E_8M6_HM_ETCH", "W_8M6_HM_CLN",
    ]
    
    # Parse all aliases
    print("\n[PARSE] Loading and categorizing columns per alias...")
    all_alias_categories = {}
    parse_results = []
    
    for alias in FULL_FLOW_ALIASES:
        columns = load_raw_columns(artifact_dir, alias)
        if not columns or (len(columns) == 1 and columns[0] == ""):
            print(f"  {alias}: [WARN] No columns found")
            continue
        
        categories = categorize_alias_columns(columns)
        all_alias_categories[alias] = categories
        
        print(f"  {alias}: {len(columns)} total, "
              f"{len(categories['top_level'])} top-level, "
              f"{len(categories['subfields'])} unique subfields, "
              f"slots {sorted(categories['subentity_indices'])}")
        
        parse_results.append({
            "alias": alias,
            "total_columns": len(columns),
            "top_level_count": len(categories["top_level"]),
            "subentity_indices": ",".join(map(str, sorted(categories["subentity_indices"]))),
            "subfield_count": len(categories["subfields"]),
            "subfields": ",".join(sorted(categories["subfields"].keys())),
            "unparseable_count": len(categories["unparseable"]),
        })
    
    # Validate consistency
    print("\n[VALIDATE] Checking consistency across aliases...")
    validations = validate_consistency(all_alias_categories)
    
    if validations["ok"]:
        print("  [OK] All aliases have consistent structure!")
    else:
        print("  [WARN] Deviations found:")
        for dev in validations["deviations"]:
            print(f"    - {dev}")
    
    # Write enriched schema CSV
    schema_csv_file = artifact_dir / "02b_apex_entity_column_schema.csv"
    try:
        with open(schema_csv_file, "w", newline="") as f:
            fieldnames = [
                "alias", "total_columns", "top_level_count", "subentity_indices",
                "subfield_count", "subfields", "unparseable_count"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parse_results)
        print(f"  [OK] Schema CSV written: {schema_csv_file.name}")
    except Exception as e:
        print(f"  [ERROR] Failed to write schema CSV: {e}")
        sys.exit(1)
    
    # Write validation report
    validation_file = artifact_dir / "03_validation_report.txt"
    try:
        with open(validation_file, "w") as f:
            f.write("APEX@ENTITY Column Schema Validation\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("CONSISTENCY CHECK:\n")
            f.write(f"Overall Status: {'OK' if validations['ok'] else 'DEVIATIONS FOUND'}\n\n")
            
            if validations["deviations"]:
                f.write("Deviations:\n")
                for dev in validations["deviations"]:
                    f.write(f"\n  {dev}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("FIELD STRUCTURE (from baseline alias):\n")
            f.write("=" * 80 + "\n\n")
            
            if all_alias_categories:
                baseline_alias = next(iter(all_alias_categories.keys()))
                baseline = all_alias_categories[baseline_alias]
                
                f.write(f"Baseline alias: {baseline_alias}\n\n")
                f.write("Top-level fields:\n")
                for field in sorted(baseline["top_level"].keys()):
                    f.write(f"  - {field}\n")
                
                f.write("\nSubentity slot indices (N in SUBENTITY_N):\n")
                f.write(f"  {sorted(baseline['subentity_indices'])}\n")
                
                f.write("\nSubfields per slot (e.g., SUBENTITY_N@SUBFIELD):\n")
                for subfield in sorted(baseline["subfields"].keys()):
                    f.write(f"  - {subfield}\n")
        
        print(f"  [OK] Validation report written: {validation_file.name}")
    except Exception as e:
        print(f"  [ERROR] Failed to write validation report: {e}")
    
    # Write markdown documentation
    schema_md_file = artifact_dir / "03_apex_entity_schema.md"
    try:
        with open(schema_md_file, "w") as f:
            f.write("# APEX@ENTITY Column Schema\n\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Validation Status: {'✓ OK' if validations['ok'] else '⚠ Deviations'}\n\n")
            
            f.write("## Overview\n\n")
            f.write("This document summarizes the APEX@ENTITY dataset structure across all 10 FULL_FLOW_ALIASES.\n\n")
            
            if all_alias_categories:
                baseline_alias = next(iter(all_alias_categories.keys()))
                baseline = all_alias_categories[baseline_alias]
                
                f.write("## Top-Level Fields\n\n")
                f.write("These fields appear once per (wafer, alias) record:\n\n")
                for field in sorted(baseline["top_level"].keys()):
                    f.write(f"- `{field}`\n")
                
                f.write("\n## Subentity Slot Structure\n\n")
                f.write(f"Each (wafer, alias) record contains **15 candidate chamber slots** (indices 0–14):\n\n")
                f.write("```\nSUBENTITY_0 (candidate chamber at slot 0)\nSUBENTITY_1 (candidate chamber at slot 1)\n...\nSUBENTITY_14 (candidate chamber at slot 14)\n```\n\n")
                
                f.write("Each slot carries the same **5 subfields**:\n\n")
                for subfield in sorted(baseline["subfields"].keys()):
                    f.write(f"- `{subfield}`\n")
                
                f.write("\n### Field Semantics (inferred from names)\n\n")
                f.write("| Field | Meaning |\n")
                f.write("|---|---|\n")
                f.write("| `BATCH_IDLE` | Whether the chamber was batch-idle (no work queued) around wafer's run |\n")
                f.write("| `PRIOR_ALIAS` | Alias of the previous operation run in that chamber before this wafer |\n")
                f.write("| `PROCESS_ORDER` | Wafer's position within its chamber run/batch |\n")
                f.write("| `SEQUENCE` | Chamber's rank/order among candidates for this dispatch decision |\n")
                f.write("| `UTILIZATION` | Chamber utilization metric around the time of wafer run |\n")
                
                f.write("\n## Per-Alias Summary\n\n")
                for result in parse_results:
                    f.write(f"### {result['alias']}\n\n")
                    f.write(f"- Total columns: {result['total_columns']}\n")
                    f.write(f"- Top-level fields: {result['top_level_count']}\n")
                    f.write(f"- Subentity slots: {result['subentity_indices']}\n")
                    f.write(f"- Subfields per slot: {result['subfield_count']}\n")
        
        print(f"  [OK] Markdown schema written: {schema_md_file.name}")
    except Exception as e:
        print(f"  [ERROR] Failed to write markdown schema: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Aliases processed: {len(all_alias_categories)}")
    print(f"Validation: {'✓ PASS' if validations['ok'] else '⚠ WARN'}")
    print(f"\nOutputs:")
    print(f"  - {schema_csv_file.name}")
    print(f"  - {validation_file.name}")
    print(f"  - {schema_md_file.name}")
    
    print(f"\n[OK] Phase 1 complete. Proceed to Phase 2, Step 4 (extract pilot wafers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
