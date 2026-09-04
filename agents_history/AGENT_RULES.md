# Agent Rules for BE Defects Workspace

**Workspace Root:**
`\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE`

**Last Updated:** 2026-08-07 (template v1.0)

---

## Purpose of This File
This file defines the operating rules, orientation steps, and slash command
conventions for any GitHub Copilot agent working in this workspace.

Every new session should begin by reading this file and confirming
the rules before any work begins.

---

## Logging System Overview

This workspace uses a structured session logging system located in:
`agents_history\`

| File | Purpose |
|------|---------|
| `agents_history\sessions\_template.md` | Template for individual session logs |
| `agents_history\index.md` | Master index of all sessions |
| `agents_history\file_map.md` | Which sessions touched which files |
| `agents_history\open_threads.md` | Master list of unresolved issues |
| `agents_history\checkpoint_prompt.md` | Reference for generating session logs |

---

## Session Goal

The purpose of this logging system is to ensure that all Copilot sessions
in this workspace are documented in a structured, searchable way so that:

- Any file can be traced back to the session in which it was modified and why
- Bugs encountered are recorded whether resolved or deferred
- Open threads are tracked and do not get lost between sessions
- Any future agent can re-enter a prior conversation with enough context
  to continue without re-reading full chat history
- The most relevant prior session can be identified when a file needs
  to be revisited or modified again

---

## Orientation Steps (Run at Start of Every New Session)

Complete these steps in order and report back on each one before
proceeding to the next.  Do not begin any work tasks until orientation
is complete.

### STEP 1: Read the Logging System Files
Read each file listed in the Logging System Overview table above.
Confirm you have read each one and give a one-sentence summary of
what each file is for.

### STEP 2: Orient to the Workspace
Survey the workspace and report:

1. Top-level folder structure to a depth of 2-3 levels
2. File types present with rough count of each
3. Any existing README, config, or documentation files -
   list them with a one-sentence description each
4. Whether a git repository exists - if yes, what is the most
   recent commit message
5. Any files or folders that already serve a logging, tracking,
   or documentation purpose even informally -
   e.g. notes.txt, changelogs, todo lists, commented headers in scripts

### STEP 3: Assess Fit
Based on Steps 1 and 2, report:

1. Does the agents_history folder and its templates already exist,
   or do they need to be created?
2. Are there existing documentation or tracking conventions that the
   logging system should be consistent with or absorb?
3. Are there files that appear recently modified or in an incomplete
   or in-progress state?  Flag these - they are likely candidates
   for the first real session log entry.
4. What kind of project does this appear to be?
   Give a 2-3 sentence characterization based on file types and structure.

### STEP 4: Propose a Setup or Continuation Plan
Based on everything above, propose a concrete numbered plan.
For each step state:

- What you will do
- Which files will be created or modified
- Whether you need any input before proceeding

**Do not execute any steps yet.  Propose the plan and wait for approval.**

---

## Ground Rules

These rules apply for the entire duration of every session.

1. **Ask before modifying.**
   Do not modify any file without first stating which file, what change,
   and why.

2. **Stop and report unexpected findings.**
   If you discover something unexpected during a task, stop and report it
   before continuing.  Do not silently work around it.

3. **Check the file map before touching tracked files.**
   If a task requires modifying a file that appears in
   `agents_history\file_map.md`, check the file map first and report
   when that file was last modified and in which session.

4. **Respect deferred decisions.**
   If a file or pattern looks wrong but is flagged as intentional in a
   prior session log, do not change it without asking first.

5. **No silent assumptions.**
   If something is ambiguous, ask.  Do not assume and proceed.

6. **Thread index entry and body entry are one atomic operation.**
   When opening a new thread, write both the row in `agents_history\index.md`
   AND the full body entry in `agents_history\open_threads.md` in the same
   operation.  Never create a thread ID in one file without immediately
   creating the matching entry in the other.

7. **Do not create checkpoint-only session logs for sessions with no work.**
   A session that produced zero code changes, zero decisions, and zero new
   threads does not need a full session log file.  If a `/checkpoint` is
   requested in such a session, output the log as a code block for review
   but ask the user whether to save it.  Do not auto-create a new session
   log and index entry just because `/checkpoint` was called.

   **Corollary — no-context checkpoint:**
   If `/checkpoint` is called and the agent has no conversation history
   to draw from (e.g., invoked fresh in a new chat), it MUST stop and ask:
   > "I don't have context for what work was done in this session.
   >  Please describe the files changed, decisions made, and any bugs
   >  encountered, and I will generate a meaningful log."
   Never generate a log whose Files Modified section contains only
   `agents_history\` files — that is a sign the log has no real content.

   **Retroactive logging workflow (for old or cross-session checkpoints):**
   If the session being logged is old or the conversation history is not
   visible (due to context window truncation or cross-session invocation),
   ask the user to provide one of:
   - A saved session text file (e.g. `.github\agents\debug\session_text.txt`)
     which can be attached with `@file:` and read directly
   - A brief written summary of: files changed, decisions made, bugs hit
   Then generate the log from that supplied content rather than from
   conversation history.  Add `retroactive: true` and `logged_date: YYYY-MM-DD`
   to the frontmatter and use the actual session start date as `date:`.

8. **Do not use "all carried" shorthand in the index.**
   The Open Threads column in the Session Log table must list specific
   relevant thread IDs (e.g., `THREAD-003, THREAD-007`).  Never write
   "THREAD-001 through THREAD-NNN (all carried)" — this loses all signal
   about which threads were actually active in a given session.

9. **File map must be updated in the same operation as the session log.**
   After writing or saving a session log, immediately update
   `agents_history\file_map.md` for every file listed in the Files Modified
   AND Files Affected tables of that log.  Do not defer this step.
   A session log whose files are absent from `file_map.md` is incomplete.
   The file map is the only cross-session traceability record — if it
   falls behind, future agents cannot find prior work on a given file.

---

## Slash Commands

These commands can be issued at any point during a session.

| Command | What the Agent Should Do |
|---------|--------------------------|
| `/checkpoint` | Generate a completed session log using the template at `agents_history\sessions\_template.md` covering everything done so far in this conversation. Output as a markdown code block ready to save as a new file in `agents_history\sessions\` |
| `/status` | Give a brief bullet summary of what has been accomplished so far this session and what is still pending |
| `/open-threads` | List all unresolved issues or deferred items encountered so far this session |
| `/file-map` | List all files modified or referenced so far this session in file map table format |
| `/plan` | Restate the current proposed plan and which steps are complete, in progress, or pending |

---

## Session Close Rule

If a session ends without `/checkpoint` being called, the agent should
remind the user before the chat is closed that no session log has been
generated and offer to generate one immediately.

---

## Session ID Convention

Session IDs follow this format:
```
YYYY-MM-DD_NNN
```
Where NNN is a zero-padded sequence number starting at 001,
incrementing per session per day.

Example: `2026-08-06_001`

Session log files are named:
```
YYYY-MM-DD_NNN_short-descriptive-title.md
```

Example: `2026-08-06_001_logging-system-setup.md`

### Session Date Rules (IMPORTANT — read before assigning any session ID)

**Rule 1: Session date = date the chat was started, not the date the log is written.**
If a session was started on July 26 and the log is being written on August 7,
the session ID must be `2026-07-26_NNN`, not today's date.
Never use today's date as a substitute for the actual session start date.

**Rule 2: When the start date is unknown, ask the user before assigning an ID.**
Do not guess or default to today's date.  Ask:
> "What date did this session start, or approximately when was this work done?"

**Rule 3: Retroactive logs must be labeled in the frontmatter.**
If a log is being written after the fact (the chat is no longer active or the work
happened in a prior conversation), add this field to the YAML frontmatter:
```
retroactive: true
logged_date: YYYY-MM-DD
```
`logged_date` is the date the log was actually written.
`date` (the standard field) must still reflect the original session start date.

**Rule 4: Sequence numbers must not collide.**
Before assigning NNN for a given date, read `agents_history\index.md` and find the
highest existing NNN for that date.  Increment by one.  Never assume 001 is free.

---

## Thread Numbering Rules (IMPORTANT — read before opening any new thread)

**Rule 1: Thread numbers are global and permanent.**
Thread IDs (THREAD-NNN) are never reused, renumbered, or reassigned once written.
A thread number belongs to exactly one issue for the lifetime of the project.

**Rule 2: Before opening a new thread, check BOTH files.**
Read `agents_history\open_threads.md` AND `agents_history\index.md` to find the
highest existing thread number across both files.  The next thread is that number + 1.
Do not rely on one file alone — they may be temporarily out of sync.

**Rule 3: When adding a retroactive log, do not backfill thread numbers.**
Retroactive threads must receive the next available number at the time of logging,
not a number that fits chronologically.  A thread opened on July 26 but logged
on August 7 gets the next number after whatever exists on August 7.

**Rule 4: Report any numbering conflict immediately.**
If two threads claim the same number in index.md vs open_threads.md, stop and
report the conflict before writing any new threads.  Do not silently pick one.

---

## Notes for All Agents

- All file paths in session logs should be relative to the workspace root
- Use backslashes in all paths (Windows environment)
- Do not repeat the full workspace root path inside session logs — use relative paths only
- The current date provided in context is the date the log is being WRITTEN,
  not necessarily the date the session started.  Always apply Session Date Rule 1
  before using that date in a session ID.
