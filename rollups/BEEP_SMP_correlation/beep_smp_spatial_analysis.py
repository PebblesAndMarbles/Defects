from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd


def _nearest_metrics(beep: np.ndarray, smp: np.ndarray) -> Tuple[float, float, float, float, float, float]:
    dist = np.sqrt(((smp[:, None, :] - beep[None, :, :]) ** 2).sum(axis=2))
    nearest = dist.min(axis=1)
    return (
        float(nearest.min()),
        float(np.median(nearest)),
        float(np.percentile(nearest, 90)),
        float(np.mean(nearest <= 5.0)),
        float(np.mean(nearest <= 10.0)),
        float(np.mean(nearest <= 15.0)),
    )


def _permutation_pvalues(
    coords: np.ndarray,
    n_beep: int,
    observed_median_nn: float,
    observed_frac10: float,
    rng: np.random.Generator,
    n_perm: int,
) -> Tuple[float, float, float, float]:
    n_total = coords.shape[0]
    if n_total <= 2 or n_beep <= 0 or n_beep >= n_total:
        return float("nan"), float("nan"), float("nan"), float("nan")

    perm_medians = np.empty(n_perm, dtype=float)
    perm_frac10 = np.empty(n_perm, dtype=float)
    all_idx = np.arange(n_total)

    for i in range(n_perm):
        beep_idx = rng.choice(n_total, size=n_beep, replace=False)
        smp_mask = np.ones(n_total, dtype=bool)
        smp_mask[beep_idx] = False
        smp_idx = all_idx[smp_mask]

        beep_p = coords[beep_idx]
        smp_p = coords[smp_idx]

        _, med, _, _, frac10, _ = _nearest_metrics(beep_p, smp_p)
        perm_medians[i] = med
        perm_frac10[i] = frac10

    # One-sided tests: unusually close = lower median distance, higher close-fraction.
    p_median = float((np.sum(perm_medians <= observed_median_nn) + 1) / (n_perm + 1))
    p_frac10 = float((np.sum(perm_frac10 >= observed_frac10) + 1) / (n_perm + 1))

    return p_median, p_frac10, float(np.median(perm_medians)), float(np.median(perm_frac10))


