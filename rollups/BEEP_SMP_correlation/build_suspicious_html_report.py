from __future__ import annotations

import argparse
import os
from html import escape
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def normalize_key(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
    except (TypeError, ValueError):
        pass
    return text


def path_to_uri(path_text: str) -> str:
    try:
        return Path(path_text).as_uri()
    except (ValueError, OSError):
        return str(path_text).replace("\\", "/")


def load_manifest_index(manifest_csv: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    cols = ["WAFER_KEY", "DEFECT_ID", "IMAGE_ID", "LOCAL_IMAGE_FILE", "INSPECTION_TIME"]
    man = pd.read_csv(manifest_csv, usecols=cols, low_memory=False)

    idx: Dict[Tuple[str, str], Dict[str, Dict[str, str]]] = {}

    for _, row in man.iterrows():
        wafer_key = normalize_key(row["WAFER_KEY"])
        defect_id = normalize_key(row["DEFECT_ID"])
        image_id = normalize_key(row["IMAGE_ID"])
        local_file = str(row["LOCAL_IMAGE_FILE"]).strip() if not pd.isna(row["LOCAL_IMAGE_FILE"]) else ""

        if not wafer_key or not defect_id or image_id not in {"2", "3"}:
            continue
        if not local_file or not os.path.isfile(local_file):
            continue

        key = (wafer_key, defect_id)
        ts = pd.to_datetime(row["INSPECTION_TIME"], errors="coerce")
        uri = path_to_uri(local_file)

        rec = idx.setdefault(key, {})
        existing = rec.get(image_id)
        if existing is None or ts > pd.to_datetime(existing["ts"], errors="coerce"):
            rec[image_id] = {"uri": uri, "ts": str(ts)}

    strict: Dict[Tuple[str, str], Dict[str, str]] = {}
    for key, rec in idx.items():
        if "2" in rec and "3" in rec:
            strict[key] = {"2": rec["2"]["uri"], "3": rec["3"]["uri"]}
    return strict


def wafermap_png(df: pd.DataFrame, wafer_id: str, layer: str, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    png_name = f"{wafer_id}_{layer}_wafermap.png".replace("/", "_")
    png_path = out_dir / png_name

    fig, ax = plt.subplots(figsize=(5.3, 5.3), facecolor="#111417")
    ax.set_facecolor("#111417")

    wafer_r = 150
    ax.add_patch(plt.Circle((0, 0), wafer_r, color="#7f8c8d", fill=False, linewidth=1.8, zorder=2))

    beep = df[df["CLASS"] == "BEEP"]
    smp = df[df["CLASS"] == "SMALL_PARTICLE"]

    ax.scatter(
        beep["WAFER_X_MM"],
        beep["WAFER_Y_MM"],
        c="#2e9cca",
        marker="x",
        s=34,
        linewidths=1.1,
        alpha=0.95,
        label=f"BEEP (n={len(beep)})",
        zorder=4,
    )
    ax.scatter(
        smp["WAFER_X_MM"],
        smp["WAFER_Y_MM"],
        c="#f4a261",
        marker="o",
        s=18,
        alpha=0.9,
        label=f"SMP (n={len(smp)})",
        zorder=3,
    )

    ax.set_xlim(-170, 170)
    ax.set_ylim(-170, 170)
    ax.set_aspect("equal")
    ax.grid(color="#1f2930", linewidth=0.5)
    ax.set_xlabel("X (mm)", color="#b0bec5")
    ax.set_ylabel("Y (mm)", color="#b0bec5")
    ax.tick_params(colors="#90a4ae", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#2f3b43")

    ax.legend(loc="upper right", facecolor="#1d252b", edgecolor="#2f3b43", fontsize=8, labelcolor="#d0d8dc")
    ax.set_title(f"{wafer_id} | {layer}", color="#e6eef2", fontsize=10, pad=8)

    fig.tight_layout(pad=0.7)
    fig.savefig(png_path, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)

    return png_name


def build_pair_table(df_group: pd.DataFrame) -> pd.DataFrame:
    beep = df_group[df_group["CLASS"] == "BEEP"].copy()
    smp = df_group[df_group["CLASS"] == "SMALL_PARTICLE"].copy()

    if beep.empty or smp.empty:
        return pd.DataFrame()

    bxy = beep[["WAFER_X_MM", "WAFER_Y_MM"]].to_numpy(dtype=float)
    sxy = smp[["WAFER_X_MM", "WAFER_Y_MM"]].to_numpy(dtype=float)
    d = np.sqrt(((sxy[:, None, :] - bxy[None, :, :]) ** 2).sum(axis=2))
    idx_min = d.argmin(axis=1)
    min_dist = d[np.arange(len(smp)), idx_min]

    rows: List[dict] = []
    beep_reset = beep.reset_index(drop=True)
    smp_reset = smp.reset_index(drop=True)

    for i, j in enumerate(idx_min):
        srow = smp_reset.iloc[i]
        brow = beep_reset.iloc[int(j)]
        rows.append(
            {
                "nn_mm": float(min_dist[i]),
                "SMP_DEFECT_ID": normalize_key(srow["DEFECT_ID"]),
                "BEEP_DEFECT_ID": normalize_key(brow["DEFECT_ID"]),
                "WAFER_KEY": normalize_key(srow["WAFER_KEY"]),
            }
        )

    return pd.DataFrame(rows).sort_values("nn_mm", ascending=True)


def make_image_card(title: str, image_set: Dict[str, str] | None) -> str:
    if not image_set:
        return (
            '<div class="card"><div class="meta">'
            + escape(title)
            + '</div><div class="missing">No BF/DF pair in manifest</div></div>'
        )

    bf = image_set.get("2")
    df = image_set.get("3")
    if not bf or not df:
        return (
            '<div class="card"><div class="meta">'
            + escape(title)
            + '</div><div class="missing">Missing image pair</div></div>'
        )

    return (
        '<div class="card">'
        f'<div class="meta">{escape(title)}</div>'
        '<div class="imgrow">'
        f'<a href="{bf}" target="_blank"><img src="{bf}" loading="lazy" alt="Brightfield"></a>'
        f'<a href="{df}" target="_blank"><img src="{df}" loading="lazy" alt="Darkfield"></a>'
        "</div></div>"
    )


def build_report_html(
    suspicious_df: pd.DataFrame,
    coord_df: pd.DataFrame,
    manifest_idx: Dict[Tuple[str, str], Dict[str, str]],
    out_dir: Path,
    top_per_status: int,
    pair_count: int,
) -> Path:
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    sections: List[str] = []

    statuses = ["HIGHFLIER", "BSL"]
    for status in statuses:
        subset = suspicious_df[suspicious_df["STATUS"] == status].head(top_per_status)
        sections.append(f'<h2>{status} Candidates (top {len(subset)})</h2>')

        for _, row in subset.iterrows():
            wafer_id = row["WAFER_ID"]
            layer = row["LAYER"]

            g = coord_df[
                (coord_df["WAFER_ID"] == wafer_id)
                & (coord_df["LAYER"] == layer)
                & (coord_df["CLASS"].isin(["BEEP", "SMALL_PARTICLE"]))
            ].copy()

            if g.empty:
                continue

            png_name = wafermap_png(g, wafer_id, layer, assets_dir)
            pair_df = build_pair_table(g).head(pair_count)

            pair_cards: List[str] = []
            for i, prow in pair_df.iterrows():
                wafer_key = prow["WAFER_KEY"]
                smp_key = (wafer_key, prow["SMP_DEFECT_ID"])
                beep_key = (wafer_key, prow["BEEP_DEFECT_ID"])

                smp_title = f"SMP #{i+1} | DEFECT_ID {prow['SMP_DEFECT_ID']} | nn={prow['nn_mm']:.2f} mm"
                beep_title = f"BEEP match | DEFECT_ID {prow['BEEP_DEFECT_ID']}"

                pair_cards.append('<div class="pair">')
                pair_cards.append(make_image_card(smp_title, manifest_idx.get(smp_key)))
                pair_cards.append(make_image_card(beep_title, manifest_idx.get(beep_key)))
                pair_cards.append("</div>")

            sections.append(
                '<section class="wafer">'
                f'<h3>{escape(str(wafer_id))} | {escape(str(layer))}</h3>'
                '<div class="meta-line">'
                f"status={escape(str(row['STATUS']))}; score={row['correlation_score_sig']:.4f}; "
                f"p={row['perm_p_median_nn']:.4f}; n_beep={int(row['n_beep'])}; n_smp={int(row['n_smp'])}; "
                f"median_nn={row['median_nn_mm']:.2f} mm"
                "</div>"
                f'<div class="map"><a href="assets/{png_name}" target="_blank"><img src="assets/{png_name}" alt="wafermap"></a></div>'
                '<div class="pairs">'
                + "".join(pair_cards)
                + "</div>"
                "</section>"
            )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<title>BEEP-SMP Suspicious Wafer Report</title>
<style>
body {{ background:#0c1115; color:#d9e3ea; font-family:Segoe UI, Tahoma, sans-serif; margin:20px; }}
h1 {{ color:#9ad1ff; margin-bottom:6px; }}
.sub {{ color:#8fa8b8; font-size:13px; margin-bottom:18px; }}
h2 {{ color:#ffd6a5; border-bottom:1px solid #23303a; padding-bottom:6px; margin-top:28px; }}
.wafer {{ background:#121a20; border:1px solid #22303a; border-radius:10px; padding:12px; margin:14px 0; }}
h3 {{ margin:0 0 6px; color:#e8f1f6; }}
.meta-line {{ color:#9fb4c1; font-size:12px; margin-bottom:10px; }}
.map img {{ width:340px; border:1px solid #2a3a45; border-radius:8px; }}
.pairs {{ margin-top:12px; display:grid; gap:10px; }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
.card {{ background:#162129; border:1px solid #2a3a45; border-radius:8px; padding:8px; }}
.meta {{ color:#c8d6df; font-size:11px; margin-bottom:6px; }}
.imgrow {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.imgrow img {{ width:100%; border-radius:6px; border:1px solid #2d3b46; }}
.missing {{ color:#90a4ae; font-size:11px; padding:8px 0; }}
</style>
</head>
<body>
<h1>BEEP-SMP Suspicious Wafer Report</h1>
<div class=\"sub\">Generated from permutation-ranked suspicious wafer-layer list.</div>
{''.join(sections)}
</body>
</html>
"""

    out_path = out_dir / "beep_smp_suspicious_report.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BEEP-SMP suspicious wafer HTML report")
    parser.add_argument(
        "--coords",
        type=Path,
        default=Path("outputs/defects/DEFECT_COORDINATES_EXTENDED.csv"),
        help="Defect coordinates CSV",
    )
    parser.add_argument(
        "--suspicious",
        type=Path,
        default=Path("rollups/BEEP_SMP_correlation/outputs/beep_smp_suspicious_significant.csv"),
        help="Suspicious wafer CSV from analysis script",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("outputs/defects/DEFECT_COORDINATES_EXTENDED_IMAGES.csv"),
        help="Image manifest CSV",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("rollups/BEEP_SMP_correlation/outputs/report"),
        help="Output folder for HTML and wafermaps",
    )
    parser.add_argument(
        "--top-per-status",
        type=int,
        default=20,
        help="Max wafer-layer sections per status",
    )
    parser.add_argument(
        "--pair-count",
        type=int,
        default=6,
        help="Nearest SMP-BEEP pairs shown per wafer",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    suspicious = pd.read_csv(args.suspicious, low_memory=False)
    coords = pd.read_csv(args.coords, low_memory=False)

    for col in ["WAFER_X_MM", "WAFER_Y_MM"]:
        coords[col] = pd.to_numeric(coords[col], errors="coerce")

    coords = coords.dropna(subset=["WAFER_ID", "LAYER", "CLASS", "WAFER_X_MM", "WAFER_Y_MM", "WAFER_KEY", "DEFECT_ID"])

    # Normalize IDs once for manifest joins.
    coords["WAFER_KEY"] = coords["WAFER_KEY"].apply(normalize_key)
    coords["DEFECT_ID"] = coords["DEFECT_ID"].apply(normalize_key)

    manifest_idx = load_manifest_index(args.manifest)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = build_report_html(
        suspicious_df=suspicious,
        coord_df=coords,
        manifest_idx=manifest_idx,
        out_dir=args.out_dir,
        top_per_status=args.top_per_status,
        pair_count=args.pair_count,
    )

    print(f"Wrote: {report_path}")


if __name__ == "__main__":
    main()
