# Alloy RAG Work Order Framework (Script-First)

## Purpose
This guide documents the approach used for the vacuum pump use case and generalizes it into a reusable, standalone-script framework for future work order mining tasks.

## BE Inline Context Alignment

When adapting this framework to BE defect-image or manifest-linked workflows, use:

1. [../../../../docs/inline_pipeline/README.md](../../../../docs/inline_pipeline/README.md)
2. [../../../../docs/inline_pipeline/operations_and_hardening.md](../../../../docs/inline_pipeline/operations_and_hardening.md)

## What We Proved in the Vacuum Pump Use Case
- Source data: AME work order CSV (roughly 90 days, 1,493 rows).
- We converted rows to structured markdown-like records and ingested into Alloy RAG (ChromaDB local vector store).
- We used multiple focused retrieval prompts, not one broad prompt.
- We used `context_only=True` to reliably retrieve evidence blocks, then used `chat()` for synthesis.
- We validated retrieval findings against direct text scanning, then exported/retained evidence.

Primary value from Alloy in this workflow:
- Better synthesis and structured explanation from retrieved evidence.
- Faster analyst interpretation once relevant records are gathered.

## Recommended Generic Workflow
1. Normalize source records.
- Keep key fields: WO ID, date, tool, description, comments, optional work-center fields.
- Build one canonical text blob per work order.

2. Ingest once, query many.
- Ingest the normalized corpus into Alloy RAG collection.
- Reuse the collection for multiple prompt sets (pump, gaslines, teflon shim, etc.).

3. Run prompt bundles.
- For each use case, run 4-8 semantically different prompts to improve recall.
- Retrieve top-k context per prompt (for example, 30-60).

4. Consolidate and de-duplicate evidence.
- Merge retrieved text blocks.
- De-duplicate by WO ID (preferred) or canonical snippet hash.

5. Synthesize with Alloy LLM.
- Feed consolidated evidence to `alloy.core.llm.chat()`.
- Ask for structured output: findings, counts, confidence, and cited examples.

6. Export deterministic artifacts.
- Row-level evidence CSV.
- Final summary markdown or JSON.

## Script-First Project Layout
Use this minimal structure for non-notebook execution:

```text
project_root/
  data/
    work_orders.csv
  outputs/
    ingest_corpus.md
    evidence_<use_case>.csv
    summary_<use_case>.md
  scripts/
    01_prepare_corpus.py
    02_ingest_rag.py
    03_query_bundle.py
    04_summarize_findings.py
    run_use_case.py
```

## Execution Pattern
Run once per dataset:
1. `python scripts/01_prepare_corpus.py`
2. `python scripts/02_ingest_rag.py`

Run per use case:
3. `python scripts/03_query_bundle.py --use-case gasline_replacement`
4. `python scripts/04_summarize_findings.py --use-case gasline_replacement`

Orchestrated run:
5. `python scripts/run_use_case.py --use-case teflon_shim --top-k 50`

## Generic Prompting Framework
Define each use case as:
- A short objective
- A list of retrieval prompts (query variants)
- Inclusion terms
- Exclusion terms
- Optional date/tool filters

Template:

```text
Objective:
Find instances where <component/action> occurred in work orders.

Retrieval Prompts:
- <variant 1>
- <variant 2>
- <variant 3>
- ...

Inclusion Hints:
- synonyms, abbreviations, misspellings

Exclusion Hints:
- nearby terms that create false positives

Output Schema:
- wo_id
- date
- tool
- matched_snippet
- why_matched
- confidence
```

## Prompt Bundles for Your Next Two Use Cases

### Use Case A: Gasline Replacement
Objective:
Find instances from work order history when gaslines were replaced.

Suggested retrieval prompts:
- "Find work orders where gas line was replaced"
- "Find records mentioning replaced gasline or gas line changeout"
- "Identify maintenance events: gas line leak then replacement"
- "Find WOs with gas manifold or gas delivery line replaced"
- "Find PM/repair notes containing swap, replaced, renewed gas line"

Inclusion hints:
- gasline, gas line, gas delivery line, manifold line, line changeout
- replaced, replacement, swapped, renewed, changed out

Exclusion hints:
- pressure check only, purge only, no replacement performed

### Use Case B: Teflon Shim Replacement or Installation
Objective:
Find instances when teflon shim was replaced or installed.

Suggested retrieval prompts:
- "Find work orders where teflon shim was replaced"
- "Find records where teflon shim installed or installation completed"
- "Identify WOs mentioning shim replacement in chamber maintenance"
- "Find notes with PTFE shim install/replace language"
- "Find events: shim wear detected then teflon shim change"

Inclusion hints:
- teflon shim, PTFE shim, shim
- installed, install, replaced, replacement, reinstalled

Exclusion hints:
- shim inspection only, shim alignment check without install/replace

## Implementation Notes for Alloy APIs
- Retrieval: `alloy.rag.query(question=..., db_name=..., mode="vector-only", context_only=True)`
- Synthesis: `alloy.core.llm.chat(prompt)`
- Optional direct answer path: `context_only=False` if stability/quality is acceptable for your collection state.

Recommended defaults:
- `top_k`: 30-60 per prompt variant
- prompt variants per use case: 5
- output: keep both raw context and parsed evidence rows

## Quality Controls
1. Recall check.
- Run a quick keyword/regex baseline and compare against retrieved WO IDs.

2. Precision check.
- Manually inspect top 20 matched records for each use case.

3. Evidence traceability.
- Every summarized finding should map to one or more source snippets and WO IDs.

4. False positive handling.
- Track common false-positive patterns and append to exclusion hints.

## Minimal CLI Config Pattern
Use a JSON or YAML config per use case so no code edits are needed.

Example keys:
- `use_case_name`
- `db_name`
- `top_k`
- `prompts[]`
- `include_terms[]`
- `exclude_terms[]`
- `output_prefix`

This lets you run new use cases by adding config only.

## Next Step
After this markdown, the practical next build is a standalone runner that accepts:
- `--use-case <name>`
- `--config <file>`
- `--top-k <int>`
and emits both evidence CSV and summary markdown automatically.