"""Audit UNC wheelhouse coverage against a pinned requirements lockfile."""

from __future__ import annotations

import argparse
from pathlib import Path


IGNORE_PREFIXES = ("#", "-", "--")


def _normalize_name(name: str) -> str:
    return name.replace("_", "-").lower().strip()


def _read_lock_packages(lock_path: Path) -> list[tuple[str, str]]:
    packages: list[tuple[str, str]] = []
    for raw in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(IGNORE_PREFIXES):
            continue
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        packages.append((_normalize_name(name), version.strip()))
    return packages


def _wheelhouse_stems(wheelhouse_path: Path) -> set[str]:
    stems: set[str] = set()
    for file_path in wheelhouse_path.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in {".whl", ".zip", ".tar", ".gz"}:
            continue
        stems.add(_normalize_name(file_path.name))
    return stems


def audit_wheelhouse(lock_path: Path, wheelhouse_path: Path) -> tuple[int, int, list[str]]:
    required = _read_lock_packages(lock_path)
    stems = _wheelhouse_stems(wheelhouse_path)
    missing: list[str] = []

    for name, version in required:
        needle = f"{name}-{version}".lower()
        if not any(needle in stem for stem in stems):
            missing.append(f"{name}=={version}")

    return len(required), len(required) - len(missing), missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit wheelhouse coverage vs lockfile")
    parser.add_argument("--requirements-lock", required=True, help="Path to requirements lockfile")
    parser.add_argument("--wheelhouse", required=True, help="Path to wheelhouse directory")
    args = parser.parse_args()

    lock_path = Path(args.requirements_lock)
    wheelhouse_path = Path(args.wheelhouse)

    if not lock_path.is_file():
        raise FileNotFoundError(f"Requirements lock not found: {lock_path}")
    if not wheelhouse_path.is_dir():
        raise NotADirectoryError(f"Wheelhouse directory not found: {wheelhouse_path}")

    total, covered, missing = audit_wheelhouse(lock_path, wheelhouse_path)

    print(f"requirements_total={total}")
    print(f"requirements_covered={covered}")
    print(f"requirements_missing={len(missing)}")
    if missing:
        print("missing_packages:")
        for pkg in missing:
            print(f"- {pkg}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
