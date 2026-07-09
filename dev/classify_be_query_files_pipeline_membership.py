from __future__ import annotations

import ast
import csv
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
BE_ROOT = ROOT / "BE_QUERY_FILES"
OUT_CSV = ROOT / "artifacts" / "be_query_files_pipeline_membership.csv"


def choose_output_path() -> Path:
    """Return the primary output path, or a timestamped fallback if locked."""
    try:
        with OUT_CSV.open("w", newline="", encoding="utf-8"):
            pass
        return OUT_CSV
    except PermissionError:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return OUT_CSV.with_name(f"be_query_files_pipeline_membership_{stamp}.csv")


INLINE_ENTRYPOINTS = {
    "8M5CL_8M6CL_UPDATE.py",
}

SURF_ENTRYPOINTS = {
    "surf_scan_daily.py",
    "surf_scan_incremental.py",
    "surf_scan_seed.py",
    "surf_scan_update.py",
}


@dataclass(frozen=True)
class PyNode:
    rel_path: str
    module_name: str


def py_files() -> list[Path]:
    return sorted(p for p in BE_ROOT.rglob("*.py") if p.is_file())


def module_name_from_path(path: Path) -> str:
    rel = path.relative_to(BE_ROOT)
    parts = list(rel.parts)
    parts[-1] = parts[-1][:-3]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def module_aliases(path: Path, module_name: str) -> set[str]:
    rel = path.relative_to(BE_ROOT)
    aliases = {module_name, path.stem}
    if path.name == "__init__.py":
        pkg = module_name
        if pkg:
            aliases.add(pkg)
            aliases.add(pkg.split(".")[-1])
    else:
        aliases.add(rel.with_suffix("").as_posix().replace("/", "."))
    return {a for a in aliases if a}


def resolve_relative(base_module: str, level: int, target: str | None) -> str:
    base_parts = base_module.split(".") if base_module else []
    current_pkg = base_parts[:-1]
    up = max(level - 1, 0)
    prefix = current_pkg[:-up] if up else current_pkg
    if target:
        prefix = prefix + target.split(".")
    return ".".join(prefix)


