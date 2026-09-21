from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


def stable_bucket(value: str, seed: int) -> int:
    payload = f"{seed}|{value}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:8], 16)


def assign_split(df: pd.DataFrame, eval_ratio: float, seed: int) -> pd.DataFrame:
    out = df.copy()
    out["split"] = ""

    group_cols = ["source_pool", "chamber", "adjudicated_coarse_class"]
    for col in group_cols:
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str).str.strip()

    if "benchmark_id" not in out.columns:
        out["benchmark_id"] = ""

    grouped = out.groupby(group_cols, dropna=False)
    for _, idx in grouped.groups.items():
        ix = list(idx)
        keys = []
        for i in ix:
            bmk = str(out.at[i, "benchmark_id"])
            pair = str(out.at[i, "pair_key"]) if "pair_key" in out.columns else ""
            key = bmk or pair or str(i)
            keys.append((i, stable_bucket(key, seed)))

        keys.sort(key=lambda item: item[1])
        eval_count = int(round(len(keys) * eval_ratio))
        eval_set = {i for i, _ in keys[:eval_count]}
        for i, _ in keys:
            out.at[i, "split"] = "eval" if i in eval_set else "tune"

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Assign deterministic tune/eval split post-adjudication")
    parser.add_argument("--input-csv", required=True, help="Adjudicated benchmark CSV")
    parser.add_argument("--output-csv", required=True, help="Output CSV with split assigned")
    parser.add_argument("--eval-ratio", type=float, default=0.3, help="Eval fraction per stratified group")
    parser.add_argument("--seed", type=int, default=1278, help="Deterministic split seed")
    args = parser.parse_args()

    if args.eval_ratio <= 0 or args.eval_ratio >= 1:
        raise ValueError("--eval-ratio must be between 0 and 1")

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    df = pd.read_csv(input_path, dtype=str).fillna("")
    out = assign_split(df, eval_ratio=args.eval_ratio, seed=args.seed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    counts = out["split"].value_counts().to_dict()
    print(f"wrote={output_path.resolve()}")
    print(f"split_counts={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())