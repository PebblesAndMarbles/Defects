# Alloy Updates and Runtime Tracking

## Purpose
Track Alloy-related changes made for this Phase 1 workflow, and define the runtime patch needed to expose native usage metrics before scaling.

## Date
- 2026-07-26

## Workspace Changes Implemented

### 1) Stage A/B prompt test assets
- Added config: `config/stage_ab_prompt_tests.json`
- Added smoke config: `config/stage_ab_prompt_tests_smoke.json`
- Added runner: `reporting/run_stage_ab_prompt_tests.py`

Behavior:
- Runs Stage A and Stage B prompts on BF/DF pairs.
- Writes row-level results to `outputs/stage_ab_tests/stage_ab_results.jsonl`.
- Writes summary metrics to `outputs/stage_ab_tests/stage_ab_summary.json`.

### 2) Token usage metrics behavior
Current runtime (`c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/alloy/core/llm/core.py`) returns text-only content for `image()`, so native usage fields are not currently exposed.

Runner behavior in current state:
- Uses fallback token estimation when native usage is absent.
- Records source counts in summary:
  - `native_usage_rows`
  - `estimated_usage_rows`

### 3) Forward compatibility
`run_stage_ab_prompt_tests.py` now detects whether `alloy.core.llm.image` supports `include_usage` and passes it automatically when available.

This allows the same runner to switch from estimated to native token metrics immediately after runtime update.

### 4) Runtime wrapper patch applied (local interpreter)
Patched file:
- `c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/alloy/core/llm/core.py`

Patch applied:
- Added `include_usage: bool = False` to `chat()` and `image()`.
- Default behavior unchanged: returns string content/description.
- When `include_usage=True`, returns a dict including content/description and `usage`.

Validation results:
- `image_default_type=str`
- `image_usage_type=dict` with keys `description,id,model,usage`
- `chat_default_type=str`
- `chat_usage_type=dict` with keys `content,id,model,usage`
- `usage` currently `None` from backend response.

## Proposed Alloy Runtime Patch (for wheelhouse update)

Target file in runtime package:
- `alloy/core/llm/core.py`

Current behavior:
- `chat()` returns only `result.get("content")`.
- `image()` returns only `result.get("description")`.

Proposed API-compatible extension:

1. Add optional parameter to `chat()` and `image()`:
- `include_usage: bool = False`

2. If `include_usage=False`:
- Keep current return behavior unchanged (string content/description).

3. If `include_usage=True` and result is dict:
- Return dict payload with both content and usage:
  - For `chat()`:
    - `content`
    - `usage` (pass through if present)
    - optional metadata fields if present (`model`, `id`, etc.)
  - For `image()`:
    - `description`
    - `usage` (pass through if present)
    - optional metadata fields if present

4. If `include_usage=True` but usage is absent:
- Return same dict shape with `usage: null`.

Why this approach:
- Preserves backward compatibility for existing scripts.
- Exposes native usage when backend supports it.
- Enables pre-scale cost/usage checks without downstream API churn.

## Suggested Acceptance Check for Usage Tracking
Run after wheelhouse/runtime refresh:

1. Re-run Stage A/B smoke:
- `python images/Alloy_Class/reporting/run_stage_ab_prompt_tests.py --config images/Alloy_Class/config/stage_ab_prompt_tests_smoke.json --input-folder images/Alloy_Class/inputs --output-folder images/Alloy_Class/outputs/stage_ab_tests --run-id stage_ab_postpatch_smoke`

2. Confirm in summary:
- `native_usage_rows > 0`
- `estimated_usage_rows` decreases (ideally to 0)

3. If native usage remains 0:
- Verify backend response payload includes usage.
- If backend omits usage, keep estimator and document limitation.

## Wheelhouse/Runtime Update Readiness Notes
Before broad scaling (20+ pairs and production-adjacent runs), prefer native usage visibility.

Recommended order:
1. Patch alloy runtime wrapper with `include_usage`.
2. Build/package updated wheel.
3. Update wheelhouse lock reference if package version changes.
4. Re-bootstrap ScriptHost-parity environment.
5. Run Stage A/B smoke and then 20-pair benchmark.

## Current Known Limitation
- Existing ScriptHost-parity runtime currently returns no native usage fields for `image()` calls.
- Token totals currently represent estimator values.

Even with `include_usage` support patched in the wrapper, backend currently does not populate `usage`, so summary remains estimator-driven.

## BEEP Readiness Note
- The image library and manifest contain substantial BEEP-labeled BF/DF pairs (`_BEEP_` in filename).
- These BEEP pairs are suitable for a follow-on validation dataset to test whether SMP-labeled samples are being misclassified as BEEP-like outcomes.
- Current optimization focus is SMP-only runtime/cost reduction and stable raw transient workflow performance.
