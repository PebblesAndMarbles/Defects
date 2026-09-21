## Plan: Multi-commit push handoff

TL;DR: Split the current dirty tree into the 7 logical commit batches described in `HANDOFF_GIT_PUSH.md`, verify each commit boundary with `git show --stat HEAD`, keep the tree clean between batches, and stop before any push until the review gate is explicitly cleared. Preserve the current scope boundaries: do not expand beyond the handoff, do not rewrite pushed history, and do not auto-include deferred scratch artifacts.

**Steps**
1. Baseline the current working tree and compare it against the handoff list.
   - Confirm which of the handoff files are still dirty, renamed, or newly untracked.
   - Separate durable work from scratch artifacts before staging anything.
   - Resolve any mismatches between the handoff and live `git status` so the commit plan reflects current reality.

2. Build Commit 1: Alloy_Class generic-description v9 pipeline and probe archive.
   - Use the literal `git add` file list under Commit 1 in `HANDOFF_GIT_PUSH.md` (not a reconstruction from memory) -- it includes `images/Alloy_Class/VLM_Overhaul.md` by name alongside the v9 probe, chunked runner, consolidation, enrichment, HTML report, tranche builder, and prompt configs.
   - Keep the already-staged v1-v8 probe renames in the same commit.
   - Leave `images/Alloy_Class/400pairdebug.txt` out unless the user explicitly approves it.

3. Build Commit 2: BOST accumulating-history pipeline and retire superseded scripts.
   - Stage the new accumulating-history builder, registry plan, pilot outputs, gate-rollout script, and BOST2/archive/registry/doc updates.
   - Include the superseded-file deletions only after confirming they are truly obsolete per the prior BOST checkpoint history.
   - Do not silently absorb any unrelated BOST scratch exports.

4. Build Commit 3: WDS APEX_ENTITY enrichment module.
   - Stage the `WDS/` tree plus `dev/wds-decoder-cache/`.
   - Verify no ignored proprietary carve-outs are accidentally staged.
   - Keep the commit narrowly scoped to the APEX_ENTITY enrichment work already referenced by the handoff.

5. Build Commit 4: BE_QUERY_FILES routine data refresh.
   - Stage the refreshed NCDD/reclass CSVs, the new HVF JSL, the surf_scan daily script, and the merged-source outputs listed in the handoff.
   - Ask before adding `BE_QUERY_FILES/SUBSET_SUBSET_SS_EDX_STACKED By (INSPECTION_TIME, PRIMARY_EQUIP).csv`; treat it as scratch unless the user says otherwise.

6. Build Commit 5: html/ and surf-scan reporting updates.
   - Stage the inline/SS HTML report scripts, surf-scan design doc updates, Biv report script/debug output, docs/FLEET.txt, and the listed run artifacts.
   - Keep the change set focused on reporting and artifact refreshes, not on broader pipeline rewrites.

7. Build Commit 6: agents_history backlog and saved planning prompts.
   - Add the listed retroactive session logs, update `agents_history/index.md`, `agents_history/file_map.md`, and `agents_history/open_threads.md`, and add the `.github/prompts/` material.
   - Check the duplicate BOST session-log filenames first; if they are byte-for-byte duplicates, follow the established precedent and keep only the canonical one referenced by the index.
   - Keep the logging update atomic so index, open threads, and file map stay consistent.

8. Build Commit 7: repo hygiene.
   - Stage `.gitignore`, `USEFUL_COMMANDS.txt`, and `HANDOFF_GIT_PUSH.md` (the handoff doc itself is currently untracked and has no other home in this sequence).
   - Confirm this commit only captures hygiene/documentation and not any payload work.

9. Run the stop-and-review gate after Commit 7.
   - Verify the final history with `git log --oneline -8` and the tree state with `git status --short`.
   - Report any deferred or intentionally omitted items back to the user.
   - Wait for explicit approval before any `git push origin master`.

**Relevant files**
- `HANDOFF_GIT_PUSH.md` — source of the proposed commit sequence and review gate.
- `images/Alloy_Class/VLM_Overhaul.md` — higher-level Alloy_Class scope anchor for the generic-description and enrichment work.
- `agents_history/index.md` — session and thread registry that must stay consistent with any logging commits.
- `agents_history/open_threads.md` — deferred/open issue tracking, especially the duplicate-log and scratch-artifact decisions.
- `agents_history/file_map.md` — file traceability map that must be updated in the same operation as any new session log.

**Verification**
1. After each commit, run `git show --stat HEAD` and review the boundary before moving on.
2. After Commit 3, run the WDS-specific `git status --short` check from the handoff to ensure no ignored proprietary carve-outs were staged.
3. After Commit 7, run `git log --oneline -8` and `git status --short` to confirm the tree is clean except for any explicitly deferred items.
4. If any handoff file is already clean or missing, re-derive the live status instead of forcing the stale grouping.

**Decisions**
- Scope is limited to the seven commit batches already described in the handoff; no extra reorganization or new feature work is included.
- The push is gated and must not happen until the user explicitly approves after the final review pass.
- `images/Alloy_Class/400pairdebug.txt`, the `SUBSET_SUBSET` CSV, and the duplicate BOST session log are treated as deferred decisions, not auto-committed payload.
- The plan assumes the BOST deletions are still valid supersessions, but that assumption must be checked against the current tree before staging.
- `OLD/` is globally gitignored (unanchored rule in `.gitignore`); already-tracked files renamed into an `OLD/` folder stay tracked (confirmed for the v1-v8 renames), but any new untracked file added under an `OLD/` path will be silently skipped by plain `git add` -- do not add new files under any `OLD/` directory in this pass.
- `images/Alloy_Class/docs/OLD/` already has local content but none of it is tracked in git (`git ls-files` returns nothing for that path). Do not attempt to fix or track this in this pass -- report it back to the user as a separate, unresolved decision.

**Further Considerations**
1. If the live tree differs materially from the handoff, should the commit grouping be rebalanced to keep the commits reviewable, or should the original batch boundaries be preserved as closely as possible?
2. If the duplicate BOST session log is not a byte-for-byte duplicate, should both be retained and documented, or should one be replaced by a consolidated log?
3. For the deferred scratch artifacts, do you want them deleted, kept untracked, or promoted into a tracked cleanup commit later?