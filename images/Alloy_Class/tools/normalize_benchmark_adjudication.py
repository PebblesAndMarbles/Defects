from __future__ import annotations

import argparse
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# Canonical shorthand expansions per column.
EXPANSIONS: dict[str, dict[str, str]] = {
    "adjudicated_coarse_class": {
        "b": "possible_beep",
        "p": "particle",
        "i": "indeterminate",
    },
    "adjudicated_blocked_etch_evidence": {
        "s": "strong",
        "m": "moderate",
        "n": "none",
        "w": "weak",
    },
    "adjudicated_confidence": {
        "h": "high",
        "m": "medium",
        "l": "low",
    },
    "comparator_visible": {
        "y": "yes",
        "n": "no",
        "p": "partial",
    },
    # Binary yes/no fields
    "notes_needed":                     {"y": "yes", "n": "no"},
    "occlusion_present":                {"y": "yes", "n": "no"},
    "offset_surface_lines_present":     {"y": "yes", "n": "no"},
    "sunken_residual_continuity_present": {"y": "yes", "n": "no"},
    "comparator_boundary_line_present": {"y": "yes", "n": "no"},
    "mult_particles_present":           {"y": "yes", "n": "no"},
    "review_required_expected":         {"y": "yes", "n": "no"},
}

# These canonical values must not be remapped (already normalized).
VALID_VALUES: dict[str, set[str]] = {
    "adjudicated_coarse_class":           {"possible_beep", "particle", "indeterminate"},
    "adjudicated_blocked_etch_evidence":  {"strong", "moderate", "none", "weak"},
    "adjudicated_confidence":             {"high", "medium", "low"},
    "comparator_visible":                 {"yes", "no", "partial"},
    "notes_needed":                       {"yes", "no"},
    "occlusion_present":                  {"yes", "no"},
    "offset_surface_lines_present":       {"yes", "no", "unclear"},
    "sunken_residual_continuity_present": {"yes", "no"},
    "comparator_boundary_line_present":   {"yes", "no"},
    "mult_particles_present":             {"yes", "no"},
    "review_required_expected":           {"yes", "no"},
}


def normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], list[str]]:
    out = df.copy()
    change_counts: dict[str, int] = defaultdict(int)
    unknown: list[str] = []

    for col, mapping in EXPANSIONS.items():
        if col not in out.columns:
            continue
        valid = VALID_VALUES.get(col, set())
        for idx in out.index:
            raw = str(out.at[idx, col]).strip()
            if not raw or raw in valid:
                continue
            lower = raw.lower()
            if lower in mapping:
                out.at[idx, col] = mapping[lower]
                change_counts[col] += 1
            else:
                unknown.append(f"row {idx} col={col!r} value={raw!r}")

    return out, dict(change_counts), unknown


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand adjudication shorthand to canonical enum values")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--no-backup", action="store_true", help="Skip pre-write backup of output file")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    df = pd.read_csv(input_path, dtype=str).fillna("")

    if not args.no_backup and output_path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        bak = output_path.with_suffix(f".pre_normalize_{ts}.bak")
        shutil.copy2(output_path, bak)
        print(f"backup={bak}")

    out, change_counts, unknown = normalize(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    total = sum(change_counts.values())
    print(f"rows_input={len(df)}")
    print(f"cells_normalized={total}")
    for col, n in sorted(change_counts.items()):
        print(f"  {col}: {n}")
    if unknown:
        print(f"UNRECOGNIZED VALUES ({len(unknown)}):")
        for u in unknown:
            print(f"  {u}")
    else:
        print("unrecognized_values=0")
    print(f"wrote={output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
