# Scheduler + GitHub Push POC (Independent Runbook)

## Goal

Document a safe proof-of-concept for scheduled GitHub backups using the same thin-launcher pattern as existing daily jobs.

This POC is for another process and is explicit opt-in only.

## Existing Scheduler Pattern in This Workspace

Current daily jobs use a small launcher script and keep business logic in a separate module.

Reference pattern:

- `BE_QUERY_FILES/surf_scan_daily.py` launches `surf_scan_update.main(...)`
- scheduler invokes Python with an absolute interpreter path and absolute script path

Example existing style:

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\surf_scan_daily.py"
```

## POC Backup Launcher

POC launcher file:

- `BE_QUERY_FILES/csv_backup_daily.py`

What it does:

1. validates git repository access
2. stages only files matched by explicit `--include` globs
3. commits only if staged changes exist
4. pushes current branch to origin
5. exits without action if no include globs are provided

Important:

- There are no default backup targets.
- This prevents accidental backup of any CSVs during POC.

## Example POC Command (Dry Operational Scope)

Choose paths for your other process only.

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\csv_backup_daily.py" --include "<other-process-folder>/*.csv" --message-prefix "other-process-csv-backup"
```

Example with multiple patterns:

```powershell
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\csv_backup_daily.py" --include "<other-process-folder>/*.csv" --include "<other-process-folder>/manifests/*.json" --message-prefix "other-process-backup"
```

## Scheduler Implementation Notes (Roaming Bot Service)

Use same conventions as existing daily jobs:

1. fixed interpreter path
2. fixed script path
3. fixed cadence (for example hourly or daily)
4. logs captured by scheduler platform

Recommended POC cadence:

- start with once per day
- move to higher frequency only after confirming commit volume is acceptable

## Credential and Access Requirements

For non-interactive scheduled push:

1. repo remote must exist and be reachable
2. roaming bot identity must have GitHub push permission
3. credentials must be pre-provisioned (Git Credential Manager or token/SSH route)

If push fails with repository not found:

1. validate remote URL
2. validate repo exists
3. validate identity has access (private repos return 404 when unauthorized)

## Safety Guardrails

1. Keep image folders and bulky binaries excluded from git tracking.
2. Use explicit include globs only for the process being protected.
3. Use isolated commit prefix so backup commits are easy to filter.
4. Consider a second remote for internal redundancy if GitHub is unavailable.

## Quick Validation Sequence

Run manually before scheduling:

```powershell
git remote -v
git branch --show-current
& "c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe" "\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\BE_QUERY_FILES\csv_backup_daily.py" --include "<other-process-folder>/*.csv" --message-prefix "poc-backup"
git status -sb
```

Success criteria:

1. no-op when no matching changes exist
2. commit created only on data change
3. push succeeds to origin on scheduler identity
