# Alloy Workflow Implementation Guide

## Purpose
This document captures what we learned while implementing two real Alloy workflows, and turns it into a repeatable method for building new, production-oriented workflows quickly.

## BE Inline Context Alignment

For BE defect-classification use cases, pair this generic workflow guidance with the inline context docs:

1. [../../../../docs/inline_pipeline/README.md](../../../../docs/inline_pipeline/README.md)
2. [../../../../docs/inline_pipeline/runtime_contract.md](../../../../docs/inline_pipeline/runtime_contract.md)
3. [../../../../docs/inline_pipeline/coordinates_and_images.md](../../../../docs/inline_pipeline/coordinates_and_images.md)

## What Worked (Key Learnings)
1. Start with narrow, testable slices.
- Build a minimal end-to-end path first (load data -> call Alloy -> inspect output).
- Expand only after first successful results.

2. Use Alloy for synthesis and reasoning, not only retrieval.
- For structured datasets, direct filtering/regex can outperform retrieval on raw recall.
- Alloy adds strongest value in summarization, categorization, and narrative synthesis.

3. Separate retrieval from classification goals.
- `rag.query()` is best for evidence retrieval and context assembly.
- Taxonomy/Pareto generation is better served by embeddings + clustering or direct batched LLM labeling.

4. Keep workflows resilient to imperfect infra.
- Local vector tooling may have environment-specific quirks; include fallback modes (`context_only=True`) and small repair/validation cells.

5. Always export enriched outputs.
- Final artifacts should preserve original source fields and append Alloy-generated columns for downstream analytics.

## Alloy Implementation Patterns (Reusable)

### Pattern A: Retrieval + Synthesis (Evidence-first)
Use when question answering must cite source-like context.

- Ingest source corpus (`alloy.rag.ingest`).
- Retrieve with focused prompts (`alloy.rag.query`, context mode if needed).
- Synthesize and explain with `alloy.core.llm.chat`.
- Export: question, retrieved snippets/context, final answer, confidence notes.

### Pattern B: Embeddings + Clustering + LLM Naming (Discovery-first)
Use when categories are unknown.

- Embed each item (`alloy.core.llm.embeddings`).
- Cluster (e.g., k-means, 6-10 groups).
- Ask LLM to name/describe each cluster from representative samples.
- Export: row-level cluster, cluster label, frequency/Pareto stats.

### Pattern C: Batched LLM Classification (Policy-first)
Use when human-readable labels matter more than latent geometry.

- Batch records (e.g., 30-50 rows).
- Maintain evolving category list with cap (e.g., max 10).
- Force structured JSON output from chat.
- Aggregate counts + LLM descriptions for each category.
- Export row-level label and category metadata.

## Streamlined Workflow Template (Recommended Default)
1. Define objective + output schema first.
- Example schema: `doc_id`, `parameter_name`, `current_value`, `proposed_value`, `unit`, `change_rationale`, `source_excerpt`, `page`, `confidence`.

2. Build a 3-phase notebook.
- Phase 1: Data extraction and normalization.
- Phase 2: Alloy analysis (retrieve/classify/extract).
- Phase 3: QA + export.

3. Enforce deterministic interfaces.
- Require JSON outputs with strict keys.
- Validate every batch; retry malformed responses automatically.

4. Add observability from day one.
- Track counts, skipped rows, parse failures, and confidence thresholds.

5. Produce two outputs every run.
- Detailed row-level CSV/JSON.
- Executive summary table (top findings, Pareto, exceptions).

## Next Task Blueprint: Multi-Page Word Document Parameter Extraction
Goal: Identify fine-grained, adjustable process parameters proposed by a document (change request / process update), with traceability to source text.

### Recommended Architecture
1. Ingest and segment document.
- Extract text page-by-page (or section-by-section).
- Create chunks with overlap (for example, 600-1000 words, 100-word overlap).
- Keep metadata: `page`, `section_heading`, `chunk_id`.

2. Candidate retrieval.
- Use embedding search over chunks for terms like "setpoint", "tolerance", "recipe", "adjust", "target", "window", "increase", "decrease".
- Optionally combine with keyword pre-filter for speed.

3. Structured extraction with Alloy chat.
- Prompt for strict JSON array entries:
  - `parameter_name`
  - `proposed_adjustment`
  - `direction` (increase/decrease/retune)
  - `current_or_baseline`
  - `proposed_target`
  - `unit`
  - `applicability_scope`
  - `reason_or_expected_impact`
  - `source_excerpt`
  - `page`
  - `confidence`

4. Consolidation.
- Merge duplicate parameters across chunks/pages.
- Resolve conflicts by confidence + explicitness.
- Keep full provenance (all supporting excerpts).

5. Verification pass.
- Second-pass Alloy check: "Given extracted table + source excerpts, flag hallucinations, missing units, or unsupported claims."
- Mark items requiring human review.

6. Export.
- `*_parameter_changes_detailed.csv` (one row per extracted claim).
- `*_parameter_changes_canonical.csv` (deduplicated parameter-level view).
- Optional markdown summary for review.

## Prompting Standards That Improved Results
1. Give domain context in first sentence (fab module/process context).
2. Specify strict output format (JSON only, fixed keys).
3. Add negative constraints ("do not infer values not explicitly stated").
4. Request source excerpt + page for every extracted claim.
5. Include confidence scoring rubric (high/medium/low or 0-1).

## Quality Gates Before Sign-Off
1. Schema validity: 100% parseable JSON rows.
2. Traceability: every extracted parameter has source excerpt + page.
3. Precision audit: sample 20 rows manually, target high precision.
4. Completeness audit: verify known critical parameters appear.
5. Export integrity: row counts and key columns validated.

## Practical Runbook (This Workspace)
1. Set environment/proxy as needed, then run workflow notebook end-to-end once.
2. Cache intermediate artifacts (clean text, chunks, embeddings) to avoid full re-runs.
3. Re-run only extraction/consolidation cells when tuning prompts.
4. Version outputs with timestamps for comparison.

## Suggested Starter Deliverable for the Word-Doc Use Case
Create a notebook with these sections:
- Load DOCX/PDF text + metadata
- Chunking and indexing
- Candidate retrieval queries
- Structured parameter extraction (batched)
- Deduplication + conflict resolution
- QA verification pass
- Final exports (detailed + canonical)

This structure will let you iterate quickly while preserving rigor, provenance, and reproducibility.