"""
select_generic_description_sample.py
-------------------------------------
Selection-only step for the SMALL_PARTICLE generic-description VLM pilot
(clustering-refinement phase). Builds a small pilot manifest of brightfield/
darkfield image pairs -- does not call the VLM and does not download images.

Source: DEFECT_COORDINATES_EXTENDED_IMAGES.csv, filtered to CLASS ==
'SMALL_PARTICLE'. BEEP defects are excluded entirely -- this pilot is scoped
to SMALL_PARTICLE only.

The output manifest carries the burned LOCAL_IMAGE_FILE columns only as a
join key (never sent to the model) plus IMAGE_FILESPEC/QUERY_SITE, which
tools/probe_generic_description_v1.py uses to resolve and download the raw
(non-burned) source image for each of the two roles before calling the VLM.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

DEFAULT_INPUT = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv"
)
DEFAULT_OUTPUT = (
    r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson"
    r"\Defects\BE\images\Alloy_Class\outputs\probes\generic_description_pilot_manifest.csv"
)

TARGET_CLASS = "SMALL_PARTICLE"
BRIGHTFIELD_IMAGE_ID = 2
DARKFIELD_IMAGE_ID = 3

# Carried through for later correlation with clustering output, not used for selection.
METADATA_COLUMNS = [
    "SUBENTITY", "LOT", "LOT7", "LAYER", "WAFER_ID",
    "SIZE_X", "SIZE_Y", "SIZE_D", "AREA", "FINEBIN", "INSPECT_TIME",
]


def _to_int(value: object) -> int | None:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def load_small_particle_pairs(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv, low_memory=False, dtype=str)
    df = df[df["CLASS"] == TARGET_CLASS].copy()
    df = df[df["LOCAL_IMAGE_FILE"].fillna("").str.strip() != ""]
    df["_IMAGE_ID_INT"] = df["IMAGE_ID"].apply(_to_int)
    df = df[df["_IMAGE_ID_INT"].isin([BRIGHTFIELD_IMAGE_ID, DARKFIELD_IMAGE_ID])]

    rows: list[dict[str, object]] = []
    for key, group in df.groupby(["WAFER_KEY", "INSPECTION_TIME", "DEFECT_ID"]):
        by_role = {int(r["_IMAGE_ID_INT"]): r for _, r in group.iterrows()}
        bright = by_role.get(BRIGHTFIELD_IMAGE_ID)
        dark = by_role.get(DARKFIELD_IMAGE_ID)
        if bright is None or dark is None:
            continue  # need both roles to make a callable pair

        record: dict[str, object] = {
            "wafer_key": key[0],
            "inspection_time": key[1],
            "defect_id": key[2],
            "bright_local_image_file": bright["LOCAL_IMAGE_FILE"],
            "dark_local_image_file": dark["LOCAL_IMAGE_FILE"],
            "bright_image_filespec": bright.get("IMAGE_FILESPEC", ""),
            "dark_image_filespec": dark.get("IMAGE_FILESPEC", ""),
            "query_site": bright.get("QUERY_SITE") or bright.get("SITE", ""),
        }
        for col in METADATA_COLUMNS:
            record[col.lower()] = bright.get(col, "")
        rows.append(record)

    return pd.DataFrame(rows)


def stratified_sample(df: pd.DataFrame, n: int, strata_col: str, seed: int) -> pd.DataFrame:
    """Round-robins across distinct strata_col values so the sample isn't dominated by one chamber/tool."""
    if df.empty or n <= 0 or len(df) <= n:
        return df.reset_index(drop=True)

    rng = random.Random(seed)
    strata = sorted(df[strata_col].fillna("UNKNOWN").unique())
    buckets = {s: df[df[strata_col].fillna("UNKNOWN") == s].index.tolist() for s in strata}
    for indices in buckets.values():
        rng.shuffle(indices)

    selected: list[int] = []
    while len(selected) < n and any(buckets.values()):
        for s in strata:
            if len(selected) >= n:
                break
            if buckets[s]:
                selected.append(buckets[s].pop())

    return df.loc[selected].reset_index(drop=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select a pilot sample of SMALL_PARTICLE image pairs for the generic-description VLM probe."
    )
    parser.add_argument("--input-csv", default=DEFAULT_INPUT)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sample-size", type=int, default=40,
        help="Target pilot sample size (default: 40, within the 30-50 pilot range agreed with user)",
    )
    parser.add_argument(
        "--strata-column", default="subentity",
        help="Column to spread the sample across for basic variety (default: subentity/chamber)",
    )
    parser.add_argument("--seed", type=int, default=20260830, help="Random seed for reproducible sampling")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)

    pairs = load_small_particle_pairs(input_csv)
    if pairs.empty:
        print("no_small_particle_pairs_found")
        return 1

    sample = stratified_sample(pairs, args.sample_size, args.strata_column, args.seed)
    sample.insert(0, "case_id", [f"SMP_PILOT_{i:03d}" for i in range(1, len(sample) + 1)])

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(output_csv, index=False)

    print(f"candidate_pairs_total={len(pairs)}")
    print(f"sample_size={len(sample)}")
    print(f"strata_covered={sample[args.strata_column].nunique()}")
    print(f"output_csv={output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
