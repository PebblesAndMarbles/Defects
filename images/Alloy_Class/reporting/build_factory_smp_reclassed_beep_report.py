from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd


def _norm(value: object) -> str:
    return str(value or "").strip()


def _counts_by_chamber(df: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chamber, grp in df.groupby("chamber", dropna=False):
        key = _norm(chamber)
        counts[key] = int(len(grp))
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def render_html(rows: list[dict[str, str]], counts_by_chamber: dict[str, int], out_html: Path) -> None:
    stat_total = len(rows)
    chamber_rows = "".join(
        f"<tr><td>{html.escape(chamber)}</td><td>{count}</td></tr>"
        for chamber, count in counts_by_chamber.items()
    )

    cards: list[str] = []
    for row in rows:
        bright_path = _norm(row.get("bright_image_path"))
        dark_path = _norm(row.get("dark_image_path"))
        cards.append(
            "<section class='card'>"
            "<div class='card-head'>"
            f"<div class='meta'>{html.escape(_norm(row.get('benchmark_id')))}</div>"
            f"<div class='meta'>{html.escape(_norm(row.get('chamber')))}</div>"
            f"<div class='meta'>Defect {html.escape(_norm(row.get('defect_id')))}</div>"
            f"<div class='meta'>Factory: {html.escape(_norm(row.get('factory_class_label')))}</div>"
            f"<div class='meta'>Adj: {html.escape(_norm(row.get('adjudicated_coarse_class')))}</div>"
            f"<div class='meta'>{html.escape(_norm(row.get('inspection_time')))}</div>"
            "<div class='pill'>factory_smp_to_b</div>"
            "</div>"
            "<div class='pair'>"
            "<div class='imgbox'>"
            "<div class='title'>BF (image_id=2)</div>"
            f"<a href='{html.escape(bright_path)}' target='_blank' rel='noopener'>"
            f"<img src='{html.escape(bright_path)}' alt='BF image'>"
            "</a>"
            f"<div class='caption'>{html.escape(_norm(row.get('bright_image_name')))}</div>"
            "</div>"
            "<div class='imgbox'>"
            "<div class='title'>DF (image_id=3)</div>"
            f"<a href='{html.escape(dark_path)}' target='_blank' rel='noopener'>"
            f"<img src='{html.escape(dark_path)}' alt='DF image'>"
            "</a>"
            f"<div class='caption'>{html.escape(_norm(row.get('dark_image_name')))}</div>"
            "</div>"
            "</div>"
            "</section>"
        )

    html_doc = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Factory SMALL_PARTICLE Reclassed to B Report</title>
  <style>
    body {{ margin: 0; background: #0f151c; color: #e6edf3; font-family: Segoe UI, Arial, sans-serif; }}
    .head {{ background: #13202b; border-bottom: 1px solid #25384a; padding: 14px 18px; }}
    .h1 {{ font-size: 20px; font-weight: 700; margin: 0 0 8px 0; }}
    .sub {{ font-size: 12px; color: #9fb2c5; }}
    .main {{ padding: 16px; }}
    .summary {{ background: #121a23; border: 1px solid #283544; border-radius: 10px; padding: 12px; margin-bottom: 14px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 520px; }}
    th, td {{ border: 1px solid #2a3a4b; padding: 6px 8px; text-align: left; font-size: 12px; }}
    th {{ background: #1a2632; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(540px, 1fr)); gap: 12px; }}
    .card {{ background: #121a23; border: 1px solid #283544; border-radius: 12px; padding: 12px; }}
    .card-head {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }}
    .meta {{ background: #1a2632; border: 1px solid #2a3a4b; border-radius: 8px; padding: 4px 8px; font-size: 12px; }}
    .pill {{ border-radius: 999px; padding: 5px 10px; color: #fff; font-size: 12px; font-weight: 700; background: #c9681a; }}
    .pair {{ display: grid; grid-template-columns: repeat(2, minmax(0, max-content)); gap: 10px; justify-content: start; align-items: start; }}
    .imgbox {{ background: #0d131a; border: 1px solid #263646; border-radius: 8px; padding: 8px; width: fit-content; max-width: 100%; }}
    .title {{ font-size: 12px; color: #9fb2c5; margin-bottom: 6px; }}
    img {{ width: 240px; max-width: min(240px, 100%); max-height: 240px; object-fit: contain; border: 1px solid #314557; background: #000; display: block; }}
    .caption {{ margin-top: 6px; font-size: 11px; color: #9fb2c5; word-break: break-all; }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .pair {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class=\"head\">
    <h1 class=\"h1\">Factory SMALL_PARTICLE Reclassed to B</h1>
    <div class=\"sub\">{stat_total} rows from benchmark_candidates_14day.csv</div>
  </header>
  <main class=\"main\">
    <section class=\"summary\">
      <h2>Counts by chamber</h2>
      <table>
        <thead><tr><th>chamber</th><th>count</th></tr></thead>
        <tbody>{chamber_rows}</tbody>
      </table>
    </section>
    <section class=\"grid\">{''.join(cards)}</section>
  </main>
</body>
</html>
"""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build report for factory SMALL_PARTICLE rows adjudicated as b")
    parser.add_argument(
        "--input-csv",
        default="images/Alloy_Class/artifacts/benchmark_candidates_14day.csv",
        help="Benchmark adjudication CSV",
    )
    parser.add_argument(
        "--output-html",
        default="images/Alloy_Class/reporting/factory_smp_reclassed_beep_report.html",
        help="Output html report path",
    )
    parser.add_argument(
        "--output-csv",
        default="images/Alloy_Class/artifacts/factory_smp_reclassed_beep.csv",
        help="Output filtered csv path",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv, dtype=str).fillna("")
    required = [
        "benchmark_id",
        "chamber",
        "defect_id",
        "inspection_time",
        "factory_class_label",
        "adjudicated_coarse_class",
        "bright_image_name",
        "dark_image_name",
        "bright_image_path",
        "dark_image_path",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    filtered = df[
        df["factory_class_label"].str.strip().str.upper().eq("SMALL_PARTICLE")
        & df["adjudicated_coarse_class"].str.strip().str.lower().eq("b")
    ].copy()

    filtered = filtered.sort_values(["benchmark_id"], kind="stable")

    out_csv = Path(args.output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(out_csv, index=False)

    rows = filtered.to_dict(orient="records")
    render_html(rows, _counts_by_chamber(filtered), Path(args.output_html))

    print(f"rows={len(filtered)}")
    print(f"wrote_csv={Path(args.output_csv).resolve()}")
    print(f"wrote_html={Path(args.output_html).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
