# Wheelhouse Blocker Summary (2026-07-26)

## Purpose
Capture the current runtime blocker preventing Alloy classification execution with the ScriptHost-aligned interpreter and UNC-only dependency policy.

## Decision status (important)

Development/testing with the current Alloy API is approved and can continue now.

Specifically:

- Continue feature development and prompt/schema experiments using the working local Alloy environment.
- Treat wheelhouse as a ScriptHost-parity and production-validation blocker only.
- Do not interpret this blocker as a stop-work condition for Phase 1 experimentation.

## Scope and environment
- Interpreter (required for parity):
  - `c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe`
- UNC runtime profile:
  - `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\Alloy_Apps\_shared_runtime`
- Wheelhouse path:
  - `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\Alloy_Apps\_shared_runtime\wheelhouse\py311`
- Lockfile path:
  - `\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\Alloy_Apps\_shared_runtime\constraints\requirements.lock.py311.txt`

## What was previously proven
Historical project outputs show successful Alloy runs (`status: ok`) for both structured and caption workflows under prior setup:
- `images/Alloy_Class/outputs/phase1/phase1_results.jsonl`
- `images/Alloy_Class/outputs/captions/caption_results.jsonl`

Current scripts use canonical Alloy import path:
- `from alloy.core.llm import image`

## Current blocker
Resolved for current baseline: UNC wheelhouse parity is now unblocked for the pinned offline set in this document.

Current state:

- `Runtime unblocked`: ScriptHost interpreter can import `alloy` and `from alloy.core.llm import image`.
- `Wheelhouse parity unblocked`: audit and no-index bootstrap/install validations pass for the current pinned set.

### Evidence 0: Offline copy workaround succeeded

Using local venv source:
- `C:\Users\tbatson\OneDrive - Intel Corporation\Documents\Projects\Alloy\alloy-sandbox\.venv\Lib\site-packages`

Copied package trees into ScriptHost Python path:
- `c:\Users\tbatson\My Programs\SQLPathFinder3\Python3`

Post-copy verification:
- `scripthost_alloy_api_ok=True`
- `requests=2.33.1`
- `urllib3=2.6.3`

Important note:
- this enables immediate execution and testing
- wheelhouse artifacts were subsequently created offline from local installed packages to restore no-index parity

### Evidence 5: Wheelhouse parity restored

Wheelhouse now contains:

- `requests-2.33.1-py3-none-any.whl`
- `urllib3-2.6.3-py3-none-any.whl`
- `certifi-2026.2.25-py3-none-any.whl`
- `idna-3.11-py3-none-any.whl`
- `charset_normalizer-3.4.6-cp311-cp311-win_amd64.whl`

Audit result:

- `requirements_total=5`
- `requirements_covered=5`
- `requirements_missing=0`

No-index clean target install result:

- `target_install_exit=0`

Shared bootstrap verification result:

- `parity_bootstrap_ok=True`

### Evidence 1: Alloy import missing before bootstrap
Preflight result:
- `alloy_present=False`

### Evidence 2: Bootstrap failure from UNC wheelhouse
Command path:
- `...\bootstrap\install_from_wheelhouse.ps1`

Error:
- `Could not find a version that satisfies the requirement requests==2.32.3`
- `No matching distribution found for requests==2.32.3`

### Evidence 3: Wheelhouse audit (new utility)
Audit command:
- `python tools/wheelhouse_audit.py --requirements-lock <lock> --wheelhouse <wheelhouse>`

Audit result:
- `requirements_total=2`
- `requirements_covered=0`
- `requirements_missing=2`
- Missing:
  - `requests==2.32.3`
  - `urllib3==2.2.2`

### Evidence 4: Wheelhouse directory contents
Current wheelhouse directory contains only:
- `README.md`

No wheel artifacts are present for locked requirements.

## Impact
- Pair-safe classification logic is implemented and tested for gating behavior (`max_pairs`, BF/DF pairing), but execution cannot reach Alloy inference under the required interpreter.
- Production-parity validation is blocked until UNC wheelhouse coverage matches lockfile.

