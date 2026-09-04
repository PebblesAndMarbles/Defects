# Checkpoint Prompt
Copy and paste the block below into Copilot chat when you want to log a session.

---

```
Please generate a session log for our conversation using the template at:
agents_history\sessions\_template.md

Use the following guidelines:
- session_id: use the date this session STARTED (not today if logging retroactively) and next available sequence number from agents_history\index.md
- Be specific about file paths relative to the workspace root
- List ALL files we looked at, not just ones we changed
- For any bug we hit, note whether it is resolved or still open
- For open threads, write a re-entry prompt I could paste into a future session
- Note any decisions we made explicitly, including things we decided NOT to do
- Flag anything that looked wrong but was intentional so a future agent doesn't undo it
- After saving the log, update agents_history\file_map.md for every file in Files Modified and Files Affected

Output the completed log as a markdown code block so I can copy it directly
into a new file in agents_history\sessions\
```
