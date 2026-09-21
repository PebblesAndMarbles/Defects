Overall Assessment
The plan is well-structured and the phase sequencing is correct. The key insight — instrumentation before hypothesis testing — is exactly right. You cannot confirm or reject the max-token theory with fabricated usage estimates, and running Phase 1 before Phase 0 would produce unreliable conclusions. The dependency chain is sound.
Specific Observations
Phase 0 — Strong, One Addition
The instrumentation scope is correct. One addition worth considering: log the raw byte length of the image payload being sent on each multi-image call. If Alloy is silently resizing or recompressing images before submission, this would surface as a payload size discrepancy between what the pipeline constructs and what the API actually receives. Costs nothing to add at instrumentation time and directly answers the image quality question without needing the Alloy team to respond first.
Phase 1 — Decision Gate is Clean
The 400 vs 1800 token comparison on 5 FN cases is the right minimal test. One note: run both token budgets on the same call structure — bare image call, no Stage A context, no JSON contract — to isolate the token variable cleanly. If you run 1800 tokens with the full production prompt, you're testing two variables simultaneously.
Phase 2 — Scope is Appropriately Contained
Throwaway script, not a production config edit. This is the right call. The describe-then-classify structure is a meaningful architectural change and needs standalone validation before it touches versioned configs.
Phase 3 — Control Case Coverage
BMK_0008 as the single true-particle control is thin. If you have any additional particle cases available outside the benchmark set, even 2-3, adding them to the Phase 3 validation would strengthen confidence that the free-observation call isn't inflating BEEP calls on genuine particles. The describe-then-classify structure's main FP risk is that Call 1 free observation on a particle near a trench wall produces language that Call 2 then interprets as boundary conformance evidence.
Phase 4 — Benchmark Comparison Framing
When comparing V13 to V12 baseline, the primary metric should be tune-set FN rate, not overall agreement. Overall agreement at n=15 is noisy. The specific question is: do the 4 tune-set FNs (BMK_0050, BMK_0029, BMK_0005, BMK_0009) flip to correct? Secondary: does BMK_0001 (eval FN) also flip? Tertiary: does evidence agreement recover from V12's regression on BMK_0018?
Phase 5 — Alloy Owner Report
The image resize/compression question should be framed as a specific ask, not a general question. Recommend asking owners for:
Whether any image transformation occurs between pipeline submission and API call
Whether finish_reason is available in the response object and if so where
The persistent empty response pattern on BMK_0050/p2 specifically — 4 consecutive empty responses on identical inputs suggests something deterministic, not transient
One Strategic Note
The plan correctly keeps the two tracks independent, but there is a sequencing opportunity worth flagging: if Phase 1 confirms that the empty response issue is purely a max-token problem at 400 tokens, then the probe data that showed the model correctly identifying FN signals was generated under token-constrained conditions. The free-observation Call 1 responses may have been truncated mid-sentence — which means the positive probe results are actually conservative estimates of what the model can perceive. This strengthens the case for the describe-then-classify architecture rather than weakening it, but it is worth noting in the Phase 5 report.
Summary Verdict
Ship the plan as written with three additions:
Log raw image payload byte length in Phase 0 instrumentation
Isolate token budget as the sole variable in Phase 1 by using bare calls at both token levels
Add 2-3 additional particle cases to Phase 3 control set if available
The sequencing is correct, the scope is appropriately bounded, and the decision gates are clean. This is a well-designed diagnostic and validation plan.