# Adjudication Worksheet (One Pager)

Date: 2026-08-02
Purpose: fast, consistent labeling of BF/DF benchmark pairs during HTML review.

## Use This While Reviewing Each Card

Primary input:
- BF image + DF image for one pair

Goal:
- Decide coarse class and blocked-etch evidence
- Flag uncertainty and escalation needs

## Key Term Definitions

### Comparator

Meaning:
- A similar, nearby structure in the same image (or BF/DF pair) used as a like-to-like reference.

Why it matters:
- BEEP-like calls depend on comparing a suspicious structure against another instance expected to have similar geometry.

Examples:
- Yes comparator: multiple repeated trenches with similar orientation and pitch are visible; one appears anomalous.
- Partial comparator: only edge-cropped or distant repeats are visible.
- No comparator: large obstruction or sparse pattern leaves no reliable like-to-like reference.

### Occlusion

Meaning:
- A large bright/dark object, artifact, or saturation region blocks visibility of underlying substrate/structure details needed for comparison.

Why it matters:
- Occlusion reduces confidence and can cause false blocked-etch conclusions if not accounted for.

Examples:
- Particle/deposit covers trench edges so trench continuity cannot be evaluated.
- Bloom/saturation hides line-end geometry in the candidate region.

### Confounder

Meaning:
- A visual pattern that can mimic or obscure true defect evidence, increasing misclassification risk.

Why it matters:
- Confounders should lower certainty or trigger review, not be treated as direct blocked-etch evidence by default.

Examples:
- Offset surface lines on SiO near trench edges that resemble structure discontinuity.
- Nonuniform contrast bands or imaging artifacts that imitate morphology changes.
- Background pattern variation that looks like anomaly but is process-pattern normal for that context.

## Minimum Fields To Fill Per Row

Fill these every time:
1. adjudicated_by
2. adjudicated_at_utc
3. adjudication_status
4. adjudicated_coarse_class
5. adjudicated_blocked_etch_evidence
6. adjudicated_confidence
7. comparator_visible
8. occlusion_present
9. review_required_expected
10. notes_needed

Fill when relevant:
1. offset_surface_lines_present
2. sunken_residual_continuity_present
3. comparator_boundary_line_present
4. mult_particles_present
5. pre_etch_geometry_match (optional explicit geometry cue; often overlaps comparator_boundary_line_present)
6. evidence_coherence (optional override; default from adjudicated_confidence)
7. evidence_localization (optional override; usually inferred from signature flags)
8. particle_edge_morphology (optional morphology track)
9. particle_morphology_match_to_beep_like (optional morphology track)
10. failure_mode_primary (only if model output is wrong/risky)
11. failure_mode_secondary (optional)
12. notes_short (1 to 2 lines, only when notes_needed=yes)

## Quick Value Guide

### adjudication_status
- complete: enough evidence to decide
- needs_second_review: ambiguous/high-impact disagreement
- deferred: not enough image/context quality to decide

### adjudicated_coarse_class
- particle: no convincing blocked-etch signature
- possible_beep: convincing blocked-etch behavior
- indeterminate: evidence insufficient or conflicting

### adjudicated_blocked_etch_evidence
- none: no blocked-etch signs
- weak: suggestive but not stable
- moderate: multiple aligned cues with comparators
- strong: clear blocked-etch signature with convincing comparators

### adjudicated_confidence
- low: uncertain, should likely escalate
- medium: usable but uncertain
- high: strong visual evidence and coherent comparator logic

## BEEP Evidence Signatures (Named Modes)

Named visual patterns that constitute blocked-etch evidence. Multiple signatures on one pair increase confidence. Cite these by name in notes_short when applicable.

### inset_surface_lines
Material lying on the top level of the SiO substrate shows edge lines slightly inset from the expected SiO bridge or trench boundary, indicating the etch boundary shifted relative to the substrate edge. Evidence appears at the surface, not inside the comparator.

### sunken_residual_continuity
Material is visible on the top level of the SiO substrate outside the comparator interior. Within the comparator, the material appears largely absent at that top level (etched away), but a residual deposit is visible sunken into the interior of the comparator structure. The sunken material shows altered contrast relative to the top-level material, bears a line that matches the expected comparator boundary, and continues the morphological shape of the surface defect into the structure interior. Indicates etch was blocked at surface, leaving partially trapped material inside the comparator at a recessed depth.

### comparator_boundary_line
A sharp contrast transition within the material coincides spatially with the expected boundary of a comparator. The material appears to be conforming to an etch stop at that boundary rather than terminating naturally. May co-occur with sunken_residual_continuity at the same comparator edge.

Notes on usage:
- inset_surface_lines and comparator_boundary_line can appear independently or together.
- sunken_residual_continuity typically presents alongside comparator_boundary_line at the same comparator.
- Multiple named signatures on one pair => blocked_etch_evidence = strong is appropriate.
- Single ambiguous signature alone => moderate or weak.

