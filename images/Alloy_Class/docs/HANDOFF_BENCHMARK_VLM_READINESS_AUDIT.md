# Handoff: Structured Benchmark VLM Readiness Audit

Date: 2026-08-09
Owner intent: transition from infrastructure build-out into prompt engineering and measured benchmark runs.

## Purpose

Direct a status-oriented agent to verify that benchmark assets, schema contracts, adjudication guidance, and run infrastructure are ready for structured VLM prompt experimentation.

This is a readiness audit handoff, not a request to redesign workflows.

## Current Transition Point

Completed:
- Benchmark labeling is complete on the active 14-day candidate set.
- Comparator and occlusion adjudication guidance is updated and aligned across docs.
- Notes-light adjudication policy is in place (`notes_needed` gate).
- Active benchmark CSV has been published to UNC artifacts path.

Now starting:
- Prompt engineering iterations and measured evaluation against adjudicated benchmark labels.

## Canonical Inputs To Audit

Primary artifacts:
- `images/Alloy_Class/artifacts/benchmark_candidates_14day.csv`
- `images/Alloy_Class/artifacts/benchmark_candidates_14day_summary.json`
- `images/Alloy_Class/artifacts/benchmark_candidates_14day_split_preview.csv`
- `images/Alloy_Class/artifacts/benchmark_slice_v1_template.csv`

Primary guidance docs:
- `images/Alloy_Class/docs/BENCHMARK_SCHEMA_AND_LABELING_WORKFLOW.md`
- `images/Alloy_Class/docs/ADJUDICATION_WORKSHEET_ONE_PAGER.md`
- `images/Alloy_Class/docs/BENCHMARK_CANDIDATE_TOOL_SCOPE.md`
- `images/Alloy_Class/docs/HANDOFF_PROMPT_ITERATION_1PAIR_RUNTIME.md`

Session logs to review for context and assumptions:
- `agents_history/sessions/2026-08-09_002_alloy-benchmark-adjudication-schema-and-unc-publish.md`
- `agents_history/sessions/2026-08-09_001_substrate-prompt-tier-test-20-image-raw-run.md`
- Relevant 2026-08-08 session logs under `agents_history/sessions/`

## Audit Questions (Must Answer)

1. Schema contract readiness
- Are benchmark CSV columns, template columns, and doc-defined fields aligned enough for reproducible prompt scoring?
- Identify any must-fix drift vs acceptable optional/derived drift.

2. Label normalization readiness
- Are adjudication enum values consistently encoded (especially blocked-etch evidence and confidence)?
- Identify remaining shorthand or anomalies that would break metric grouping.

3. Split and freeze readiness
- Is current split strategy deterministic and traceable?
- Is there a clear freeze protocol for tune/eval snapshots before prompt iteration?

4. Prompt-run infrastructure readiness
- Are scripts and report paths in place for rapid iteration from VLM call to review artifact?
- Confirm that runtime optimizations and pair-selection controls are ready to avoid avoidable cost/time overhead.

5. Measurement readiness
- Are metric definitions clear for false negatives on possible_beep, false positives on non-beep, disagreement rate, and review_required calibration?
- Are there any unresolved ambiguities that would make metric comparisons unreliable?

## Required Deliverables From Status Agent

1. Readiness verdict
- `GO` or `NO-GO` for structured benchmark VLM prompt iteration.

2. Findings table (severity-ordered)
- critical blockers
- high-priority fixes
- medium polish items

3. Explicit contract snapshot
- final column set to use for scoring
- which fields are required vs optional/derived
- enum/value mappings used in scoring logic

4. Immediate action plan
- ordered 1-2 day checklist to reach (or confirm) GO state
- include exact file targets for each fix

5. Reproducibility package recommendation
- name/version for frozen benchmark CSV
- required companion artifacts (summary, split preview, config hash/prompt version log)

## Boundaries

Do:
- validate readiness and consistency
- propose smallest viable fixes to remove blockers
- preserve current adjudication intent and comparator/occlusion semantics

Do not:
- relabel benchmark rows unless a narrowly scoped normalization is required
- redesign taxonomy beyond what is needed for prompt scoring reliability
- introduce new workflow branches unless a blocker requires it

## Suggested Prompt To The Status Agent

Use this exact prompt:

"Perform a structured readiness audit for benchmark-driven Alloy VLM prompt iteration. Read the benchmark artifacts, schema/workflow docs, and recent session logs listed in `images/Alloy_Class/docs/HANDOFF_BENCHMARK_VLM_READINESS_AUDIT.md`. Return a severity-ordered findings list and a strict GO/NO-GO verdict. If NO-GO, provide the minimum fix set with exact file-level actions to reach GO within 1-2 days. Preserve current adjudication semantics, especially comparator-visible partial logic and occlusion separation."

## Success Criteria

This handoff succeeds when the status agent returns:
- a defensible GO/NO-GO verdict
- a concrete, minimal unblock plan
- a stable contract suitable for repeatable prompt-versus-benchmark measurement.