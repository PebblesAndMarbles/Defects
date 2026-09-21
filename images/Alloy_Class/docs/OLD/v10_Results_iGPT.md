v10 Results — This Case
Scorecard vs v7
Field	v7	v10	Change
evidence_check_inset_surface_lines	unclear	yes	✅ Fixed
evidence_check_boundary_conformance	yes	yes	✓ Held
evidence_check_sunken_residual	unclear	unclear	✓ Appropriate
defect_coarse_class	possible_beep	possible_beep	✓ Held
blocked_etch_evidence	moderate	strong	✅ Upgraded
confidence	0.72	0.91	✅ More decisive
confidence format	float	float	✓ Contract clean
ISL fix worked exactly as intended. The Pathway 4 occlusion independence instruction directly produced the correct reasoning:
"visible wall junctions show horizontal trench edges terminating into a shared, uninterrupted defect boundary"
That is precisely the wall continuity signature we wanted the model to find.
Remaining Issues
1. Rationale Still Truncating
Both BF and DF rationale fields end with:
"...Boundary "
The rationale is hitting the token ceiling mid-sentence despite the 3-sentence limit instruction. At 346 completion tokens total, the JSON body itself is consuming most of the budget before rationale closes.
The parsed JSON fields are all complete and correct — the truncation is only in stage_b_raw_excerpt which is a logging artifact of how your runner captures the raw string. Check whether the actual stage_b parsed object has the full rationale — it appears to in both records. If the parsed object is complete, this may be a runner excerpt truncation rather than a model truncation.
2. BF and DF Outputs Are Identical
Both records show:
Identical stage_b JSON
Identical completion_tokens: 346
DF stage_b_input_paths still points to the BF image path
This suggests the DF inference is reusing the BF result rather than running independently — likely a runner-side issue where the darkfield image path isn't being passed correctly to the Stage B call. Worth verifying inference_image_path_stage_b is being used as the actual input rather than burned_image_path.
Overall v10 Assessment on This Case
Criterion	Status
ISL correctly upgraded to yes	✅
Evidence chain ISL+BC → strong	✅
Confidence numeric and appropriate	✅
JSON contract clean on parsed fields	✅
Rationale reasoning quality	✅ Correct logic
Raw excerpt truncation	⚠️ Check if runner artifact
DF image path routing	⚠️ Investigate
Core prompt fix is confirmed working on this case. Ready to run the full 15-case set and compare v10 vs v7 aggregate scores?

FULL 15 PAIR CASE:

v10 Aggregate Results Assessment
Progress vs Baseline
Metric	v8 (600 tok)	v9 (900 tok)	v10 (1800 tok)	Trend
Overall class agreement	~low	~0.40 est	0.5333	✅
FN BEEP rate (all)	high	high	0.3571	✅
FP BEEP rate (all)	unknown	unknown	0.0	✅ Strong
Contract failures	7 missing	2 missing	4 raw_text	⚠️
Non-numeric confidence	22	22	4	✅ Much better
Zero FP rate is the standout result — the FP suppression work from the four-case analysis is holding across the full set. The remaining problem is purely FN-side.
Eval vs Tune Split Analysis
This is the most diagnostic signal in the results:
Split	Class Agreement	FN Rate	Notes
eval (n=6)	0.8333	0.20	Strong — 1 miss only
tune (n=9)	0.3333	0.4444	Struggling — 4 misses
The eval/tune gap is large. A few interpretations:
Possibility 1: Tune Set Has Harder Cases
The tune set is all-BEEP ground truth (particle_gt_count: 0) with 9 BEEP cases — these are likely the edge cases, subtle BEEPs, small features that were harder to label in the first place. The eval set has a mix including at least 1 particle. Harder cases will naturally score lower.
Possibility 2: Prompt Overfitting to Eval Cases
The prompt was iterated using images that may overlap with the eval set. If the stress-test images we worked through are in eval, the prompt is partially fitted to those cases. The tune set represents unseen generalization and the 0.33 agreement there is the more honest performance estimate.
Possibility 3: ISL Pathways Still Not Executing on Subtle Cases
The tune set FN rate of 0.44 suggests the model is still defaulting to particle on cases where the BEEP signal is weak — small dimensional deficits, subtle asymmetry, narrow wall continuity zones. These are exactly the cases where the pathway instructions need the most forcing.
Contract Issues — 4 Raw Text Fallbacks
Still seeing raw_text_fallback_rows=4 with non_numeric_confidence=4. These are likely correlated — the same 4 rows are probably both raw_text and non-numeric.
Two likely causes:
Cause A: Prompt length pushing input tokens too high At prompt_tokens: 3046 for Stage B, the v10 prompt is significantly longer than v7. For some image/prompt combinations the total context may be hitting a limit causing the model to abandon JSON formatting.
Cause B: Specific image characteristics triggering verbose reasoning Complex images with many comparators may cause the model to write longer pathway assessments, consuming the 1800 token budget before closing JSON.
BF/DF Identity Issue Confirmation
The identical outputs across BF/DF pairs need investigation. Looking at the runner data:
stage_b_input_paths: [..._150_2.jpg] ← BF image burned_image_path: [..._150_3.jpg] ← DF image inference_image_path_stage_b: [..._150_3.jpg] ← DF image
The stage_b_input_paths field shows the BF image being passed to both calls. The inference_image_path_stage_b correctly shows the DF path but stage_b_input_paths — which is likely what the actual API call uses — is not being updated for the DF row. This means:
DF rows are being scored on the BF image
Results are identical because the input is identical
This effectively halves your unique image evidence per pair
This is a runner-side bug worth fixing before the next benchmark run — it means your 30 JSONL rows are only representing 15 unique inferences, not 30.
Priority Next Steps
Immediate — Runner Fix
Verify stage_b_input_paths is updated per row role (BF vs DF) not just inference_image_path_stage_b
This is the highest leverage fix — fixing it doubles your effective evidence per pair at no prompt cost.
Short Term — Contract Stability
The 4 raw_text fallbacks suggest a subset of images are still hitting limits. Options:
Option	Action
Raise to 2000 tokens	Low risk, may resolve remaining fallbacks
Add JSON-open instruction	"Begin your response with { immediately"
Shorten pathway instructions	Compress without losing forcing function
Medium Term — Tune Set FN Analysis
Pull the 4 FN cases from the tune set and examine:
Are they all subtle ISL cases?
Are they boundary_conformance misses?
Are they cases where both ISL and BC are genuinely weak?
This will tell you whether the remaining FNs are prompt-fixable or represent inherent ambiguity at the image quality level.
Longer Term — Eval/Tune Rebalance
With only n=6 eval and n=9 tune, the split is small enough that single-case swings move the metrics significantly. As the benchmark grows, a larger held-out eval set will give more stable performance estimates.
Summary Verdict
v10 is a meaningful improvement. The zero FP rate confirms the suppression work is solid. The 0.83 eval agreement shows the prompt is working well on cleaner cases. The tune set gap tells you the next frontier is subtle BEEP detection — cases where the ISL signal is present but small.
The runner BF/DF bug is probably the single highest-leverage fix available right now — want to dig into that first, or pull the 4 tune FN cases for prompt analysis?