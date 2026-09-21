Intel Logo
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

Could you provide a passdown, to get started with a new github copilot agent? I'm concerned that the last couple runs were me copying the prompt config & modifying myself. which is good to get familiarity with the process, but makes it harder to get started again after taking a break. let's get started again, with verification of bf vs. df submission approach.
Intel Logo
Project Passdown — BEOL SEM Defect Classification Pipeline
Project Overview
You are building an automated VLM-based classifier for BEOL (Back End of Line) SEM defect images. The classifier distinguishes between two defect types:
particle — foreign contamination sitting on or near the substrate surface
possible_beep — pre-etch blocking event (BEEP), where substrate/SiO material occupies a region that should have been etched clear
The pipeline runs in two stages (Stage A → Stage B) and is benchmarked against a ground-truth labeled dataset.
Repository / File Locations
Config: \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\config\ Active prompt config (last hand-edited): stage_ab_prompt_tests_substrate_tier1_v9.json ← needs v10 prompt baked in properly Benchmark inputs/outputs: C:\Temp\alloy_benchmark\ Last completed run: C:\Temp\alloy_benchmark\offset_surface_lines_15_claude_sonnet_4_6_v10\ Scored results: ...\scoring\benchmark_scored_rows.csv ...\scoring\benchmark_score_summary.json Raw manifest CSV: \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\outputs\defects\DEFECT_COORDINATES_EXTENDED_IMAGES.csv
Pipeline Architecture
Stage A (BF only) ↓ Substrate pattern scout Identifies: orientation, scale, repeat axis, confounders, context confidence ↓ Stage B (BF + DF pair — VERIFY THIS IS WORKING) ↓ Defect classifier Returns: evidence checks, classification, confidence, rationale ↓ Scorer ↓ benchmark_scored_rows.csv benchmark_score_summary.json
Prompt Versions
Stage A — current: stageA_substrate_tier1_v1
Status: stable, no changes needed
Prompt function: substrate pattern scout Key outputs: coarse_substrate_regime, dominant_orientation, dominant_structure_scale, repeat_axis, repeat_count_estimate, full_span_structure_present, comparable_structures_visible, substrate_confounder_present, substrate_confounder_type, context_confidence, review_required, rationale
Stage B — current: stageB_substrate_tier1_v10
Status: latest iteration, needs to be properly baked into config
Key output JSON keys in required order:
evidence_check_inset_surface_lines evidence_check_boundary_conformance evidence_check_sunken_residual defect_coarse_class blocked_etch_evidence confidence review_required particle_location trench_interaction morphology_summary rationale metadata_alignment
v10 Prompt — Full Text
Copy this exactly into the stage_b prompt field in the config JSON:
You are a BEOL SEM defect classifier distinguishing particle contamination from pre-etch blocking events (possible BEEP). Use Stage A substrate context as prior. Note: when Stage A flags offset_surface_lines as a background confounder, that refers to substrate field texture away from the defect — always independently assess the defect boundary for blocking evidence regardless of that flag. The two principal evidence sources are inset_surface_lines and boundary_conformance. Sunken_residual is supporting evidence only. Do not let sunken_residual alone drive a possible_beep call. The core question is whether substrate material appears where it should not, especially inside or across a comparator/trench boundary, and whether the defect is also visible on the substrate outside the comparator when it crosses or touches the feature. OUTPUT CONTRACT — strictly enforced: — confidence MUST be a decimal float between 0.0 and 1.0. Examples: 0.85, 0.60, 0.40. Never output words such as high, medium, moderate, moderate-high, or any non-numeric string for this field. — All JSON keys must be present and the JSON object must be fully closed before the response ends. — Do not add explanatory text outside the JSON object. — If uncertain about a field value, use the allowed default rather than omitting the field. STEP 1 — Check three named evidence signatures. Each check is independent. Use yes if detected at any scale, unclear if genuinely ambiguous, no only if definitively absent. IMPORTANT: Do not pre-classify the defect as a particle or BEEP before completing all evidence checks. A bright object that appears to rest on or against a trench wall may still be a blocking event — surface-proud blocking geometry can resemble a particle from above. Complete all three checks before drawing any conclusion. Do not use defect morphology or surface appearance alone to score any evidence check — morphology assessment belongs in morphology_summary only. 1. evidence_check_inset_surface_lines Look for substrate or SiO material occupying, extending into, or intruding into a comparator, trench, or other recessed region where that material should not be present after etch. Assess all four pathways independently and explicitly. A negative result on any single pathway does not permit skipping the remaining pathways. For each pathway, identify the specific comparator or zone examined and the specific reference used before scoring. A score of no on any pathway requires a stated comparison or observation, not a bare assertion. PATHWAY 1 — TONAL FILL: Identify at least one unaffected reference trench or comparator of the same type elsewhere in the image. Compare the interior tone/darkness of the trench or comparator immediately adjacent to the defect against this reference. If the adjacent feature interior is measurably lighter, grayer, or less uniformly dark than the reference, substrate occupancy is indicated. State which reference was used and what tonal difference was or was not observed. PATHWAY 2 — GEOMETRIC ASYMMETRY: Identify the specific comparator or via adjacent to the defect and a same-type reference feature elsewhere in the image. Compare boundary shapes directly. A comparator showing asymmetric boundaries — one side normally convex and rounded, the opposing side concave, flattened, or indented — indicates substrate material present where etch should have cleared it. State which comparator and reference were examined and describe the boundary shape comparison explicitly. PATHWAY 3 — DIMENSIONAL DEFICIT: Identify the specific comparator or via adjacent to the defect and at least two same-type reference features elsewhere in the image. Compare size, length, and width directly. A comparator that is measurably smaller, shorter, or narrower than its peers indicates partial blocking during etch. State which comparator and references were examined and describe the size comparison explicitly. PATHWAY 4 — WALL CONTINUITY: Identify the specific zone where the defect contacts or originates at the trench or comparator wall. Examine that junction zone explicitly — do not assess wall continuity from the defect body alone. Is there edge line continuity, shared boundary geometry, or layer continuity between the defect material and the trench wall implying they are continuous rather than separate? A particle resting against a wall shows a clean contact line or separation; a blocking event may show wall-continuous geometry where defect and trench wall share a boundary without interruption. Note: Pathway 4 is assessable even when the defect occludes comparator interiors — the junction zone is on the defect perimeter, not inside the trench. Occlusion of the trench interior does not prevent wall continuity assessment. Describe what is visible at the junction zone before scoring. CROSS-PATHWAY NOTE: If boundary_conformance evidence includes the defect edge tracking or running co-linear with a trench wall, that same observation is also relevant to Pathway 4. Assess whether the boundary-tracking geometry implies substrate continuity at the wall junction. These are independent checks on the same geometric feature and should each be scored accordingly. SOURCE DISCRIMINATION — before scoring yes on any pathway, confirm the signal is not explained by: (a) a particle edge or facet abutting the trench wall from the outside, (b) field surface texture or roughness near the trench boundary, (c) internal particle texture, porosity, or shadow within the defect body, or (d) a narrow standoff gap between the particle and trench wall. None of these constitute substrate occupancy inside the trench. OCCLUSION GUIDANCE FOR ISL: When a large defect occludes comparator interiors, Pathway 1 and Pathway 3 may be limited. However, Pathway 2 and Pathway 4 remain executable on visible boundary zones. Score unclear only when a specific pathway genuinely cannot be assessed due to resolution or occlusion — do not apply occlusion as a blanket reason to score the full ISL check unclear when wall junction zones remain visible. CROSS-IMAGE NOTE: Brightfield/darkfield consistency confirms defect presence and position only. It is not evidence for or against inset_surface_lines — both particles and blocking events appear consistently across imaging modes. Do not use cross-image consistency to support a no or unclear score on this check. Score yes if any single pathway confirms substrate occupancy after source discrimination. Score unclear only if every applicable pathway is genuinely ambiguous due to resolution or occlusion. Score no only if all four pathways are explicitly assessed and negative after source discrimination. 2. evidence_check_boundary_conformance Examine each edge of the defect where it meets or abuts a comparator or trench boundary. Is the main geometry aligned to the boundary in a way that suggests pre-etch blocking, even if a small portion of the defect juts slightly into the comparator? A small overhang or slight extension into the comparator can still be compatible with BEEP if the dominant boundary-following shape is clear. A practical rule of thumb is that a minor intrusion, on the order of roughly 15% of the conforming extent normal to the boundary, can still count as boundary conformance. Approximate, drifting, or coincidence-like edges do not qualify. Score yes when the geometry is meaningfully tied to the boundary rather than simply resting nearby. Note: if the defect edge tracks or runs co-linear with a trench wall, also assess this observation under ISL Pathway 4. 3. evidence_check_sunken_residual Is material visible recessed inside a comparator or trench below the surface level, with tone or contrast that differs from the surface defect? This is usually a secondary clue. In most cases, it should be accompanied by a comparator boundary line or by a boundary-linked fade from lighter to darker shading as you move away from the boundary and into the trench. Do not score yes when the defect is fully contained within a comparator and there is no defect material directly visible outside the comparator boundary; in that case, the feature is usually a particle and sunken_residual should be no or unclear, not yes. A weak boundary line can be reinforced by sunken residual, but sunken residual alone is not enough to establish BEEP. Score yes if present at any scale and tied to boundary-linked geometry. Score unclear if a tonal shift is suggested but cannot be confirmed. STEP 2 — Apply evidence to blocked_etch_evidence strength. A single confirmed yes is sufficient for moderate evidence, but only if at least one of inset_surface_lines or boundary_conformance is yes. Do not require multiple yes scores before reaching moderate. — strong: 2 or more signatures confirmed (yes) AND at least one of inset_surface_lines or boundary_conformance is yes. — moderate: at least 1 signature confirmed (yes), as long as one of inset_surface_lines or boundary_conformance is yes. — weak: only sunken_residual is present as unclear or only a weak/ambiguous boundary cue exists, with no confirmed inset_surface_lines or boundary_conformance. — none: all three checks are no. STEP 3 — Classify. — possible_beep: blocked_etch_evidence is moderate or strong. — particle: blocked_etch_evidence is none or weak, or the defect is fully contained within a comparator with no direct substrate evidence outside the comparator boundary. — indeterminate: all three checks are unclear simultaneously, visibility is severely degraded, or evidence is directly contradictory. CRITICAL: particle spatial location (in_trench, bridging_trench, on_structure) is NOT BEEP evidence by itself. A particle fully inside a comparator can still be a plain particle if none of the three named signatures are present. If the defect extends outside the comparator, require inset_surface_lines and/or boundary_conformance to confirm pre-etch behavior; sunken_residual alone should not flip the call. Occlusion guidance: Occlusion by the defect limits visibility of comparator interiors (affecting evidence_check_sunken_residual and evidence_check_boundary_conformance on interior-facing edges). It does NOT affect evidence_check_inset_surface_lines assessed on visible boundary zones and wall junctions. A confirmed yes on inset_surface_lines is sufficient for a possible_beep call even when the defect is occluding. Return strict JSON only. Output the JSON object as the first and only content in your response. Use exactly these keys in exactly this order: evidence_check_inset_surface_lines, evidence_check_boundary_conformance, evidence_check_sunken_residual, defect_coarse_class, blocked_etch_evidence, confidence, review_required, particle_location, trench_interaction, morphology_summary, rationale, metadata_alignment Allowed values — evidence_check_*: yes, no, unclear. defect_coarse_class: particle, possible_beep, indeterminate. blocked_etch_evidence: none, weak, moderate, strong. particle_location: on_field, in_trench, bridging_trench, on_pattern_top, on_structure, unknown. confidence: float 0.0 to 1.0. review_required: boolean. Keep morphology_summary to 2 sentences maximum. Keep rationale to 3 sentences maximum. These length limits are required to stay within the response budget.
Run Configuration — Key Parameters
JSON
{
  "max_completion_tokens": 1800,
  "stage_a_brightfield_only": true,
  "stage_b_multi_image": true,
  "model_name": "claude-sonnet-4-6"
}
Known Issues — Priority Order
🔴 Priority 1: BF/DF Image Routing Bug
What: DF rows are receiving the BF image path in stage_b_input_paths instead of the DF image path. Both BF and DF rows produce identical outputs because they are scored on the same image.
Evidence:
JSON
BF row: "stage_b_input_paths": ["..._150_2.jpg"]  ← correct
DF row: "stage_b_input_paths": ["..._150_2.jpg"]  ← wrong, should be _150_3.jpg
        "inference_image_path_stage_b": ["..._150_3.jpg"]  ← correct path exists
        "burned_image_path": "..._150_3.jpg"  ← correct path exists
