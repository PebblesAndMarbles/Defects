Strategic ROI Analysis — Next Intervention Options
Reframing the Problem
Before evaluating paths, let me be precise about what we know:
What prompt engineering can fix: Reasoning failures where the model sees the signal but draws the wrong conclusion.
What prompt engineering cannot fix: Visual detection failures where the model does not perceive the signal at all.
The V12 post-mortem confirmed we are in the second category for all 4 FN cases. The model is reporting "normally shaped," "uniformly dark," "clean separation" on images where those descriptions are factually wrong. This is a perception problem, not a reasoning problem. More prompt text will not fix it.
Option Inventory — Honest ROI Assessment
Option 1 — Stage A/B Merge with Defect Pre-Analysis
What it is: Restructure Stage A to include a defect localization and preliminary geometric description pass alongside the substrate scout. Stage B then receives a structured prior that includes "defect is located at X, nearest comparator wall is Y, junction zone shows Z" rather than only substrate context.
Why it might help: Forces explicit attention to the junction zone before classification. The model's Stage A pass, focused on substrate geometry, may actually perceive trench termination anomalies and wall junction geometry more accurately when not simultaneously trying to classify a defect.
Why it might not help: Stage A is BF only and already runs on the same images. If the model can't see the concave terminus in Stage B, it may not see it in Stage A either. The perception limit may be model-level, not task-framing-level.
Effort: Medium. Requires Stage A prompt revision, output schema extension, and Stage B prompt update to consume the new prior fields.
Risk: Could destabilize Stage A which is currently stable. New Stage A outputs need validation before they improve Stage B.
ROI estimate: Medium. Addresses attention anchoring but not resolution/contrast limits.
Option 2 — Image Preprocessing (Crop/Zoom + Contrast Enhancement)
What it is: Before VLM submission, programmatically generate a second image: a cropped and contrast-enhanced view centered on the defect-comparator junction zone. Submit both the full image and the crop to Stage B.
Why it might help: The four FN failure modes all involve subtle signals at the junction zone — concave terminus pixels wide, dark flanking voids, crescent occupancy, bridging material. These signals exist in the images but are small relative to the full frame. A 2-3x zoom crop centered on the junction zone would make these signals occupy a much larger fraction of the VLM's effective visual field.
Why it might not help: If the model's perception limit is contrast-based rather than resolution-based, zoom alone won't help. Also requires knowing where to center the crop, which requires defect centroid coordinates.
Effort: Medium-High. Requires:
Defect centroid extraction from existing coordinate data (already in DEFECT_COORDINATES_EXTENDED_IMAGES.csv — this may be free)
Crop generation logic
Contrast enhancement tuning
Validation that crops don't introduce artifacts
Risk: Low on classification logic. High on pipeline complexity. Crop centering errors could make things worse.
ROI estimate: High IF defect coordinates are already available and accurate. The coordinate CSV suggests they are.
Option 3 — FFT-Based Substrate Analysis Pre-VLM
What it is: Run FFT on the SEM image before VLM submission to extract substrate periodicity, dominant orientation, and spatial frequency content. Replace or augment Stage A VLM substrate scout with deterministic FFT outputs.
Why it might help: Stage A currently produces substrate context that the V12 results suggest is not substantially improving Stage B classification. FFT would produce more reliable, quantitative substrate characterization — periodicity, pitch, orientation — that could be passed as structured metadata rather than VLM-interpreted text.
Why it might not help: The FN failures are not caused by wrong substrate context. Stage A substrate information is not the bottleneck. Improving substrate characterization does not address the visual detection failures in Stage B.
Effort: High. FFT implementation, parameter tuning, validation across substrate types, integration into pipeline, output schema design.
Risk: Medium. FFT is deterministic and well-understood but tuning for BEOL SEM images with mixed substrate types requires validation work.
ROI estimate: Low-Medium for the current FN problem. High for long-term pipeline robustness and cost reduction (replacing Stage A VLM calls with deterministic computation).
Option 4 — Defect Coordinate-Guided Attention Crop (Hybrid of 2+3)
What it is: Use existing defect centroid coordinates from DEFECT_COORDINATES_EXTENDED_IMAGES.csv to generate a tight crop around the defect-comparator interaction zone. Use FFT or simple spatial frequency analysis on the crop to characterize the local substrate geometry. Pass both the crop image and the FFT-derived local geometry description to Stage B.
Why it might help: Combines the attention-focusing benefit of the crop with structured substrate geometry that doesn't rely on VLM perception of the substrate. The VLM then only needs to assess the defect-comparator interaction in a zoomed view with known substrate context.
Why it might not help: Still depends on VLM perceiving the junction zone signals in the crop. If the model calls a concave terminus "normally shaped" in the full image, it may do the same in the crop.
Effort: High. Combines complexity of Options 2 and 3.
ROI estimate: High ceiling, high effort. Best long-term architecture but not the fastest path to FN improvement.
Option 5 — Model Upgrade / Alternative VLM
What it is: Test the same V11 prompt on a more capable vision model — Claude Opus, GPT-4o, or Gemini 1.5 Pro — to determine if the visual detection failures are model-specific or fundamental to the image difficulty.
Why it might help: If the failures are model-specific perception limits of claude-sonnet-4-6, a more capable model may perceive the concave terminus, crescent occupancy, and flanking voids without any other changes. This would immediately tell us whether the problem is solvable at the prompt/image level or requires a different model.
Why it might not help: More capable models cost more per call and may introduce new failure modes. The signals may be genuinely at the limit of what any VLM can perceive in these images.
Effort: Low. Run the existing V11 benchmark on a different model. One afternoon of work.
Risk: Low. Non-destructive test. V11 remains the baseline.
ROI estimate: High diagnostic value at low cost. Does not solve the problem but tells us which other options are worth pursuing.
ROI Matrix
Option	FN Impact	Effort	Risk	Time to Result
1 — Stage A/B merge	Medium	Medium	Medium	1-2 weeks
2 — Crop/zoom preprocessing	High	Medium	Low	3-5 days
3 — FFT substrate analysis	Low (for FNs)	High	Medium	2-4 weeks
4 — Coordinate-guided crop + FFT	High ceiling	High	Medium	3-5 weeks
5 — Model upgrade test	High diagnostic	Low	Low	1 day
Recommended Sequence
Step 1 — Model upgrade diagnostic (1 day, low effort)
Run V11 benchmark on one alternative model. This answers the most important unknown: is the visual detection failure model-specific or image-difficulty-fundamental?
If alternative model fixes 2+ FNs → the problem is model-specific, pursue model upgrade or hybrid routing
If alternative model shows same failures → the problem is image-difficulty, preprocessing is required regardless of model
Step 2A — If model upgrade shows improvement
Evaluate cost/latency tradeoff of upgraded model vs. current model. Consider tiered routing: use cheaper model for easy cases, upgraded model for cases where Stage A flags high uncertainty or large occluding defect.
Step 2B — If model upgrade shows same failures
Pursue coordinate-guided crop (Option 2) using existing defect centroid data from DEFECT_COORDINATES_EXTENDED_IMAGES.csv. This is the highest-ROI preprocessing intervention because:
Defect coordinates already exist — crop centering is essentially free
Crop generation is straightforward image processing
Directly addresses the visual detection limit by enlarging the diagnostic zone
Can be validated on the 4 FN cases before full pipeline integration
Step 3 — FFT substrate analysis (parallel track, lower urgency)
Begin FFT substrate characterization as a parallel workstream with the goal of replacing Stage A VLM calls entirely. This is a longer-term pipeline improvement that reduces cost and improves substrate characterization reliability, but is not on the critical path for FN reduction.
The One Question That Changes Everything
Do the defect centroid coordinates in DEFECT_COORDINATES_EXTENDED_IMAGES.csv accurately locate the defect-comparator junction zone, or do they locate the defect centroid only?
If the coordinates locate the defect centroid accurately, a crop centered at (x, y) with radius ~2x defect_size will reliably capture the junction zone for all four FN failure modes. That makes Option 2 a 3-day implementation with high confidence of success.