### comparator_visible
- yes: one or more impacted structures have a strong, like-to-like comparator with sufficient visible geometry for boundary/shape checks.
- partial: comparator support is mixed or degraded. Use partial when any of the following applies:
	- at least one impacted structure has a likely comparator but another impacted structure does not
	- comparator is present but only a small remnant of the impacted structure remains (for example deep extension into the structure), limiting confirmation quality
	- nearest comparator exists but is only a partial geometric match (for example impacted trench is partial-image-height while comparator trench is full-image-height)
	- comparators are visible only indirectly or with limited fidelity due to crop/sparsity
- no: no reliable comparator for impacted structures, and no defensible nearest-structure fallback.

Comparator decision rule:
- If structures are impacted: adjudicate comparator visibility from impacted structures first.
- If structures are not impacted: adjudicate from the nearest structure to the material defect.

Occlusion interaction:
- occlusion_present and comparator_visible are separate axes.
- Occlusion can lower confidence of comparator assessment, but does not automatically force comparator_visible=partial/no.

### occlusion_present
- yes: large object/brightness obscures substrate context
- no: substrate context remains visible

### review_required_expected
- yes: should escalate in production workflow
- no: stable enough for automated pass-through

### pre_etch_geometry_match (optional)
- yes: explicit geometry-match cue is present (shared flat edge, corner notch/chip, or boundary-conforming profile)
- no: explicit geometry-match cue is not present
- unclear: visibility or comparator quality insufficient
- note: often redundant with comparator_boundary_line_present; use only when it adds clarity

### evidence_coherence (optional)
- high: cues agree on one interpretation
- medium: mixed cues but one interpretation still favored
- low: cues conflict or are too weak
- note: usually inferred from adjudicated_confidence

### evidence_localization (optional)
- surface: evidence primarily on SiO surface level
- interior: evidence primarily recessed/inside comparator structure
- both: coherent evidence on both surface and interior
- unclear: location signal uncertain
- note: usually inferred from offset_surface_lines_present and sunken_residual_continuity_present

### notes_needed
- yes: low confidence, deferred/second-review, contradictory cues, or novel morphology
- no: structured fields are sufficient

## Fast Decision Sequence (Per Pair)

1. Check comparator availability
- If no comparators, bias toward indeterminate unless evidence is very strong.
- Use impacted-structure-first logic; if not impacted, use nearest-structure fallback.
- Use partial when comparator support is mixed across impacted structures.

2. Check occlusion/confounders
- If occlusion or offset surface lines dominate, reduce certainty.

3. Make coarse class call
- particle vs possible_beep vs indeterminate.

4. Set blocked-etch evidence strength
- none/weak/moderate/strong.

5. Set confidence + review_required_expected + notes_needed
- low or medium confidence usually implies review_required_expected=yes.
- if low confidence or ambiguity, set notes_needed=yes and add 1 to 2 lines.

## Failure Taxonomy (When Model Misses)

Pick one primary mode:
- substrate_orientation_error
- structure_scale_error
- blocked_etch_overcall
- blocked_etch_undercall
- occlusion_not_handled
- confounder_not_handled
- insufficient_evidence_but_forced_class
- other

## Practical Defaults

When uncertain:
- adjudicated_coarse_class=indeterminate
- adjudicated_confidence=low
- review_required_expected=yes

Keep notes short and concrete:
- mention one visible comparator cue or one blocking limitation.
- if notes_needed=no, notes_short may be left blank.

## Shorthand Codebook (Fast Entry)

Use these short forms while typing quickly, then normalize to canonical values before final publish.

### adjudication_status
- c = complete
- r = needs_second_review
- d = deferred

### adjudicated_coarse_class
- p = particle
- b = possible_beep
- i = indeterminate

### adjudicated_blocked_etch_evidence
- n = none
- w = weak
- m = moderate
- s = strong

### adjudicated_confidence
- l = low
- m = medium
- h = high

### comparator_visible
- y = yes
- p = partial
- n = no

### occlusion_present
- y = yes
- n = no

### offset_surface_lines_present
- y = yes
- n = no

### sunken_residual_continuity_present
- y = yes
- n = no

### comparator_boundary_line_present
- y = yes
- n = no

### mult_particles_present
- y = yes
- n = no

### pre_etch_geometry_match
- y = yes
- n = no
- u = unclear

Use only when needed; comparator_boundary_line_present is usually sufficient.

### evidence_coherence
- h = high
- m = medium
- l = low

Usually inferred from adjudicated_confidence.

### evidence_localization
- s = surface
- i = interior
- b = both
- u = unclear

Usually inferred from offset_surface_lines_present and sunken_residual_continuity_present.

### notes_needed
- y = yes
- n = no

### particle_edge_morphology (optional)
- r = rounded
- f = flat
- c = notched_or_chipped
- i = irregular
- m = mixed
- u = unclear

### particle_morphology_match_to_beep_like (optional)
- y = yes
- n = no
- u = unclear

### review_required_expected
- y = yes
- n = no

Guardrails:
- Keep shorthand to enumerated fields only.
- Keep notes_short in plain words, not single letters.
- If any code could be ambiguous, expand it immediately in the row.
- Use morphology fields only when pattern is visible; otherwise use u/blank.
