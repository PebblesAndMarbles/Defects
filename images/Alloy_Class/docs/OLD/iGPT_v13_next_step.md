The One Open Question for Production Decision
The FP rate number deserves honest framing before any production promotion discussion:
At n=15 with one particle GT case, FP rate is not a reliable metric. The benchmark was designed to stress-test BEEP detection, not particle specificity. BMK_0008 being the only particle case means the FP rate swings between 0.0 and 1.0 on a single call.
Before promoting V13 to production default, the question to answer is:
What is the FP rate on a larger particle-only set?
The Phase 3 validation gave partial evidence — BMK_0020, BMK_0024, BMK_0100 all correctly stayed particle under the describe-then-classify architecture. That is 3/3 on wall-adjacent particles. But production will encounter a much wider variety of particle cases.
Recommendation before production promotion: Run the describe-then-classify architecture on a 25-case particle-only set from benchmark_candidates_14day.csv filtered on adjudicated_coarse_class == particle and adjudication_status == complete. This is a one-afternoon validation that would give a reliable FP rate estimate before the architecture handles production volume.