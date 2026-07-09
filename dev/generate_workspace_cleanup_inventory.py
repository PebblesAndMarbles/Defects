from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "workspace_cleanup_inventory.csv"


def is_image_path(path: Path) -> bool:
    return any(part.lower() == "images" for part in path.parts)


def is_git_path(path: Path) -> bool:
    return any(part.lower() == ".git" for part in path.parts)


def top_level_folder(rel: Path) -> str:
    return rel.parts[0] if len(rel.parts) > 1 else "[root]"


def file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if suffix else "[no extension]"


def production_vs_debug(rel: Path, name: str) -> str:
    rel_lower = str(rel).replace("/", "\\").lower()
    name_lower = name.lower()
    debug_markers = (
        "\\dev\\",
        "\\old\\",
        "\\rollups\\",
        "\\debug_logs\\",
    )
    if any(marker in rel_lower for marker in debug_markers):
        return "DEBUG"
    if any(
        token in name_lower
        for token in (
            "debug",
            "probe",
            "mwe",
            "tmp",
            "test",
            "adhoc",
            "compare",
            "validate",
            "explore",
            "scratch",
            "copy",
            "draft",
        )
    ):
        return "DEBUG"
    return "PRODUCTION"


def suggested_action(rel: Path, name: str, prod_debug: str) -> str:
    rel_lower = str(rel).replace("/", "\\").lower()
    name_lower = name.lower()

    if rel_lower.startswith("be_query_files\\") or rel_lower.startswith("docs\\"):
        return "keep"
    if name_lower in {
        "pipeline_design.md",
        "surf_scan_pipeline_design.md",
        "surf_scan_pipeline_design_rf.md",
        "design_index.md",
        "git_status.md",
        "be.code-workspace",
    }:
        return "keep"
    if rel_lower.startswith("old\\") or rel_lower.startswith("rollups\\"):
        return "archive"
    if rel_lower.startswith("debug_logs\\"):
        return "delete"
    if rel_lower.startswith("outputs\\"):
        return "archive"
    if rel_lower.startswith("artifacts\\"):
        return "keep"
    if rel_lower.startswith("dev\\"):
        return "move"
    if any(
        token in name_lower
        for token in (
            "debug",
            "probe",
            "mwe",
            "adhoc",
            "compare",
            "validate",
            "explore",
            "draft",
            "copy",
            "tmp",
            "test",
        )
    ):
        return "move"
    return "keep" if prod_debug == "PRODUCTION" else "move"


def suggested_target(action: str, rel: Path) -> str:
    rel_lower = str(rel).replace("/", "\\").lower()
    if action == "keep":
        return "as-is"
    if action == "delete":
        return "remove"
    if action == "archive":
        if rel_lower.startswith("old\\"):
            return "OLD\\"
        if rel_lower.startswith("rollups\\"):
            return "rollups\\"
        if rel_lower.startswith("outputs\\"):
            return "archive\\outputs"
        return "archive\\review"
    if action == "move":
        if rel_lower.startswith("dev\\"):
            return "dev\\"
        return "dev\\review"
    return "review"


def confidence(action: str, prod_debug: str, rel: Path) -> str:
    if action == "keep" and prod_debug == "PRODUCTION":
        return "High"
    if action in {"delete", "archive"}:
        return "Medium"
    if rel.parts and rel.parts[0].lower() in {"dev", "old", "rollups", "debug_logs"}:
        return "High"
    return "Low"


def reason(rel: Path, name: str) -> str:
    rel_lower = str(rel).replace("/", "\\").lower()
    name_lower = name.lower()
    if rel_lower.startswith("be_query_files\\"):
        return "pipeline code or entrypoint"
    if rel_lower.startswith("docs\\"):
        return "supporting documentation"
    if name_lower in {
        "pipeline_design.md",
        "surf_scan_pipeline_design.md",
        "surf_scan_pipeline_design_rf.md",
        "design_index.md",
        "git_status.md",
        "be.code-workspace",
    }:
        return "workspace entry or design doc"
    if rel_lower.startswith("dev\\"):
        return "development or exploratory material"
    if rel_lower.startswith("old\\") or rel_lower.startswith("rollups\\"):
        return "legacy or superseded output"
    if rel_lower.startswith("outputs\\") or rel_lower.startswith("artifacts\\"):
        return "generated output or manifest"
    if rel_lower.startswith("debug_logs\\"):
        return "transient debug log"
    if any(token in name_lower for token in ("debug", "probe", "mwe", "adhoc", "compare", "validate", "explore", "draft", "copy", "tmp", "test")):
        return "one-off analysis or scratch file"
    return "general workspace file"


@dataclass(frozen=True)
class InventoryRow:
    relative_path: str
    file_name: str
    file_type: str
    file_size_bytes: int
    file_size_kb: float
    file_size_mb: float
    last_modified: str
    days_since_mod: float
    age_days: float
    depth: int
    top_level_folder: str
    production_vs_debug: str
    suggested_action: str
    suggested_target: str
    confidence: str
    reason: str


def build_inventory() -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    now = datetime.now(timezone.utc)

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path == OUTPUT:
            continue
        if is_image_path(path) or is_git_path(path):
            continue

        rel = path.relative_to(ROOT)
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        age_days = round((now - mtime).total_seconds() / 86400.0, 1)
        file_size_bytes = int(stat.st_size)
        file_size_kb = round(file_size_bytes / 1024.0, 2)
        file_size_mb = round(file_size_bytes / (1024.0 * 1024.0), 3)
        prod_debug = production_vs_debug(rel, path.name)
        action = suggested_action(rel, path.name, prod_debug)

        rows.append(
            InventoryRow(
                relative_path=str(rel).replace("/", "\\"),
                file_name=path.name,
                file_type=file_type(path),
                file_size_bytes=file_size_bytes,
                file_size_kb=file_size_kb,
                file_size_mb=file_size_mb,
                last_modified=mtime.strftime("%Y-%m-%d %H:%M:%S"),
                days_since_mod=age_days,
                age_days=age_days,
                depth=len(rel.parts) - 1,
                top_level_folder=top_level_folder(rel),
                production_vs_debug=prod_debug,
                suggested_action=action,
                suggested_target=suggested_target(action, rel),
                confidence=confidence(action, prod_debug, rel),
                reason=reason(rel, path.name),
            )
        )

    rows.sort(key=lambda row: (row.suggested_action, row.production_vs_debug, row.relative_path.lower()))
    return rows


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = build_inventory()

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relative_path",
                "file_name",
                "file_type",
                "file_size_bytes",
                "file_size_kb",
                "file_size_mb",
                "last_modified",
                "days_since_mod",
                "age_days",
                "depth",
                "top_level_folder",
                "production_vs_debug",
                "suggested_action",
                "suggested_target",
                "confidence",
                "reason",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)

    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()