def extract_import_targets(path: Path, module_name: str) -> set[str]:
    targets: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return targets

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # For absolute imports (level == 0), keep module as-is.
            # For relative imports (level > 0), resolve from current module.
            if node.level == 0:
                base = node.module or ""
            else:
                base = resolve_relative(module_name, node.level, node.module)
            if base:
                targets.add(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                if base:
                    targets.add(f"{base}.{alias.name}")
                else:
                    targets.add(alias.name)
    return targets


def _iter_string_constants(node: ast.AST) -> Iterable[str]:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield child.value


def _extract_script_vars(tree: ast.AST) -> dict[str, set[str]]:
    script_vars: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        py_names = {
            Path(s).name
            for s in _iter_string_constants(node.value)
            if s.lower().endswith(".py")
        }
        if not py_names:
            continue

        for target in node.targets:
            if isinstance(target, ast.Name):
                script_vars[target.id].update(py_names)
    return script_vars


def extract_script_exec_targets(path: Path, known_py_names: dict[str, set[str]]) -> set[str]:
    targets: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return targets

    script_vars = _extract_script_vars(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        called = False
        if isinstance(node.func, ast.Attribute):
            # Match subprocess.run(...)
            called = node.func.attr == "run"
        elif isinstance(node.func, ast.Name):
            # Match direct run(...) wrappers in some helper scripts.
            called = node.func.id == "run"

        if not called:
            continue

        candidate_names: set[str] = set()
        for arg in node.args:
            for s in _iter_string_constants(arg):
                if s.lower().endswith(".py"):
                    candidate_names.add(Path(s).name)
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id in script_vars:
                    candidate_names.update(script_vars[sub.id])

        for py_name in candidate_names:
            for rel in known_py_names.get(py_name, set()):
                targets.add(rel)

    return targets


def build_graph(nodes: dict[str, PyNode], aliases_to_rel: dict[str, str]) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    graph: dict[str, set[str]] = defaultdict(set)
    import_edges: dict[str, set[str]] = defaultdict(set)
    script_exec_edges: dict[str, set[str]] = defaultdict(set)

    known_py_names: dict[str, set[str]] = defaultdict(set)
    for rel_path in nodes:
        known_py_names[Path(rel_path).name].add(rel_path)

    # Handle short package imports used inside modular_processor, e.g.:
    # from core.base_processors import ProcessorBase
    # from processors.elwc_processor import OptimizedELWCProcessor
    short_pkg_aliases = {
        "core": "modular_processor.core",
        "processors": "modular_processor.processors",
    }

    for rel_path, node in nodes.items():
        src_path = BE_ROOT / rel_path
        targets = extract_import_targets(src_path, node.module_name)
        for target in targets:
            candidate = target
            while candidate:
                mapped = aliases_to_rel.get(candidate)
                if not mapped:
                    for short_pkg, full_pkg in short_pkg_aliases.items():
                        if candidate == short_pkg or candidate.startswith(f"{short_pkg}."):
                            rewritten = full_pkg + candidate[len(short_pkg):]
                            mapped = aliases_to_rel.get(rewritten)
                            if mapped:
                                break
                if mapped and mapped != rel_path:
                    graph[rel_path].add(mapped)
                    import_edges[rel_path].add(mapped)
                    break
                if "." not in candidate:
                    break
                candidate = candidate.rsplit(".", 1)[0]

        script_targets = extract_script_exec_targets(src_path, known_py_names)
        for mapped in script_targets:
            if mapped != rel_path:
                graph[rel_path].add(mapped)
                script_exec_edges[rel_path].add(mapped)

    return graph, import_edges, script_exec_edges


def bfs_reachable(seeds: set[str], graph: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    queue = deque(sorted(seeds))
    while queue:
        cur = queue.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in sorted(graph.get(cur, set())):
            if nxt not in seen:
                queue.append(nxt)
    return seen


def label(inline: bool, surf: bool) -> str:
    if inline and surf:
        return "BOTH"
    if inline:
        return "INLINE"
    if surf:
        return "SURF"
    return "NEITHER"


def confidence(rel_path: str, category: str) -> str:
    name = Path(rel_path).name.lower()
    if category in {"INLINE", "SURF", "BOTH"}:
        return "High"
    if name.startswith("_tmp_") or "test" in name or "debug" in name or "probe" in name:
        return "High"
    return "Medium"


def rationale(rel_path: str, category: str) -> str:
    name = Path(rel_path).name.lower()
    if category == "INLINE":
        return "reachable from inline orchestrator import graph"
    if category == "SURF":
        return "reachable from SURF orchestrator/entrypoint import graph"
    if category == "BOTH":
        return "reachable from both inline and SURF import graphs"
    if name.startswith("_tmp_"):
        return "temporary probe script not imported by pipeline entrypoints"
    if "test" in name or "debug" in name or "compare" in name:
        return "test/debug helper not imported by pipeline entrypoints"
    return "not import-reachable from documented pipeline entrypoints"


def main() -> None:
    files = py_files()

    nodes: dict[str, PyNode] = {}
    aliases_to_rel: dict[str, str] = {}

    for path in files:
        rel_path = str(path.relative_to(BE_ROOT)).replace("/", "\\")
        module = module_name_from_path(path)
        node = PyNode(rel_path=rel_path, module_name=module)
        nodes[rel_path] = node
        for alias in module_aliases(path, module):
            aliases_to_rel.setdefault(alias, rel_path)

    graph, import_edges, script_exec_edges = build_graph(nodes, aliases_to_rel)

    inline_seeds = {p for p in nodes if Path(p).name in INLINE_ENTRYPOINTS}
    surf_seeds = {p for p in nodes if Path(p).name in SURF_ENTRYPOINTS}

    inline_reach = bfs_reachable(inline_seeds, graph)
    surf_reach = bfs_reachable(surf_seeds, graph)

    output_path = choose_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relative_path",
                "file_name",
                "module_name",
                "in_inline_pipeline",
                "in_surf_pipeline",
                "pipeline_membership",
                "is_seed_entrypoint",
                "imported_by_count",
                "imports_count",
                "script_exec_targets_count",
                "edge_types",
                "confidence",
                "rationale",
            ],
        )
        writer.writeheader()

        reverse_graph: dict[str, set[str]] = defaultdict(set)
        for src, dsts in graph.items():
            for dst in dsts:
                reverse_graph[dst].add(src)

        for rel_path in sorted(nodes):
            file_name = Path(rel_path).name
            in_inline = rel_path in inline_reach
            in_surf = rel_path in surf_reach
            membership = label(in_inline, in_surf)
            writer.writerow(
                {
                    "relative_path": rel_path,
                    "file_name": file_name,
                    "module_name": nodes[rel_path].module_name,
                    "in_inline_pipeline": str(in_inline).lower(),
                    "in_surf_pipeline": str(in_surf).lower(),
                    "pipeline_membership": membership,
                    "is_seed_entrypoint": str(file_name in INLINE_ENTRYPOINTS or file_name in SURF_ENTRYPOINTS).lower(),
                    "imported_by_count": len(reverse_graph.get(rel_path, set())),
                    "imports_count": len(import_edges.get(rel_path, set())),
                    "script_exec_targets_count": len(script_exec_edges.get(rel_path, set())),
                    "edge_types": ",".join(
                        t
                        for t in [
                            "import" if import_edges.get(rel_path) else "",
                            "script_exec" if script_exec_edges.get(rel_path) else "",
                        ]
                        if t
                    )
                    or "none",
                    "confidence": confidence(rel_path, membership),
                    "rationale": rationale(rel_path, membership),
                }
            )

    print(f"Wrote {len(nodes)} rows to {output_path}")


if __name__ == "__main__":
    main()