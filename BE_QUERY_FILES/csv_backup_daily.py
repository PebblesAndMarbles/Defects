from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage selected CSV/artifact files, commit when changed, and push to origin. "
            "Designed for scheduler/roaming-bot execution."
        )
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help=(
            "Glob relative to repo root. Can be repeated. "
            "No defaults are applied; explicit opt-in is required."
        ),
    )
    parser.add_argument(
        "--message-prefix",
        default="csv-backup",
        help="Commit message prefix (default: csv-backup).",
    )
    return parser.parse_args(argv)


def resolve_targets(repo_root: Path, include_globs: list[str]) -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()

    for pattern in include_globs:
        for path in repo_root.glob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_root)
            if rel in seen:
                continue
            seen.add(rel)
            targets.append(rel)

    return sorted(targets)


def ensure_git_ready(repo_root: Path) -> None:
    check = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    if check.returncode != 0:
        raise RuntimeError(
            "This folder is not a git repository or is inaccessible for git commands."
        )


def stage_targets(repo_root: Path, targets: list[Path]) -> None:
    if not targets:
        print("No files matched include globs. Nothing to back up.")
        return

    add = run_git(repo_root, ["add", "--", *[str(p) for p in targets]])
    if add.returncode != 0:
        raise RuntimeError(f"git add failed:\n{add.stderr.strip()}")


def has_staged_changes(repo_root: Path) -> bool:
    diff = run_git(repo_root, ["diff", "--cached", "--quiet"])
    return diff.returncode == 1


def commit_and_push(repo_root: Path, message_prefix: str) -> int:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"{message_prefix}: {stamp}"

    commit = run_git(repo_root, ["commit", "-m", commit_message])
    if commit.returncode != 0:
        print(commit.stdout)
        print(commit.stderr, file=sys.stderr)
        return commit.returncode

    branch = run_git(repo_root, ["branch", "--show-current"])
    if branch.returncode != 0:
        print(branch.stderr, file=sys.stderr)
        return branch.returncode

    current_branch = branch.stdout.strip()
    if not current_branch:
        print("Unable to detect current git branch.", file=sys.stderr)
        return 2

    push = run_git(repo_root, ["push", "-u", "origin", current_branch])
    if push.stdout.strip():
        print(push.stdout.strip())
    if push.stderr.strip():
        print(push.stderr.strip())
    return push.returncode


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    include_globs = args.include

    try:
        ensure_git_ready(repo_root)
        if not include_globs:
            print("No --include globs were provided. POC mode: nothing will be backed up.")
            return 0

        targets = resolve_targets(repo_root, include_globs)
        stage_targets(repo_root, targets)

        if not has_staged_changes(repo_root):
            print("No staged changes detected. Backup push skipped.")
            return 0

        return commit_and_push(repo_root, args.message_prefix)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