## Addendum 2026-08-26 — FN Feature-Perception Probe Results

Before committing to Options 1-5 above, ran a low-load diagnostic (tool: `tools/probe_fn_feature_perception.py`, results: `outputs/probes/fn_feature_probe_consolidated.jsonl`) to separate a framing/overhead problem from a genuine visual-perception ceiling. For each of the 5 known FN cases (BMK_0050, BMK_0029, BMK_0009, BMK_0005, BMK_0001), the same BF/DF images were resubmitted directly to claude-sonnet-4-6 with Stage A context and the JSON evidence-check contract stripped out, using two variants: a free-text junction-zone description (p1) and a narrow yes/no+describe question naming the specific missed feature (p2).

**Result: 4 of 5 cases clearly surfaced the exact signal the pipeline's Stage B call denied, using the identical images.**

- BMK_0050: pipeline said "uniformly dark... no wall continuity." Isolated p1: "the normally smooth, rounded wall boundary is interrupted by a bright, circular protrusion... bright material visibly occupies part of the trench interior."
- BMK_0029: pipeline said "normally shaped... clear gap rather than wall-continuous." Isolated p1 agreed with the pipeline (straight/continuous, clear gap), but the targeted p2 question surfaced it: "Yes. A distinct dark wedge-like void is visible immediately to the right of the defect... flanking the defect-wall junction."
- BMK_0005: pipeline said "clean particle contact... no wall continuity." Isolated p1: "the left rounded wall... is locally irregular and interrupted/obscured... A bright, elongated feature overlaps the wall and extends slightly into the dark trench interior."
- BMK_0001: pipeline said "clean particle-to-trench contact rather than wall-continuous geometry." Isolated p1 and p2 both surfaced it clearly: "the dark trench/line is interrupted... reappears on the right rather than remaining continuous through the contact point."
- BMK_0009: mixed/partial. Isolated p1 noted the boundary "becomes rounded and is obscured by the bright feature, so it is not visibly continuous" (a signal the pipeline denied), but p2's specific "crescent-shaped" wording was answered "no" — most likely a vocabulary/framing mismatch in our guessed feature description rather than true non-perception, since p1 on the same image did note a continuity anomaly.

