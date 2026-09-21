Diagnostic Result — Analysis and Next Steps
This is a Significant Finding
The probe result resolves the most important unknown in the entire project. Let me state it precisely:
The model can see all four FN signals. The pipeline is suppressing their expression.
This is a fundamentally different problem than what we were solving with V12. We were adding more instructions to fix a perception problem that doesn't exist. The real problem is that the current Stage B framing is actively interfering with perception that the model already has.
What is Likely Causing the Suppression
Based on the probe design — stripping Stage A context injection and JSON contract — there are three candidate mechanisms:
Candidate 1 — Stage A Context Poisoning
Stage A outputs offset_surface_lines, large_occluding_defect, and similar confounder flags. When these are injected as priors into Stage B, the model may be anchoring on them as permission to dismiss boundary evidence. The prompt says "use Stage A substrate context as prior" — and the model is doing exactly that, but the prior is suppressing rather than informing.
Specifically: when Stage A flags large_occluding_defect, Stage B appears to interpret this as "comparator interiors are not assessable" and cascades that to "all pathways unclear or no." This is the wrong inference but it is a reasonable reading of the current framing.
Candidate 2 — JSON Contract Forcing Premature Commitment
The strict JSON output contract with enumerated allowed values may be causing the model to resolve ambiguity toward the nearest clean answer rather than holding genuine uncertainty. When the model is mid-reasoning and uncertain, the contract pressure pushes it to a definitive no rather than unclear because no is a cleaner JSON value. This collapses the evidence aggregation logic toward particle.
Candidate 3 — Pathway Instruction Volume Creating Anchoring
The sheer volume of pathway instructions — four pathways, multiple variants each, source discrimination rules, scope notes — may be causing the model to over-index on the instructions themselves rather than the image. The model reads the instructions, forms an expectation of what it should see, looks at the image through that expectation, and reports against the expectation rather than against the image. The probe, with no instructions, forced genuine image-first observation.
Recommended Architecture — Describe Then Classify
The probe result directly suggests the fix: separate observation from classification.
Proposed Stage B Structure
Stage B — Call 1: Free Observation
Describe what you see at the defect-comparator junction zone in this image. Focus on: the defect's position relative to trench or comparator walls, any geometric irregularities in the nearest comparator or trench relative to others in the field, and any material visible inside features that should be clear. Do not classify. Do not use structured output. Describe only what is visually present.
Output: free text description, 3-5 sentences.
Stage B — Call 2: Classify from Observation
Given this image and the following observation: [insert Call 1 output] Now apply the evidence framework and return the classification JSON. [abbreviated evidence rules + JSON contract]
Output: structured JSON as current.
Why this should work: Call 1 replicates the probe condition that successfully surfaced the signals. Call 2 then applies the classification framework to an observation that already contains the correct geometric description, rather than asking the model to simultaneously observe and classify under contract pressure.
What to Validate Before Full Benchmark
Test the describe-then-classify structure on the 5 FN cases first:
Case	Expected Call 1 output	Pass condition
BMK_0050	Mentions crescent/partial fill of comparator	ISL yes in Call 2
BMK_0029	Mentions concave/irregular trench terminus	ISL yes in Call 2
BMK_0005	Identifies angular object at short-end wall separately	ISL or BC yes in Call 2
BMK_0001	Mentions bridging material in trench at contact zone	ISL yes in Call 2
BMK_0009	Mentions widened/irregular trench base at junction	ISL yes in Call 2
If 4 of 5 pass → run full 15-case benchmark.
On the Empty Response Side Finding
The ~40% empty first-attempt rate and the BMK_0050/p2 persistent empty across 4 retries is worth flagging to the Alloy codebase owners separately. That failure pattern — no error, no content — suggests a content filtering or response validation layer in the Alloy routing that is silently dropping responses rather than returning an error. This is independent of the FN problem but could be masking additional failures in production at scale.
Immediate Recommended Actions
This week, in order:
Design the Call 1 free observation prompt — minimal, no JSON contract, image-first
Test on 5 FN cases, confirm signals surface in Call 1 output
Design Call 2 classification prompt — abbreviated rules, full JSON contract, consumes Call 1 output as context
Validate Call 2 produces correct classification from correct Call 1 observations
Check that BMK_0008 (only true particle GT) still correctly classifies as particle under the new structure
If 5-case validation passes, run full 15-case benchmark
Parallel track:
Report empty response issue to Alloy codebase owners with the retry data from the probe
Ask owners specifically whether image resizing or compression occurs before VLM submission — the perception gap between pipeline and probe may have an additional image quality component even if framing is the primary cause
The path forward is now much clearer than it was before the probe. Good diagnostic work.