# ScriptHost Launcher Pattern: Scheduled Wrapper + Live Network Modules

## Purpose
This document describes a practical deployment pattern for ScriptHost-style schedulers where:

- The scheduler runs a small, stable launcher script.
- The launcher imports and executes larger pipeline modules from a network/shared workspace.
- Operational teams can modify unscheduled modules in real time without re-registering or re-scheduling the ScriptHost job.

This is useful when schedule ownership is strict, but code iteration on business logic needs to stay fast.

---

## High-Level Architecture

1. Scheduled artifact (small and stable)
- A tiny launcher file is packaged/zipped and scheduled in ScriptHost.
- The launcher only sets module path and calls one orchestration entrypoint.

2. Unscheduled implementation modules (network drive)
- Orchestrator and processing modules live on the network workspace.
- These modules are imported at runtime by the launcher.
- Edits to these modules take effect on the next scheduled run.

3. Runtime outputs and artifacts
- Outputs, manifests, and run summaries are written under workspace-managed output/artifact folders.
- Logs provide step-by-step status and completion evidence.

---

## Example from Current SURF Setup

### Scheduled launcher (minimal)
`BE_QUERY_FILES/surf_scan_daily.py` is intentionally minimal:

```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from surf_scan_update import main


if __name__ == "__main__":
    raise SystemExit(main(["--mode", "incremental", "--run-images", *sys.argv[1:]]))
```

Why this works:
- It pins execution to a single stable entrypoint (`main`).
- It delegates all behavior to `surf_scan_update.py` and downstream modules.
- It avoids duplicated logic in the scheduled layer.

### Orchestrator (unscheduled, live-editable)
`BE_QUERY_FILES/surf_scan_update.py` controls pipeline steps:
- Coordinates stage
- ELWC RF refresh stage/apply
- Stacked EDX derivation
- Zero-timebin summary
- Optional images stage
- Image retention prune
- Run summary + artifact writes

`run()` composes these steps, and `main()` maps CLI arguments to defaults and runtime behavior.

### Path/config indirection
`BE_QUERY_FILES/pipeline_config.py` centralizes paths and environment overrides:
- `BE_PIPELINE_ROOT`
- `BE_SHARED_DATA_ROOT`

This keeps launcher code static while paths and assets can be managed centrally.

---

## Why This Pattern Is Effective

1. Schedule stability
- ScriptHost schedule points to one durable launcher artifact.
- No frequent schedule edits required for normal code changes.

2. Fast iteration
- Business logic changes happen in unscheduled modules.
- Next scheduler invocation picks up updates.

3. Reduced operational risk
- Minimal launcher has low churn and low breakage risk.
- Complex logic lives in versioned modules where code review/testing is easier.

4. Better separation of concerns
- Scheduler concern: when to run.
- Pipeline concern: what to run.

---

## Implementation Blueprint for a New Workspace

Use this structure as a template:

```text
<workspace>/
  BE_QUERY_FILES/
    my_pipeline_daily.py           # scheduled launcher (tiny)
    my_pipeline_update.py          # orchestrator (live-editable)
    my_pipeline_step_a.py
    my_pipeline_step_b.py
    pipeline_config.py
  outputs/
  artifacts/
  debug_logs/
```

### 1) Create minimal launcher

```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from my_pipeline_update import main


if __name__ == "__main__":
    raise SystemExit(main(["--mode", "incremental", *sys.argv[1:]]))
```

### 2) Put all logic in orchestrator + modules
- Keep launcher free of business logic.
- Put orchestration in `my_pipeline_update.py`.
- Put heavy logic in dedicated step modules.

### 3) Make paths environment-driven
- Use a central `pipeline_config.py`.
- Support environment overrides for root/shared paths.

### 4) Emit artifacts every run
- Write run summary JSON.
- Write artifact manifest with paths and step completion.
- Keep logs step-scoped (`[step_name] started/finished`).

---

## Scheduling Model on ScriptHost

Recommended practice:

1. Register one scheduled job for the launcher zip/script only.
2. Keep launcher file changes rare (treat as interface contract).
3. Allow frequent updates in unscheduled imported modules.
4. Validate by checking:
- Step completion logs
- Run summary JSON
- Artifact manifest paths

Operational note:
- If ScriptHost caches extracted zip content per run, live module edits are naturally picked up each run when it re-extracts.
- If your platform snapshots code differently, verify cache/extraction behavior once with a controlled test change.

---

## Guardrails and Governance

1. Backward-compatible launcher contract
- Keep function signature and import path stable (`from ... import main`).
- Parse optional args in orchestrator to avoid launcher churn.

2. Fail-fast startup checks
- Validate required folders, writable outputs, and required env vars early.

3. Explicit step boundaries
- Each step logs start/end and duration.
- Keep step outputs idempotent where possible.

4. Safe rollback path
- Keep previous orchestrator/module versions available.
- Roll back unscheduled module files without touching schedule registration.

5. Change control for production columns
- Treat output schema as a contract.
- For schema retirements, prune historical columns during merge/apply paths to prevent reintroduction.

---

## Pros and Tradeoffs

Pros:
- Rapid runtime updates without schedule changes
- Lower operational overhead
- Clear separation between scheduling and logic

Tradeoffs:
- Requires disciplined module/interface management
- Runtime module import path must be reliable
- Strong logging/artifacts are essential for supportability

---

## Copy/Paste Checklist for New Workspace

- [ ] Create tiny scheduled launcher (`*_daily.py`).
- [ ] Create orchestrator with `main()` and `run()`.
- [ ] Centralize filesystem paths in `pipeline_config.py`.
- [ ] Add per-step logging and duration metrics.
- [ ] Write run summary + artifact manifest each run.
- [ ] Keep schedule pointed only at launcher artifact.
- [ ] Update unscheduled modules for live behavior changes.

---

## Optional: Standard Entry Contract

For consistency across pipelines, standardize launcher contract as:
- `main(argv: list[str] | None = None) -> int`
- `raise SystemExit(main([...]))`
- `--mode` defaults to `incremental`
- optional `--lookback-days`, `--run-images`, `--dry-run` style switches

This keeps all scheduled jobs uniform and easier to operate.