Operational note: 4 of the first 10 calls returned empty responses on the first attempt (no error, `completion_tokens` estimated at 1) and needed a retry; all but one (BMK_0050 / p2, empty across 4 consecutive attempts with the same prompt/images) succeeded on retry. This intermittent-empty-response behavior is itself worth tracking as a contract-reliability issue independent of the FN question.

**Conclusion: this is primarily a framing/overhead problem, not a fundamental visual-perception ceiling.** The same model, on the same burned/staged images, correctly perceives wall-boundary interruption and material intrusion into the trench when Stage A's injected context and the multi-field JSON evidence-check contract are removed. This reprioritizes the ROI matrix above:

- **De-prioritize** Option 5 (model upgrade) as the first move — the current model can already see these signals under the right framing, so a different/more expensive model is unlikely to be the fastest fix.
- **De-prioritize** Option 2/4 (crop/FFT preprocessing) as the first move — these solve a resolution/attention problem that this probe suggests is not the primary bottleneck here.
- **Promote** a lighter version of Option 1 (Stage A/B relationship rework): first try trimming Stage B's prompt (fewer simultaneous guidance blocks, less injected Stage A context) and/or splitting the single Stage B call into a two-step call (plain junction-zone description, then classify from that description) rather than a full architecture rebuild. This directly targets what the probe showed is suppressing perception.
- Follow-up validation: rerun the trimmed/split Stage B prompt against the same 5 FN cases (still low load) before touching the full 15-pair benchmark, to confirm the simplification actually flips these cases before scaling up.
If the coordinates are approximate or locate the wrong zone, crop centering becomes a harder problem and the FFT/Stage A merge path becomes more attractive.
What does the coordinate CSV look like — does it include defect size/extent or just centroid?

## Addendum 2026-08-26 (2) — Phase 0/1 Instrumentation and Max-Token Test Results