Updated impact:

- ScriptHost runtime execution is possible.
- Wheelhouse/audit parity is restored for the current pinned baseline.

Practical interpretation:

- `Allowed now`: API workflow development, pairing logic, metadata joins, prompt and report iteration.
- `Blocked until wheelhouse`: ScriptHost-parity runs and no-index production-style validation with the fixed interpreter.

## Actions already completed in code/docs
1. Added fail-fast Alloy preflight in classifier:
- `images/Alloy_Class/pipelines/classify_phase1_batch.py`

2. Added wheelhouse coverage audit utility:
- `images/Alloy_Class/tools/wheelhouse_audit.py`

3. Added ScriptHost-parity preflight steps to runbook:
- `images/Alloy_Class/docs/PHASE1_RUNBOOK.md`

## Required owner action (wheelhouse)
1. Keep UNC wheelhouse and lockfile aligned whenever package versions change.
2. Treat the following as the current offline parity baseline:
- `requests==2.33.1`
- `urllib3==2.6.3`
- `certifi==2026.2.25`
- `idna==3.11`
- `charset_normalizer==3.4.6`
3. If pin changes are needed later, regenerate wheels offline from an approved source environment and re-run audit/bootstrap verification.

## Verification sequence after wheelhouse update
1. Audit wheelhouse coverage:
- `python tools/wheelhouse_audit.py ...`
- Expect: `requirements_missing=0`

2. Bootstrap interpreter from UNC wheelhouse:
- `install_from_wheelhouse.ps1 -PythonExe <exact interpreter> -WheelhousePath <UNC> -RequirementsFile <UNC lock>`

3. Verify imports:
- `python -c "import alloy; from alloy.core.llm import image; print('alloy_import_ok=True')"`

4. Re-run bounded classification (handful first):
- `python pipelines/classify_phase1_batch.py --phase1-settings config/phase1_settings_pairsafe.json --max-pairs 3 ...`

## Notes for handoff
- This is an environment/content blocker, not a classifier logic blocker.
- Keep UNC-only dependency policy to preserve ScriptHost parity.
- Do not relax to internet/index installs for production validation unless explicitly approved.
- Use two-track execution:
  - Track A (active now): local Alloy API development/testing.
  - Track B (gated): ScriptHost-parity verification after wheelhouse is populated.
- A temporary offline local-package copy workaround has already been applied to the ScriptHost interpreter and verified for Alloy imports.

Status update:

- Track B gate has been cleared for the current baseline via offline wheelhouse artifact generation and no-index verification.

## Final verification (post-unblock)

Using the exact ScriptHost-aligned interpreter and UNC/runtime-local paths from this workspace:

- Bounded pair-safe classification run (`max_pairs=3`) completed successfully.

Result summary:

- `processed=6`
- `failed=0`
- `skipped=0`
- `total_pairs=3`
- `selected_pairs=3`
- `selected_images=6`

Interpretation:

- End-to-end parity path is now operational for capped BF/DF runs.
- Phase 1 development and ScriptHost-parity validation can proceed under current baseline pins.

## Post-unblock addendum: transient raw-mode validation (2026-07-26)

Transient raw-image flow is validated in the same ScriptHost-parity environment.

Run context:

- Command mode: bounded pair-safe cohort with `--raw-image-mode --max-pairs 3`
- Run id: `phase1_raw_transient_verify_20260726`

Result summary:

- `processed=6`
- `failed=0`
- `skipped=0`
- `total_pairs=3`
- `selected_pairs=3`
- `raw_used=6`
- `raw_deleted=6`

Interpretation:

- Raw images were downloaded for inference and deleted after inference for all processed rows.
- Burned-image linkage remained intact via output provenance fields (`burned_image_path`, `inference_image_path`, `raw_download_status`).
- This satisfies the current Phase 1 transient-raw handling objective without persistent raw-library growth.

Cross-document alignment:

- Run guidance: `PHASE1_RUNBOOK.md`
- Acceptance status and gates: `PHASE1_ACCEPTANCE_CHECKLIST.md`
