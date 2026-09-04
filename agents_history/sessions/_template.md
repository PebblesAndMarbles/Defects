---
session_id: YYYY-MM-DD_NNN
title: Short Descriptive Title
date: YYYY-MM-DD
time_start: HH:MM
time_end: HH:MM
agent: GitHub Copilot
model: Claude Sonnet 4.6 (or whatever is shown in Copilot)
triggered_by: manual-checkpoint
status: partial | complete | abandoned | blocked
original_goal: One sentence description of what you sat down to do
# retroactive: true          # uncomment if logging after the fact
# logged_date: YYYY-MM-DD   # uncomment if retroactive — date the log was written
---

## Original Goal
Expand on the one-liner above.  What was the entry condition?
What did you expect to be straightforward?

## Completed Tasks
- [x] Task that got done
- [x] Another completed task
- [ ] Task that was started but not finished

## Files Modified
| File | Change Type | Notes |
|------|-------------|-------|
| `relative\path\to\file.ext` | Created / Modified / Deleted | Brief note |

## Files Affected (referenced but not modified)
| File | Reason Referenced | Action Needed? |
|------|-------------------|----------------|
| `relative\path\to\file.ext` | Why it came up | Yes / No |

## Bugs Encountered
### BUG-001: Short bug title
- **Status:** Resolved / Unresolved / Deferred
- **File(s):** `path\to\file.ext`
- **Root Cause:** What caused it
- **Fix Applied:** What was done, or blank if deferred
- **Notes:** Anything a future agent needs to know

## Excursions / Scope Creep Discovered
- Item that came up but was out of scope for this session
- Another rabbit hole that was noted but not pursued

## Open Threads
- [ ] Thing that still needs doing
- [ ] Known issue deferred to future session
- [ ] Dependency on something external

## Key Decisions Made
- Decision and brief rationale
- What was explicitly rejected and why (important for future agents)

## Recommended Re-Entry
**Load these files for context:**
- `relative\path\to\file1.ext`
- `relative\path\to\file2.ext`

**Suggested starting prompt:**
> "Paste a ready-to-go prompt here so a future agent
> can pick up exactly where this left off"

## Notes for Future Agent
Free text.  Anything that would have helped YOU at the start
of this session that isn't captured above.  Gotchas, assumptions,
things that look wrong but are intentional.