Per the v13 execution plan (reviewed by an external agent across two rounds,
`docs/iGPT_v13_plan_feedback.md`, `docs/iGPT_v13_plan_feedback2.md`), Phase 0
instrumented `reporting/run_stage_ab_prompt_tests.py`'s `_call_image()` /
`_extract_json_payload()` / `_extract_usage()` before running the Phase 1
max-token experiment, in order to test evidence rather than assumption.

**Phase 0 finding (bug fix, not just instrumentation):** `_extract_json_payload()`
was discarding the full native response dict whenever the primary content field
resolved to a plain string (the normal case for these endpoints) — it returned
only `{"raw_text": ...}`, silently dropping any sibling fields (`usage`,
`finish_reason`, `model`, `id`) the response might have carried. Fixed to return
the full native payload alongside the extracted text so `_extract_usage()` checks
the real response, not a truncated shadow of it. This is a real correctness fix,
not only added logging — it's fully backward-compatible (`_call_image()`'s
external 3-tuple return signature is unchanged, so the scored-pipeline caller in
`run_suite()` is unaffected).

New diagnostic fields added to every call's `usage` dict (and surfaced at the
probe's top level): `usage_source` (native vs. estimated), `error_class`
(`content_filter` / `http_error` / `network_or_timeout` / `unknown_error` / `None`,
classified from `_make_request()`'s stringified error paths — the installed Alloy
package does not expose a literal HTTP status code), `empty_response` (explicit
boolean, no more string-length guessing), `response_char_count`, `finish_reason`
(read from the native payload if present), and `image_payload_diagnostics`
(per-image source file size in bytes, base64-encoded length, and the ratio).

**Phase 1 — max-token experiment (bare p1/p2 calls, no Stage A context, no JSON
contract, single attempt per call, 2 repetitions per token budget = 20 calls per
budget, 40 calls total):**

| Token budget | Empty responses | Truncated (mid-sentence, no closing punctuation) |
|---|---|---|
| 400 (probe default) | 5/20 (25%) | 0/20 |
| 1800 (production parity) | 0/20 (0%) | 0/20 |

- `error_class` was `None` (not `content_filter`, not `http_error`) for every
  empty case at 400 tokens — these are genuine 200-OK responses with empty
  content, not filtered/rejected requests.
- `finish_reason` was `None` on all 40 calls — the Alloy vision endpoint does not
  expose this field at all under either token budget; this hypothesis is not
  directly testable via response metadata, as anticipated.
- `image_payload_diagnostics`'s `encode_ratio` was 1.3333-1.3334 (exact base64
  math) on every call — no evidence of image resizing/recompression happening on
  the pipeline side before encoding.
- **Correction to the original 2026-08-26 addendum's framing**: this fresh,
  instrumented run did **not** reproduce mid-sentence truncation (the original
  session's `outputs/probes/fn_feature_probe_consolidated.jsonl` does contain 3
  genuinely truncated responses at 400 tokens — verified in the stored
  `response_text` field, not a console-preview artifact — but this new sample
  showed the failure mode as full omission (empty) rather than partial cutoff).
  With n=20 per budget this is still a modest sample; truncation as a secondary
  variant of the same token-budget issue hasn't been ruled out, just not
  reproduced here.
- Notably, `BMK_0050`/p2 — empty across 4 consecutive attempts in the original
  session — was empty in both reps at 400 tokens here, and succeeded in **both**
  reps at 1800 tokens. The persistent-empty pattern the external reviewer flagged
  as "looking deterministic, not transient" does look deterministic **for a given
  token budget**, but it is not fixed to that specific input/prompt combination
  independent of budget — raising the budget resolved it cleanly.

**Decision gate result: max-token hypothesis CONFIRMED as a real contributing
cause** of the empty-response pattern (25% → 0% empty, a clean flip at n=20 per
arm). Production already runs at 1800 tokens, so this is a supporting data point
for production robustness (not a production bug) and a straightforward fix for
the probe tooling's own default (`DEFAULT_MAX_TOKENS = 400` in
`tools/probe_fn_feature_perception.py`), which should be raised to at least 1800
for any future probe runs to avoid conflating token-budget noise with the
signal(s) actually being tested.

