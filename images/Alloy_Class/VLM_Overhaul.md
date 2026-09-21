VLM Overhaul.  Before making any changes, can you provide analysis of what I'm asking here, and provide high level overview of gaps, and a plan that could include an organized working folder to contain this work within the Alloy Class folder.  (Part could involve migrating the RAW_IMAGES and its pipeline, to the UNC share -- current RAW_IMAGES cache is between 1 and 2 GB which is doable.)

Vlm Prompt Modification.  Can you review these -- I want to modify the prompt a bit, and start with a new registry.  Part of this effort will also involve creating adhoc html to review the vlm descriptions.  Another part will be to enrich these outputs with production coordinates and metrics csv's.  Many key pieces are in place.  But the grand vision is to enrich coordinates csv, and establish connections with some of the attribute labels (and maybe, their combinations).  Key is to finalize the prompt, and wire together the vlm, the wds, the bost, (and the ground truth) towards having fully integrated coordinates and metrics datasets.  The coordinates can be directly enriched with these, but the metrics datasets will require more review of the coordinates-level vlm enrichment to identify if any sort of aggregation patterns can be applied (like was already done, for ground-truth labels.  'circles' and 'defects greater than 1' or metrics for 'small' Small Particles and 'large' Small particles, etc. etc.).  So there is some open-endedness of what will be decided upon but a lot of pieces are in place. 

VLM registry & html reporting: 
agents_history/sessions/2026-09-09_004_generic-description-chunked-submission-bug-fixes-and-verification-checkpoint.md 
agents_history\sessions\2026-09-09_003_alloy-generic-description-chunked-submission-follow-through-checkpoint.md
agents_history/sessions/2026-09-09_002_generic-description-registry-bootstrap-and-tranche-fix.md

Enrichment of production coordinates, and metrics csv's with WDS and BOST data:
agents_history\sessions\2026-09-14_004_bost-accumulating-csv-lot7-initialization-checkpoint.md
agents_history\sessions\2026-09-14_003_wds-apex-entity-incremental-accumulator-checkpoint.md
agents_history\sessions\2026-09-09_004_generic-description-chunked-submission-bug-fixes-and-verification-checkpoint.md

