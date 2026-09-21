Project Passdown — BEOL SEM Defect Classification Pipeline
Session Date: 2026-08-27 | Handoff to Next Agent Session
Current State in One Sentence
V13 describe-then-classify architecture eliminated all FNs on the 15-pair benchmark (FN rate 0.357 → 0.000) but introduced a severe FP problem on the 25-case particle-only validation set (FP rate 0.84), and the root cause is now diagnosed but not yet fixed.
Where We Are in the Plan
Phase 0 — Instrumentation ✅ Complete Phase 1 — Max-token test ✅ Complete (confirmed, fixed) Phase 2 — Describe-then-classify ✅ Built Phase 3 — Validation (5 FN + controls) ✅ Complete (11/12, GT error caught/corrected) Phase 4 — Full 15-pair benchmark ✅ Complete (0.9333 agreement, 0.000 FN) Phase 5 — Reporting 🔴 Blocked pending FP fix NEW: Phase 6 — FP diagnosis ✅ Root cause identified NEW: Phase 7 — FP fix 🔴 Not yet implemented
The FP Problem — Diagnosed
What Happened
25-case particle-only validation run produced 0.84 FP rate (21/25 false positives). The 15-pair benchmark had only 1 particle GT case (BMK_0008) so this was invisible until the larger particle set was run.
Root Cause — Two Mechanisms Operating Simultaneously
Mechanism 1 — Call 2 ignores Call 1's conclusion. Call 1 correctly observes "no blocked etch evidence" or "clean particle contact." Call 2 classifies as possible_beep anyway. Call 1's observation text is not anchoring Call 2's classification — Call 2 re-examines the image independently.
Mechanism 2 — Call 2 confabulates evidence. Call 2's V11 evidence framework creates strong pressure to find and report geometric signals. On clear particle images, Call 2 generates factually incorrect pathway confirmations — describing tonal fills, asymmetric terminations, and wall continuity that do not exist in the image. Confirmed on BMK_0036: a clean triangular particle with no blocking evidence, where Call 2 reported ISL yes, BC yes, strong evidence.
Key evidence:
BMK_0036 and BMK_0003 Call 1 texts are nearly identical and both explicitly state "no blocked etch evidence" — yet both get classified possible_beep by Call 2
BMK_0036 image is an unambiguous clean particle — Call 2's rationale is factually wrong
Correct particle calls (BMK_0030, BMK_0024, BMK_0006) all had Call 1 observations with strong explicit negative language — Call 2 correctly inherited those conclusions
Case Taxonomy for the 21 FPs
Three categories exist but full distribution not yet measured:
Category A — Clear confabulation: Call 1 says no evidence, Call 2 invents it. Fix: hard gate. Examples: BMK_0036, BMK_0003
Category B — Genuine ambiguity: Call 1 hedges, geometry is at particle/BEEP boundary. Fix: uncertain, may be irreducible. Example: BMK_0026 (particle bridging inter-trench land, right trench appears shortened)
Category C — Call 1 positive: Call 1 describes real signals, Call 2 correctly responds. These are the hardest GT labeling questions
Critical unknown: distribution of A vs B vs C across all 21 FPs. This determines how much the proposed fix is worth before implementing it.
Proposed Fix — Two Components
Component 1 — Call 1 Explicit Verdict
Add to end of Call 1 prompt:
End your observation with exactly one of these three verdict lines on its own line: VERDICT: No blocking evidence observed. VERDICT: Possible blocking evidence — [one phrase naming the specific signal]. VERDICT: Ambiguous — blocking evidence cannot be confirmed or excluded.
Component 2 — Call 2 Hard Gate on Call 1 Verdict
Add to beginning of Call 2 prompt:
PRIOR OBSERVATION VERDICT: [insert verdict line from Call 1] If the verdict is "No blocking evidence observed," output the particle JSON template below and stop. Do not run pathway assessment. [particle template] If the verdict is "Possible blocking evidence" or "Ambiguous," proceed with the full pathway assessment.
Why This Should Work
Category A cases: Call 1 verdict = "No blocking evidence" → hard gate → particle, no confabulation possible
Category B cases: Call 1 verdict = "Ambiguous" → pathway runs → may still FP but these are genuinely hard
Original 5 FN cases: Call 1 verdict = "Possible blocking evidence" → pathway runs → possible_beep preserved
Risk
The fix preserves FN performance only if Call 1 correctly produces "Possible blocking evidence" verdicts for the original FN cases. This must be verified on the 5 FN cases before running the full benchmark again.
Immediate Next Steps — In Order
Step 1 — Categorize the 21 FPs (30 minutes, no code)
Pull Call 1 observation text for all 21 FP cases from the particle-only run raw artifacts. Categorize each as A, B, or C per the taxonomy above. If Category A is 15+, the fix is high ROI. If Category A is fewer than 10, a different approach may be needed for Category B cases.
Artifacts needed:
Raw run output from benchmark_particle25_v13_describe_then_classify_rerun2/
Call 1 observation text per case (should be in per-row raw JSON)
Step 2 — Verify Fix on FN Cases Before Implementing
Before touching any code, manually check: would the 5 original FN cases produce "Possible blocking evidence" verdicts from Call 1 under the new prompt? The Call 1 observation texts from Phase 3 are already captured in outputs/probes/phase3_describe_then_classify_20260826/. Review those texts and confirm they would map to "Possible blocking evidence" not "Ambiguous" or "No blocking evidence."
If any FN case would produce "No blocking evidence" or "Ambiguous" → the hard gate would suppress it → FN reintroduced. Do not proceed until this is confirmed safe.
Step 3 — Implement the Two-Component Fix
Modify tools/probe_describe_then_classify.py (throwaway script, not production config) to add the verdict instruction to Call 1 and the hard gate to Call 2. Keep Call 2's evidence framework as V11-verbatim — do not change the pathway instructions.
Step 4 — Validate on Mixed Set
Run the fixed architecture on:
5 original FN cases → must still call possible_beep
BMK_0008 → accept either call (known edge case)
4-5 Category A FP cases → must now call particle
2-3 Category B FP cases → document outcome, accept if still FP
BMK_0030, BMK_0024, BMK_0006 → must stay particle
Pass condition: all 5 FN cases correct AND Category A FP rate drops substantially.
Step 5 — Re-run Full Particle-25 Set
If Step 4 passes, run the fixed architecture on the full 25-case particle set. Target FP rate below 0.20. If achieved, proceed to re-run the 15-pair benchmark to confirm FN rate stays at 0.000.
Step 6 — Combined Benchmark
Run both the 15-pair BEEP/particle benchmark and the 25-case particle set together. Report:
Primary: FN rate on 15-pair set (must stay 0.000)
Secondary: FP rate on 25-case particle set (target <0.20)
Tertiary: evidence agreement on 15-pair set (target ≥0.800)
Key Files and Artifacts
Configs
config/stage_ab_prompt_tests_substrate_tier1_v11.json — Call 2 evidence framework source (use V11, not V12)
config/stage_ab_prompt_tests_substrate_tier1_v12.json — previous baseline, do not regress to this
config/stage_ab_prompt_tests_substrate_tier1_v13.json — current production candidate
Scripts
tools/probe_describe_then_classify.py — implement fix here first
reporting/run_stage_ab_prompt_tests.py — production runner, do not touch until fix validated
tools/run_benchmark_vlm.py — benchmark runner
tools/score_benchmark_run.py — scorer (known minor bug: flags review_required=false as missing — pre-existing, do not fix in this track)
Benchmark Artifacts
outputs/raw_runs/offset_surface_lines_15_v13_compare/ — Phase 4 full benchmark results
benchmark_particle25_v13_describe_then_classify_rerun2/scoring/benchmark_scored_rows.csv — 25-case particle FP run
outputs/probes/phase3_describe_then_classify_20260826/ — Phase 3 validation, Call 1 texts for original 5 FN cases
outputs/probes/fn_feature_probe_consolidated.jsonl — original FN perception probe results
Documentation
docs/v12_post_mortem.md — full addendum chain (addenda 1-4), append Phase 6/7 results here
docs/PROMPT_ITERATION_REGISTRY.md and artifacts/prompt_iteration_registry.csv — version tracking
docs/iGPT_VLM_Chat_Diagnostics.md — original suppression hypothesis document
docs/iGPT_v13_plan_feedback.md and iGPT_v13_plan_feedback2.md — external review notes
Ground Truth
artifacts/benchmark_candidates_14day.csv — always filter on adjudicated_coarse_class + adjudication_status == complete, never on factory_class_label or source_pool
Constraints to Preserve
Constraint	Reason
FN rate must stay at 0.000 on 15-pair set	Hard requirement — any fix that reintroduces FNs is worse than V12
Call 2 evidence framework stays V11-verbatim	V12 additions caused suppression; V11 is the validated base
Stage A prompt unchanged	Stable, no regression risk
Fix validated on throwaway script before production config	Established convention throughout this project
GT source is always adjudicated_coarse_class	Factory labels are pre-adjudication sampling labels, not ground truth
Open Questions for Next Session
What is the Category A/B/C distribution across the 21 FPs? This is the most important unknown. Answer it before writing any code.
Does BMK_0026 remain a FP after the fix? It is a genuinely ambiguous case — particle bridging inter-trench land with apparent trench shortening on one side. May be irreducible. DF image not yet reviewed.
What is the right target FP rate? 0.84 is clearly unacceptable. 0.000 may be unachievable without reintroducing FNs. The acceptable operating point — trading some FP rate for zero FN rate — is a domain judgment call for the user, not a technical decision.
Should BMK_0008 be relabeled? GT is particle with weak/ambiguous evidence. The describe-then-classify architecture consistently calls it possible_beep. At some point the question is whether the GT label or the model call is more accurate for this edge case.
Context for Next Agent
This project has been running across multiple sessions. The full prompt engineering history, benchmark results, and diagnostic chain are documented in docs/v12_post_mortem.md addenda 1-4 and docs/PROMPT_ITERATION_REGISTRY.md. The most important context for the next session is:
The describe-then-classify architecture is correct and should not be abandoned
The FP problem is a calibration problem, not an architecture problem
The fix is targeted and specific — two prompt additions, no structural changes
The single most important action is categorizing the 21 FPs before implementing anything
Do not revert to V12. Do not modify the production runner until the fix is validated on the throwaway script. Do not run the full benchmark until the mixed validation set passes.