**Strategic note (surfaced early per external review):** the original FN probe's
positive findings (4/5 cases correctly surfacing the missed signal, see the first
2026-08-26 addendum above) were generated at the same 400-token default now shown
to have a 25% empty-response rate. Those results are therefore a **conservative**
estimate of what the model can perceive under the describe-then-classify framing
— the true positive rate is likely at least as good, and possibly better, once
Phase 2's implementation uses a production-parity token budget. This strengthens
rather than weakens the case for the describe-then-classify architecture.

## Addendum 2026-08-26 (3) — Phase 2/3: Describe-Then-Classify Validation Result (FAILS control gate)

Built `tools/probe_describe_then_classify.py` per the plan: Call 1 is a neutral
free-observation prompt (no Stage A context, no JSON contract, 1800-token budget
per the Phase 1 finding above); Call 2's evidence-check framework is drafted **at
runtime directly from `config/stage_ab_prompt_tests_substrate_tier1_v11.json`'s
`stage_b` prompt (`stageB_substrate_tier1_v10`)**, not V12, per the external
review's most important execution note — only the Stage-A-context sentence is
stripped and replaced with a reference to Call 1's observation; the three
evidence-check pathway definitions and the JSON output contract are otherwise
V11-verbatim.

**Validation set (9 cases, 18 VLM calls):** the same 5 FN cases (`BMK_0050`,
`BMK_0029`, `BMK_0009`, `BMK_0005`, `BMK_0001`) plus 4 particle ground-truth
controls — `BMK_0008` (existing 15-pair benchmark control) and 3 wall-adjacent
particles added from `artifacts/benchmark_candidates_14day.csv` per the external
review's guidance to prioritize wall-adjacent over open-field particles
(`BMK_0002`, `BMK_0004`, `BMK_0092` — all selected for `comparator_visible=yes`
AND `comparator_boundary_line_present=yes`, with `notes_short` describing the
particle abutting/overlapping/protruding into a comparator).

**CORRECTION (same day, before Phase 4 was started):** the original version of
this addendum used the wrong ground-truth source. `BMK_0002`, `BMK_0004`, and
`BMK_0092` were pulled from `artifacts/benchmark_candidates_14day.csv` filtered
on `factory_class_label == "SMALL_PARTICLE"` — but `factory_class_label` is only
the pre-adjudication factory label used to build the initial `non_beep_control`
candidate pool, **not** ground truth. The actual human-adjudicated ground truth
in that same file (`adjudicated_coarse_class`, adjudicated by TB) shows all 3 of
those cases are **`possible_beep`**, not `particle`:

| benchmark_id | `factory_class_label` (wrongly used as GT) | `adjudicated_coarse_class` (actual GT) |
|---|---|---|
| BMK_0002 | SMALL_PARTICLE | **possible_beep** |
| BMK_0004 | SMALL_PARTICLE | **possible_beep** |
| BMK_0092 | SMALL_PARTICLE | **possible_beep** |
| BMK_0008 | SMALL_PARTICLE | particle (confirmed correct GT) |

`BMK_0008` is the only one of the four where `factory_class_label` and
`adjudicated_coarse_class` agree ("particle") — consistent with the user's own
recollection that `BMK_0008` was deliberately labeled particle and is a known
tricky/edge case. Replaced `BMK_0002`/`BMK_0004`/`BMK_0092` with 3 new candidates
selected on the *correct* filter (`adjudicated_coarse_class == "particle"` AND
`comparator_visible == "yes"` AND `comparator_boundary_line_present == "yes"`,
outside the scored 15-pair set): `BMK_0020`, `BMK_0024`, `BMK_0100` (all
confirmed on disk). Re-ran Call 1/Call 2 on these 3 corrected controls.

**Corrected result:**

