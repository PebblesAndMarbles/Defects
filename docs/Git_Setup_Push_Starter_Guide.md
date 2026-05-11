# Git Setup and Push Starter Guide (Windows, Network + Local Folders)

Purpose: reusable quick-start to create a new GitHub repo from any project folder, including UNC network paths.

## 1. Pre-checks

1. Open PowerShell in the target project folder.
2. Confirm Git is available:

    git --version

3. Confirm the current folder:

    Get-Location

4. Optional: size scan before first commit (recommended):

    Get-ChildItem -Recurse -File | Sort-Object Length -Descending | Select-Object -First 20 FullName,@{N='SizeMB';E={[math]::Round($_.Length/1MB,2)}}

Guideline:
- Keep generated/bulky files out of the first commit.
- Avoid tracking files above 50 MB in normal Git repos.

## 2. Initialize Git in the Folder

Run in the project root:

    git init
    git branch -M main

## 3. If Folder Is on a Network Share (UNC) and Git Blocks Access

If you see a dubious ownership error, trust that exact path once:

    git config --global --add safe.directory "//server/share/path/to/project"

Then retry:

    git status

## 4. Create a New Remote Repository on GitHub

1. Go to https://github.com/PebblesAndMarbles and click the "+" (New) button or visit https://github.com/new
2. Set the repository name to:

    BE AME Inline and Station Monitor Defects

3. (Optional) Add a description, set visibility (private/public), and DO NOT initialize with a README, .gitignore, or license (these are already in your local folder).
4. Click "Create repository".

## 5. Add the Remote and Push

In your project folder, run (replace USERNAME if needed):

    git remote add origin https://github.com/PebblesAndMarbles/BE-AME-Inline-and-Station-Monitor-Defects.git
    git branch -M master
    git push -u origin master

If prompted for credentials, use your GitHub username and a personal access token (not your password).

## 6. Exclude Images and Large Files

- The `.gitignore` is set to exclude the `images/` folder and common large file types.
- Manifest and artifact JSON files are included by default.
- To check what will be pushed:

      git status
      git diff --cached

## 7. Troubleshooting

- If you see errors about file size, add the file pattern to `.gitignore` and retry.
- If you see authentication errors, check your GitHub token or SSH key setup.
- For network path issues, see section 3 above.

## 8. First Commit

Stage intentionally (preferred), then commit:

    git add .
    git status --short
    git commit -m "Initial repo baseline"

Tip: if you want a code-docs-only first commit, stage by extension or folder instead of using git add .

## 9. Create GitHub Repo and Connect Remote

Create an empty repo on GitHub first (no README/.gitignore/license), then add remote:

    git remote add origin https://github.com/<owner>/<repo>.git
    git remote -v

If origin already exists and needs replacement:

    git remote remove origin
    git remote add origin https://github.com/<owner>/<repo>.git

## 10. First Push

    git push -u origin main

## 11. Regular Update Flow

Use this sequence for daily/weekly sync:

    git status --short
    git add .
    git commit -m "Update <what changed>"
    git push

If there are no changes, Git will tell you nothing to commit.

## 12. Recommended Optional Automation Script

Create scripts/backup_push.ps1 with this shape:

    param(
        [string]$Message = "Backup sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    )

    git add .
    $staged = git diff --cached --name-only
    if (-not $staged) {
        Write-Host "No staged changes to commit."
        exit 0
    }

    git commit -m $Message
    git push

Run it with:

    powershell -ExecutionPolicy Bypass -File .\scripts\backup_push.ps1

## 13. Common Errors and Fast Fixes

1. Remote not found
- Cause: using profile URL instead of repo URL.
- Fix: use https://github.com/<owner>/<repo>.git

2. Authentication failed
- Cause: expired credentials or missing GitHub auth setup.
- Fix:
  - Sign in via Git Credential Manager prompt when pushing.
  - Or refresh stored credentials in Windows Credential Manager.

3. Rejected non-fast-forward
- Cause: remote has new commits not in local.
- Fix:

    git pull --rebase origin main
    git push

4. Large file rejected
- Cause: committing generated or bulky files.
- Fix:
  - Add/adjust .gitignore.
  - Remove file from index (keep local copy):

    git rm --cached <path/to/file>
    git commit -m "Stop tracking large generated file"
    git push

## 14. Portable Checklist (Copy for Any New Folder)

1. Open folder in PowerShell.
2. git init and set main.
3. Add safe.directory for UNC path if required.
4. Add .gitignore before first commit.
5. Commit baseline.
6. Create empty GitHub repo.
7. Add origin and push.
8. Use regular backup flow for ongoing sync.