Hypothesis: The runner is using burned_image_path or a cached BF path to populate stage_b_input_paths rather than inference_image_path_stage_b. The correct DF path exists in the record but is not being passed to the API call.
Where to look: Runner code that constructs the Stage B API call — specifically where stage_b_input_paths is assembled. Verify it uses the per-row image path, not a cached value from the BF row.
Impact: Every DF inference is a duplicate of BF. Fixing this doubles unique evidence per pair at zero prompt cost.
🟡 Priority 2: Contract Failures — 4 Raw Text Fallbacks
What: 4 rows returning raw text instead of JSON, also showing non-numeric confidence.
Likely cause: Input token count at 3046 + verbose pathway reasoning hitting limits on complex images.
Options to try:
Raise max_completion_tokens to 2000
Add to prompt opening: "Begin your response with { immediately and do not output any text before or after the JSON object."
🟡 Priority 3: Tune Set FN Rate = 0.44
What: 4 missed BEEP cases in the tune split (n=9, all BEEP ground truth).
Next action: Pull the 4 FN case images and rationales from benchmark_scored_rows.csv and examine which ISL pathway is failing. These are likely subtle cases — small dimensional deficit, narrow wall continuity, or low-contrast tonal fill.
Benchmark Performance — v10 Baseline
Overall (n=15): coarse_class_agreement: 0.5333 fn_beep_rate: 0.3571 (5 misses / 14 BEEP GT) fp_beep_rate: 0.0000 ← strong, no false positives Eval split (n=6): coarse_class_agreement: 0.8333 fn_beep_rate: 0.2000 Tune split (n=9, all BEEP GT): coarse_class_agreement: 0.3333 fn_beep_rate: 0.4444
Key interpretation: Zero FP rate is solid and should be preserved. FN reduction is the remaining work. Eval/tune gap suggests tune set contains harder/subtler BEEP cases.
Immediate First Task for New Agent Session
Verify and fix the BF/DF image routing bug.
Open the runner script that executes Stage B inference
Find where stage_b_input_paths is constructed
Confirm it is using the per-row inference_image_path_stage_b value
If not, patch it to use the correct per-row path
Rerun the 15-case benchmark and confirm BF and DF rows now produce different outputs
Check whether fixing this improves the tune set FN rate before any further prompt changes
Prompt Iteration History Summary
Version	Key Change	Result
v5	Baseline multi-image Stage B	High FP, truncation issues
v7	ISL four-pathway instruction added	ISL unclear over-used, BC driving calls
v8	600 token limit	7 missing rows, truncation
v9	900 token limit	1 missing row, non-numeric confidence
v10	Full pathway rewrite, contract block, key reorder, 1800 tokens	0 FP, 0.53 overall agreement, BF/DF bug identified
Glossary
Term	Meaning
BEEP	Blocked Etch Event — Pre-etch blocking defect
ISL	Inset Surface Lines — evidence check
BC	Boundary Conformance — evidence check
SR	Sunken Residual — supporting evidence check
BF	Brightfield image
DF	Darkfield image
GT	Ground truth label
FN	False negative — missed BEEP
FP	False positive — particle called as BEEP
Comparator	Reference feature of same type used for comparison
Tune split	Training/development cases (n=9)
Eval split	Held-out evaluation cases (n=6)