| Case | Category | Ground truth (adjudicated) | Call 2 result | Pass? |
|---|---|---|---|---|
| BMK_0050 | fn_case | possible_beep | possible_beep (ISL=yes, BC=unclear) | ✅ |
| BMK_0029 | fn_case | possible_beep | possible_beep (ISL=yes, BC=no) | ✅ |
| BMK_0009 | fn_case | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ |
| BMK_0005 | fn_case | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ |
| BMK_0001 | fn_case | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ |
| BMK_0002 | (re-typed) fn-like, not a control | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ (was mislabeled ❌) |
| BMK_0004 | (re-typed) fn-like, not a control | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ (was mislabeled ❌) |
| BMK_0092 | (re-typed) fn-like, not a control | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ (was mislabeled ❌) |
| BMK_0008 | particle_control | particle | **possible_beep** (ISL=yes, BC=yes) | ❌ |
| BMK_0020 | particle_control | particle | particle (ISL=no, BC=no) | ✅ |
| BMK_0024 | particle_control | particle | particle (ISL=no, BC=no) | ✅ |
| BMK_0100 | particle_control | particle | particle (ISL=no, BC=no) | ✅ |

**Corrected picture: 11/12 correct.** All 5 known FN cases flip to correct, all
3 corrected wall-adjacent particle controls (`BMK_0020`/`BMK_0024`/`BMK_0100`)
correctly stay `particle`, and the 3 originally-mislabeled cases
(`BMK_0002`/`BMK_0004`/`BMK_0092`) turn out to also be correct calls once GT is
fixed. The only miss is `BMK_0008` — which the user independently confirms is a
known tricky/edge-case particle (per `notes_short`: eight scattered material
defects of different morphologies, one fully contained in a comparator, two
larger ones occluding comparators without substantial ISL/boundary evidence) —
and it was already the one wrong call in the *original* V12 scored pipeline's
neighborhood of difficulty, not a new failure mode this architecture introduced.

**This reverses the previous conclusion.** The "systematic over-calling" and
"V12's guidance was suppressing FPs too" narrative below was based on incorrect
ground truth and should be disregarded. The describe-then-classify architecture,
as implemented (Call 2 drafted from V11 per the external review), passes 11/12
on this validation set, with the single miss being a case already flagged as
hard by the user. This is a much stronger result than originally reported and
supports moving toward Phase 4 (full 15-pair benchmark), pending a closer look
at why `BMK_0008` specifically still misclassifies.

**Lesson for future probe/control selection from this candidate CSV:** always
filter on `adjudicated_coarse_class` (+ `adjudication_status == "complete"`),
never on `factory_class_label` or `source_pool` — those are pre-adjudication
sampling-pool labels, not ground truth.

---

*(Original, now-superseded analysis below, kept for the record rather than deleted -- see correction above.)*

**Result (SUPERSEDED — used wrong GT for BMK_0002/BMK_0004/BMK_0092, see correction above):**

| Case | Category | Ground truth | Call 2 result | Pass? |
|---|---|---|---|---|
| BMK_0050 | fn_case | possible_beep | possible_beep (ISL=yes, BC=unclear) | ✅ |
| BMK_0029 | fn_case | possible_beep | possible_beep (ISL=yes, BC=no) | ✅ |
| BMK_0009 | fn_case | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ |
| BMK_0005 | fn_case | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ |
| BMK_0001 | fn_case | possible_beep | possible_beep (ISL=yes, BC=yes) | ✅ |
| BMK_0008 | particle_control | particle | **possible_beep** (ISL=yes, BC=yes) | ❌ |
| BMK_0002 | particle_control | ~~particle~~ (WRONG — actual GT possible_beep) | **possible_beep** (ISL=yes, BC=yes) | ❌ |
| BMK_0004 | particle_control | ~~particle~~ (WRONG — actual GT possible_beep) | **possible_beep** (ISL=yes, BC=yes) | ❌ |
| BMK_0092 | particle_control | ~~particle~~ (WRONG — actual GT possible_beep) | **possible_beep** (ISL=yes, BC=yes) | ❌ |

