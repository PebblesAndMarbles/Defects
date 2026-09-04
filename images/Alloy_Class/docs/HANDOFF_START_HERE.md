# Alloy Classifier Handoff - Start Here

## Purpose
This folder is prepared for handoff to the next agent for staged execution of Alloy-based BE image classification.

Current priority is Phase 1 experimentation and tailoring of Rob and Doruk ideas to the specific BE classification problem.

ScriptHost-compatible production packaging is intentionally deferred to a later phase once classification output quality is acceptable.

## Read Order
1. `../Image_classification_needs.txt`
2. `learnings/Alloy_Image_Classification_ScriptHost_Handoff.md`
3. `learnings/Alloy_Workflow_Implementation_Guide.md`
4. `learnings/Alloy_RAG_WorkOrder_Script_Framework.md`
5. `DEFECT_CLASSIFICATION_NEXT_STEPS_HANDOFF.md`
6. `RUNTIME_SCAFFOLD.md`
7. `PHASE1_RUNBOOK.md`
8. `PROJECT_STRUCTURE.md`
9. `WHEELHOUSE_BLOCKER_20260726.md`
10. `PHASE1_ACCEPTANCE_CHECKLIST.md`
11. `RAW_IMAGE_REDOWNLOAD_PLAN.md`

## Inline Context Bridge

Use the inline context system below when Alloy work needs current pipeline behavior, contracts, or ownership routing.

1. Inline doc index:
	- [../../../docs/inline_pipeline/README.md](../../../docs/inline_pipeline/README.md)
2. Tier 2 inline architecture/operations summary:
	- [../../../INLINE_PIPELINE_DESIGN.md](../../../INLINE_PIPELINE_DESIGN.md)
3. Most relevant feature docs for Alloy pairing and metadata joins:
	- [../../../docs/inline_pipeline/coordinates_and_images.md](../../../docs/inline_pipeline/coordinates_and_images.md)
	- [../../../docs/inline_pipeline/operations_and_hardening.md](../../../docs/inline_pipeline/operations_and_hardening.md)

## Execution Phases
1. **Phase 1 (Now): Rob/Doruk idea operationalization + class-tailoring**
	- modernize notebook/script to current Alloy API surface
	- run targeted experiments on BE defect images
	- refine prompt + output schema for fine-bin discrimination
	- define confidence and uncertainty handling for analyst review
2. **Phase 2 (Next): pipeline-side integration planning**
	- map outputs to existing BE manifests/artifacts
	- define low-risk insertion point in current orchestrated flow
3. **Phase 3 (Later): ScriptHost runtime packaging/deployment**
	- wheelhouse/launcher/bootstrap hardening
	- scheduling and operationalization

## Key Constraints
- ScriptHost drones run a fixed Python runtime.
- UNC path execution is available.
- Use wheelhouse-first dependency strategy for deterministic behavior.
- Keep upstream `alloy-sandbox` repo clean; do not reintroduce old wheel hacks there.
- Do not assume legacy Alloy import paths; discover imports from the currently installed Alloy environment before patching examples.

Execution policy:

- Continue Phase 1 development/testing immediately with the currently working Alloy API environment.
- Treat wheelhouse gaps as a ScriptHost-parity gate, not a Phase 1 experimentation gate.

## Phase 1 Required Deliverables
1. Import compatibility matrix
	- old usage in Rob/Doruk examples
	- verified current Alloy import/call replacements
	- source references from local Alloy codebase/examples
2. Tailored prompt/schema package for BE defect classification
	- strict JSON output schema
	- fields to support downstream joining and analyst review
	- ambiguity and confidence policy
3. Experiment runbook
	- single-image smoke flow
	- small-batch comparison flow
	- rubric for deciding if class discrimination is useful

## Phase 1 Candidate Output Fields
- run_id
- timestamp_utc
- image_key (deterministic)
- image_path
- model_name
- prompt_version
- primary_class
- secondary_class (optional)
- morphology
- location_relative
- size_relative
- confidence
- review_required (boolean)
- rationale
- raw_response_excerpt
- status
- error_message

## Expected Next Actions (for the next agent)
1. API compatibility audit for Alloy vision imports/calls.
2. Modernize Rob and Doruk examples to canonical current APIs.
3. Implement Phase 1 prompt/schema tailoring for BE fine-bin use.
4. Validate with smoke + small-batch tests and summarize findings.
5. Propose Phase 2 integration point into existing BE pipeline.

## Deferred (Do Not Execute Yet Unless Requested)
- ScriptHost launcher/bootstrap implementation.
- wheelhouse build and runtime packaging.
- production scheduling handoff.

## Handoff Path
`\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class`

## Shared Runtime Root (UNC)
`\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Shared_Docs\Alloy_Apps\_shared_runtime`
