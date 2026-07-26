# Alloy Image Classification - ScriptHost Handoff

## Executive Summary
This handoff defines a production-safe path for deploying Alloy-based image classification into ScriptHost while preserving compatibility with a fixed Python runtime and UNC-hosted code/data.

The key decision is to separate:
- **Upstream Alloy repo sync** (read-only local clone updates from GitHub)
- **Production runtime packaging** (controlled wheelhouse + launcher behavior for drones)

This avoids reintroducing repo-level wheel hacks while still supporting strict ScriptHost environment constraints.

## Motivation
1. The original wheel workaround solved a real compatibility issue in a constrained environment.
2. Upstream Alloy has moved to Artifactory-based package installation and removed the bundled wheel artifact.
3. ScriptHost production jobs run in a fixed Python environment and can access UNC paths, so reliability depends on deployment packaging and deterministic runtime behavior, not notebook ergonomics.
4. The image classification workflow must be API-compatible, secure, and resumable at batch scale.

## BE Inline Context Alignment

When planning BE integration points or validating metadata/manifests, align this guide with the inline context system:

1. [../../../../docs/inline_pipeline/README.md](../../../../docs/inline_pipeline/README.md)
2. [../../../../INLINE_PIPELINE_DESIGN.md](../../../../INLINE_PIPELINE_DESIGN.md)
3. [../../../../docs/inline_pipeline/coordinates_and_images.md](../../../../docs/inline_pipeline/coordinates_and_images.md)
4. [../../../../docs/inline_pipeline/operations_and_hardening.md](../../../../docs/inline_pipeline/operations_and_hardening.md)

## Current Facts and Context
- Local clone now fast-forwarded to current `origin/main` (mono-directional sync only).
- Upstream commit history confirms intentional migration away from bundled wheel.
- ScriptHost scheduling docs confirm:
  - ZIP launcher entrypoint requirements
  - support for dynamic/live launcher mode
  - UNC share access from drones

## Architecture Decision
### Keep Alloy repo clean; package runtime dependencies separately.

Do **not** reapply old wheel modifications to `alloy-sandbox` setup scripts.

Instead:
1. Maintain a **ScriptHost deployment root** on UNC with launcher + pipeline code.
2. Maintain a **wheelhouse** for runtime dependency pinning and install stability.
3. Use **dynamic launcher mode** in ScriptHost when code must remain live-editable on UNC.

## Proposed Deployment Layout (UNC)

```text
\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\
  Scripthost_Scheduling\
    image_classification\
      launcher\
        launch_image_classification.py
      pipeline\
        classify_batch.py
        alloy_vision_adapter.py
        io_contract.py
      config\
        runtime_config.json
        label_schema.json
      deps\
        requirements_locked.txt
        wheelhouse\
          *.whl
      outputs\
      logs\
      tests\
        smoke_one_image.py
```

## Runtime Strategy (Wheelhouse Proposal)
### Goal
Deterministic installs in fixed ScriptHost Python env without relying on external network resolution during execution.

### Approach
1. Build wheelhouse from a controlled build machine matching ScriptHost Python version.
2. Pin dependency versions in `requirements_locked.txt`.
3. At job start:
   - Verify Python version compatibility.
   - Attempt import of required modules.
   - If missing, install from wheelhouse first.
   - Fall back to Artifactory only if explicitly allowed.

### Example install policy
- Primary: `pip install --no-index --find-links <UNC wheelhouse> -r requirements_locked.txt`
- Secondary (optional): Artifactory index fallback if approved.

## Alloy API Compatibility Guidance
Use canonical Alloy usage from current package:
- `from alloy.core.llm import image`
- Optional text orchestration: `from alloy.core.llm import chat`

Avoid obsolete paths such as direct internal module import patterns that bypass stable API surfaces.

## Security and Reliability Requirements
1. No hard-coded API keys in scripts.
- Use environment variables only.

2. SSL verification enabled by default.
- Support optional enterprise CA bundle path.

3. Response parsing resilience.
- Tolerate minor response-shape variations.
- Persist raw response excerpts for diagnostics.

4. Per-image fault isolation.
- One failed image must not kill entire batch.
- Log structured error rows.

5. Idempotent output identity.
- Do not key outputs by filename stem alone.
- Include stable image key (full path hash or canonical ID).

## Output Contract for Pipeline Joinability
Each classified record should include at minimum:
- `run_id`
- `timestamp_utc`
- `image_key` (stable deterministic key)
- `image_path_unc`
- `tool_or_chamber` (if available)
- `wafer_id` (if available)
- `model_name`
- `classification_label`
- `confidence`
- `raw_response_excerpt`
- `status` (`ok` or `error`)
- `error_message` (if status=error)

This is the minimum needed to join with BE pipeline manifests without destabilizing existing flow.

## ScriptHost Scheduling Integration
Use SQLPF dynamic launcher mode when pipeline modules are kept live on UNC:
- launcher remains stable scheduled entry point
- sibling implementation modules can be updated without repackaging full ZIP each change

## Execution Plan for Next Agent
1. API audit and import mapping
- Update notebook/script examples to canonical `alloy.core.llm` entry points.

2. Build production scripts
- `alloy_vision_adapter.py`: wraps image inference, auth, SSL, retries, parser.
- `classify_batch.py`: iterates folder/manifests, writes CSV/JSONL outputs.
- `launch_image_classification.py`: ScriptHost-compatible main(argv).

3. Build dependency bootstrap
- validate python version
- install from wheelhouse if needed
- emit environment diagnostics

4. Validate in phases
- smoke test one image
- batch test small folder
- failure-path tests: bad key, SSL error, malformed response

5. Schedule in ScriptHost
- package launcher ZIP
- dynamic mode if using live UNC modules
- set run-count/frequency per operational need

## Validation Checklist
- Import test passes under ScriptHost Python.
- One-image inference returns structured output row.
- Batch run handles mixed success/failure images.
- Outputs are parseable and include all schema fields.
- Re-run on same data does not duplicate rows unexpectedly.
- Logs are sufficient for root-cause analysis.

## Risks and Mitigations
1. Runtime drift between local and ScriptHost Python.
- Mitigation: wheelhouse built for exact runtime version.

2. Network/proxy interruptions.
- Mitigation: no-index wheelhouse-first installs.

3. Alloy backend response evolution.
- Mitigation: tolerant parser + raw excerpt capture.

4. UNC path intermittency.
- Mitigation: retry wrappers for file IO and checkpointed progress.

## Contacts and References
- Alloy team contact: `alloy@intel.com`
- Local repo docs: `alloy-sandbox/README.md`, `alloy-sandbox/utils/ENVIRONMENT_ARCHITECTURE.md`
- ScriptHost scheduling context:
  `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\Scripthost_Scheduling\docs\SH_SCHEDULING_USER_CONTEXT.md`
- Historical compatibility rationale:
  `20260330_py_version_resolution.md`

## Decision Log
- Chosen: clean upstream repo + separate production packaging layer.
- Deferred: reintroducing bundled wheel into repo.
- Reason: upstream intentionally migrated installation strategy; production constraints are better handled in deployment layer.