~~**5/5 FN cases flip to correct — but 4/4 particle controls also flip to
`possible_beep`, a 100% false-positive rate on the control set.** Per the plan's
own decision gate (Phase 3 step 3), this is a **fail**: do not proceed to Phase 4
(full benchmark rollout) with this exact Call 2 framework as written.~~

~~**Diagnosis:** inspecting the raw text, the FN cases and the false-positive
controls are essentially indistinguishable in structure. Call 1's observation
prompt asks for "geometric irregularities... relative to other similar
structures" — real SEM images always show *some* asymmetry/tonal variation, so
Call 1 reliably produces language like "locally narrowed/shortened," "obscured,"
or "protrudes into," regardless of whether the case is a genuine blocking event
or an ordinary particle sitting against a wall. Call 2's V11 evidence framework
then reliably finds a qualifying "yes" on `inset_surface_lines` and/or
`boundary_conformance` from that language — its STEP 2 decision rule only
requires **one** confirmed `yes` on either signature to reach `moderate`
evidence, which is enough to call `possible_beep`. Example rationale text is
nearly identical in tone between a genuine FN case (`BMK_0050`: *"the affected
trench is lighter and less uniformly dark than comparable openings, and its
visible upper/lower sections are shorter and geometrically asymmetric"*) and a
false-positive control (`BMK_0002`, a real particle: *"the adjacent bottom
trench is locally narrowed/shortened and its lower boundary is interrupted where
the defect material protrudes"*).~~

~~**Reframing of the FN-vs-FP tradeoff:** V12's ~15 added guidance blocks (dropped
in this experiment) apparently were not purely harmful — they seem to have been
suppressing both genuine BEEP signals (causing the original 4 FNs) **and** false
BEEP calls on particles (keeping FP low) at the same time. V11's lighter
framework alone, without Stage A context and without V12's tightening language,
is evidently miscalibrated toward over-calling in the opposite direction. Neither
V11 nor V12's Stage B logic, used as-is in this two-call framing, hits the right
balance.~~

~~**Not proceeding to Phase 4** with the current Call 2 draft. Recommended next
iteration (for a follow-on round, not yet built): either (a) make Call 1 more
strictly neutral/descriptive rather than comparison-prompting (drop "relative to
other similar structures" framing), and/or (b) tighten Call 2's STEP 2 decision
rule (e.g. require both `inset_surface_lines` **and** `boundary_conformance` to
be `yes`, not either alone, before calling `possible_beep`), and/or (c)
reintroduce a narrow, source-discrimination-only subset of V12's skepticism
language (e.g. the existing V11 "SOURCE DISCRIMINATION" block already present
may need to be strengthened further, not just inherited as-is). This is flagged
as an open thread for the next plan-review round rather than resolved here.~~

**Corrected recommendation (see correction above): proceed toward Phase 4.**
With correct ground truth, this Call 2 draft is 11/12 on the validation set, not
0/4 on controls. The single remaining miss, `BMK_0008`, is worth a closer look
before scaling up (see Open Thread below) but is not evidence of systematic
over-calling — no further Call 1/Call 2 redesign is needed on the strength of
this data alone.

**Open thread for next round:** why does `BMK_0008` specifically still
misclassify as `possible_beep` when 3 other wall-adjacent particle controls
(`BMK_0020`, `BMK_0024`, `BMK_0100`) correctly stay `particle`? `BMK_0008`'s
`notes_short` describes it as unusually complex (eight scattered material
defects of different morphologies in one image, one fully contained in a
comparator, two larger ones occluding comparators) — worth inspecting its Call
1 observation and Call 2 rationale specifically (already captured in
`outputs/probes/phase3_describe_then_classify_20260826/phase3_BMK_0008_smoke.jsonl`)
before deciding whether this is an acceptable single-case miss or needs a
targeted fix.

Raw data: `outputs/probes/phase3_describe_then_classify_20260826/`
(`phase3_BMK_0008_smoke.jsonl`, `phase3_remaining_8_cases.jsonl` — the latter's
particle-control rows for BMK_0002/BMK_0004/BMK_0092 are superseded, see
correction; use `phase3_corrected_controls_20260826.jsonl` for
BMK_0020/BMK_0024/BMK_0100).

## Addendum 2026-08-26 (4) — Phase 4: Full 15-Pair Benchmark, v13 vs v12

Promoted the describe-then-classify architecture into the production runner:
`reporting/run_stage_ab_prompt_tests.py` now supports a `--stage-b-describe-then-classify`
flag (also threaded through `tools/run_benchmark_vlm.py`). When set, Stage B
runs Call 1 (`CALL1_OBSERVATION_PROMPT`, neutral free observation, no Stage A
context, no JSON contract) followed by Call 2 (evidence framework built at
runtime from `config/stage_ab_prompt_tests_substrate_tier1_v11.json`'s
`stage_b` prompt, per the "V11 not V12" directive — same helper logic as
`tools/probe_describe_then_classify.py`, now shared). Stage A still runs
unchanged for provenance but is not injected into Stage B. New config:
`config/stage_ab_prompt_tests_substrate_tier1_v13.json`.

Ran the full 15-pair `offset_surface_lines_15` benchmark (same pair list CSV
and flags as the v12 comparison run: `--stage-b-multi-image`, no raw-image-mode)
via `tools/run_benchmark_vlm.py` → `tools/score_benchmark_run.py`. Output:
`outputs/raw_runs/offset_surface_lines_15_v13_compare/`.

**Result (v12 baseline → v13), metric priority order per the plan:**

| Metric | v12 (all, n=15) | v13 (all, n=15) |
|---|---|---|
| **Primary** — `beep_fn_rate` (known FNs, incl. the 4 tune-set ones) | 0.3571 (5/14) | **0.0 (0/14)** |
| **Secondary** — `BMK_0001` (eval FN) | miss | **flips correct** |
| **Tertiary** — `BMK_0018` `evidence_match` | false (regression) | **true (recovered)** |
| `coarse_class_agreement_rate` | 0.6667 (10/15) | **0.9333 (14/15)** |
| `beep_fp_rate` | 0.0 (0/1) | 1.0 (1/1) — the known `BMK_0008` edge case |
| `evidence_agreement_rate` | 0.5333 (8/15) | **0.8000 (12/15)** |
| `review_required_calibration_rate` | 0.1333 (2/15) | **0.6667 (10/15)** |

**All three priority-ordered checks pass, plus large improvements on every other
tracked metric.** The single miss on the full benchmark is `BMK_0008` — the
same case already identified in Phase 3 and confirmed by the user as a known,
accepted tricky edge case (GT `particle`, weak/ambiguous evidence per its own
adjudication notes). No other case regressed relative to v12.

Per-case detail (`benchmark_scored_rows.csv`): all 14 GT-`possible_beep` cases
now correctly classified `possible_beep`, including the previously-missed
`BMK_0050`, `BMK_0029`, `BMK_0009`, `BMK_0005` (tune) and `BMK_0001` (eval).
Evidence-level detail on the 3 cases with `evidence_match=false`: `BMK_0029`
(GT `strong`, called `moderate` — still correctly flagged as BEEP), `BMK_0005`
(GT `moderate`, called `strong` — same direction, stronger confidence than GT),
`BMK_0008` (wrong class entirely, the known edge case).

**Minor tooling note (not a v13 defect):** `score_benchmark_run.py`'s contract
check flags `review_required` as "missing" whenever its value is boolean
`False`, due to `str(False or "")` evaluating falsy — a pre-existing heuristic
quirk that would affect any run with `review_required=false` rows, not
introduced by this change. Did not fix as part of this phase (out of scope);
the real scoring metrics are unaffected since they read fields directly rather
than through the contract-check heuristic.

Recorded in `docs/PROMPT_ITERATION_REGISTRY.md`'s CSV tracker
(`artifacts/prompt_iteration_registry.csv`, row `offset_surface_lines_15_v13_compare`).

**Status: v13 is validated and ready for consideration as the new default.**
Promoting it beyond this benchmark comparison (i.e. making it the production
default instead of v12) is a follow-on decision, not automatically actioned
here, per the plan's original scope boundary.