def compute_nn_metrics(df: pd.DataFrame, n_perm: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []

    for (wafer_id, layer), group in df.groupby(["WAFER_ID", "LAYER"], dropna=False):
        beep = group[group["CLASS"] == "BEEP"][["WAFER_X_MM", "WAFER_Y_MM"]].to_numpy(dtype=float)
        smp = group[group["CLASS"] == "SMALL_PARTICLE"][["WAFER_X_MM", "WAFER_Y_MM"]].to_numpy(dtype=float)

        if len(beep) == 0 or len(smp) == 0:
            continue

        min_nn, median_nn, p90_nn, frac5, frac10, frac15 = _nearest_metrics(beep, smp)

        coords = group[["WAFER_X_MM", "WAFER_Y_MM"]].to_numpy(dtype=float)
        p_median, p_frac10, null_median_nn, null_frac10 = _permutation_pvalues(
            coords=coords,
            n_beep=len(beep),
            observed_median_nn=median_nn,
            observed_frac10=frac10,
            rng=rng,
            n_perm=n_perm,
        )

        status_values = group["STATUS"].dropna().unique().tolist()
        status = status_values[0] if status_values else "UNKNOWN"

        rows.append(
            {
                "WAFER_ID": wafer_id,
                "LAYER": layer,
                "STATUS": status,
                "n_beep": int(len(beep)),
                "n_smp": int(len(smp)),
                "min_nn_mm": min_nn,
                "median_nn_mm": median_nn,
                "p90_nn_mm": p90_nn,
                "frac_smp_within_5mm": frac5,
                "frac_smp_within_10mm": frac10,
                "frac_smp_within_15mm": frac15,
                "perm_p_median_nn": p_median,
                "perm_p_frac10": p_frac10,
                "perm_null_median_nn": null_median_nn,
                "perm_null_frac10": null_frac10,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "WAFER_ID",
                "LAYER",
                "STATUS",
                "n_beep",
                "n_smp",
                "min_nn_mm",
                "median_nn_mm",
                "p90_nn_mm",
                "frac_smp_within_5mm",
                "frac_smp_within_10mm",
                "frac_smp_within_15mm",
                "perm_p_median_nn",
                "perm_p_frac10",
                "perm_null_median_nn",
                "perm_null_frac10",
            ]
        )

    out = pd.DataFrame(rows)

    # Composite score for ranking suspicious wafers.
    out["correlation_score"] = (
        0.45 * out["frac_smp_within_10mm"]
        + 0.30 * out["frac_smp_within_5mm"]
        + 0.25 * (1.0 / (1.0 + out["median_nn_mm"]))
    )
    out["correlation_score_sig"] = out["correlation_score"] * (1.0 - out["perm_p_median_nn"])

    return out.sort_values(["correlation_score_sig", "correlation_score", "n_beep", "n_smp"], ascending=[False, False, False, False])


def build_status_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(
            columns=[
                "STATUS",
                "wafer_layer_count",
                "median_median_nn_mm",
                "median_min_nn_mm",
                "median_frac_smp_within_5mm",
                "median_frac_smp_within_10mm",
                "median_frac_smp_within_15mm",
                "median_perm_p_median_nn",
                "median_perm_p_frac10",
            ]
        )

    rows = []
    for status, group in metrics.groupby("STATUS"):
        rows.append(
            {
                "STATUS": status,
                "wafer_layer_count": int(len(group)),
                "median_median_nn_mm": float(group["median_nn_mm"].median()),
                "median_min_nn_mm": float(group["min_nn_mm"].median()),
                "median_frac_smp_within_5mm": float(group["frac_smp_within_5mm"].median()),
                "median_frac_smp_within_10mm": float(group["frac_smp_within_10mm"].median()),
                "median_frac_smp_within_15mm": float(group["frac_smp_within_15mm"].median()),
                "median_perm_p_median_nn": float(group["perm_p_median_nn"].median()),
                "median_perm_p_frac10": float(group["perm_p_frac10"].median()),
            }
        )

    return pd.DataFrame(rows).sort_values("wafer_layer_count", ascending=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BEEP-SMP spatial correlation analysis")
    parser.add_argument(
        "--coords",
        type=Path,
        default=Path("outputs/defects/DEFECT_COORDINATES_EXTENDED.csv"),
        help="Path to defect coordinates CSV",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("rollups/BEEP_SMP_correlation/outputs"),
        help="Output directory for analysis files",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum count of BEEP and SMP for suspicious wafer list",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Top suspicious wafer-layer rows to export",
    )
    parser.add_argument(
        "--n-perm",
        type=int,
        default=200,
        help="Permutation count per wafer-layer for significance tests",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1278,
        help="Random seed for reproducible permutation tests",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance threshold for p-value filtered outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.coords, low_memory=False)
    df = df[df["CLASS"].isin(["BEEP", "SMALL_PARTICLE"])].copy()

    for col in ["WAFER_X_MM", "WAFER_Y_MM"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["WAFER_ID", "LAYER", "CLASS", "WAFER_X_MM", "WAFER_Y_MM"])

    metrics = compute_nn_metrics(df, n_perm=args.n_perm, seed=args.seed)
    summary = build_status_summary(metrics)

    suspicious = metrics[(metrics["n_beep"] >= args.min_count) & (metrics["n_smp"] >= args.min_count)].copy()
    suspicious_sig = suspicious[suspicious["perm_p_median_nn"] <= args.alpha].copy()

    suspicious_highflier = suspicious[suspicious["STATUS"] == "HIGHFLIER"].copy()
    suspicious_bsl = suspicious[suspicious["STATUS"] == "BSL"].copy()
    suspicious_sig_highflier = suspicious_sig[suspicious_sig["STATUS"] == "HIGHFLIER"].copy()
    suspicious_sig_bsl = suspicious_sig[suspicious_sig["STATUS"] == "BSL"].copy()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = args.out_dir / "beep_smp_wafer_metrics.csv"
    summary_path = args.out_dir / "beep_smp_status_summary.csv"
    suspicious_path = args.out_dir / "beep_smp_suspicious_top.csv"
    suspicious_sig_path = args.out_dir / "beep_smp_suspicious_significant.csv"
    suspicious_hf_path = args.out_dir / "beep_smp_suspicious_highflier_top.csv"
    suspicious_bsl_path = args.out_dir / "beep_smp_suspicious_bsl_top.csv"
    suspicious_sig_hf_path = args.out_dir / "beep_smp_suspicious_highflier_significant.csv"
    suspicious_sig_bsl_path = args.out_dir / "beep_smp_suspicious_bsl_significant.csv"

    metrics.to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)
    suspicious.head(args.top_n).to_csv(suspicious_path, index=False)
    suspicious_sig.to_csv(suspicious_sig_path, index=False)
    suspicious_highflier.head(args.top_n).to_csv(suspicious_hf_path, index=False)
    suspicious_bsl.head(args.top_n).to_csv(suspicious_bsl_path, index=False)
    suspicious_sig_highflier.to_csv(suspicious_sig_hf_path, index=False)
    suspicious_sig_bsl.to_csv(suspicious_sig_bsl_path, index=False)

    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {suspicious_path}")
    print(f"Wrote: {suspicious_sig_path}")
    print(f"Wrote: {suspicious_hf_path}")
    print(f"Wrote: {suspicious_bsl_path}")
    print(f"Wrote: {suspicious_sig_hf_path}")
    print(f"Wrote: {suspicious_sig_bsl_path}")
    print(f"Wafer-layer rows with both classes: {len(metrics)}")
    print(f"Significant rows (p <= {args.alpha}): {len(suspicious_sig)}")


if __name__ == "__main__":
    main()
