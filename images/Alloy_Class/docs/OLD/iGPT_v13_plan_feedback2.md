Plan Review — Final Assessment
Overall Verdict
This is a production-quality engineering plan. The incorporation of all external review feedback is complete and correctly placed. The dependency chain is sound, the decision gates are crisp, and the scope boundaries are well-enforced. I have no structural objections.
Specific Observations by Phase
Phase 0 — Instrumentation
Complete and correctly scoped. The payload byte-length logging addition is well-placed. One implementation note worth flagging to whoever writes the code: when logging base64 payload size, log both the pre-encoding file size (bytes on disk) and the post-encoding base64 string length. The ratio should be consistently ~1.37x for unmodified images. A ratio significantly different from 1.37x would indicate transformation is occurring inside the Alloy layer before encoding, which is a different failure mode than post-encoding compression.
Phase 1 — Max-Token Test
The bare-call isolation requirement is correctly stated and critical. The decision gate is clean. One addition: record the actual response text length (character count) alongside the empty/truncated flag for each call at both token budgets. If truncation is the cause, the 400-token responses should cluster around a consistent character ceiling while 1800-token responses should vary freely. This pattern would be visible in the raw data even if finish_reason is unavailable.
Phase 2 — Describe-Then-Classify Architecture
The Call 1 / Call 2 structure is correctly specified. The instruction to abbreviate the evidence framework in Call 2 is important and easy to underweight — the abbreviated Call 2 prompt should be drafted carefully. Specifically: retain the three evidence check definitions and the JSON contract, but drop all the variant blocks added in V12. The V12 variants were written to fix visual detection failures that the two-call structure addresses at the architectural level. Keeping them in Call 2 reintroduces instruction-volume anchoring into the classification step.
Phase 3 — Validation
The expanded control set requirement is correctly incorporated. When selecting the 2-3 additional particle controls from benchmark_candidates_14day.csv, prioritize cases where the particle is near or touching a trench wall rather than isolated on open field. The FP risk of the describe-then-classify architecture is specifically at the wall-adjacent particle case — a particle sitting on open field will not stress-test Call 2's boundary conformance assessment. BMK_0008 already has this property (particle near comparator), so the additional controls should match that profile.
Phase 4 — Scale-Up
The metric priority order is correct and should be enforced strictly when writing the post-mortem. Overall agreement at n=15 is a noisy headline number that can move for the wrong reasons. The primary question is whether the 4 specific tune-set FNs flip, full stop.
Phase 5 — Reporting
The three specific questions to Alloy owners are well-framed. The strategic note about token-constrained probe results strengthening rather than weakening the describe-then-classify case is an important framing point and should appear early in the report, not buried in a footnote.
One Risk Not Currently Called Out
Call 2 prompt design is the highest-risk single artifact in this plan.
If Call 2's abbreviated evidence framework is too loose, it will over-call BEEP on the particle controls. If it is too tight, it reintroduces the suppression problem. The V11 prompt — before the V12 variant additions — is the natural starting point for Call 2, since V11 had zero FP rate and the V12 additions were the ones that caused the evidence agreement regression on BMK_0018. This is worth stating explicitly in the Phase 2 implementation notes so whoever writes the script doesn't start from V12.
Summary
Ship this plan. It is well-reasoned, correctly sequenced, and appropriately scoped. The two tracks are genuinely independent, the instrumentation prerequisite is correctly identified, and the validation gates are specific enough to produce actionable decisions rather than ambiguous results.
The most important execution note: draft Call 2 from V11, not V12.