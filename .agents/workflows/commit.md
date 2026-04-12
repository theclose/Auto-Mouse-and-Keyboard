---
description: Auto git commit with version bump after code changes
---
// turbo-all

# Auto Commit Workflow

Run this after making code changes to auto-bump version, run QA, and commit.

## Steps

1. Bump the patch version:
```
python scripts/bump_version.py patch
```

2. Run the full QA suite (tests + all lint checks):
```
python scripts/qa_check.py
```

3. Stage all changes:
```
git add -A
```

4. Check what will be committed:
```
git diff --cached --stat
```

5. Commit with a descriptive message. Replace `DESCRIPTION` with a summary of what changed:
```
git commit -m "vNEW_VERSION: DESCRIPTION"
```

> **Note**: Replace `NEW_VERSION` with the version output from step 1 (e.g. `1.0.1`), 
> and `DESCRIPTION` with a brief summary of changes made.
> The pre-commit hook will auto-run `qa_check.py --quick` before committing.

## For Minor/Major Bumps

- **New feature** (backwards-compatible): `python scripts/bump_version.py minor`
- **Breaking change**: `python scripts/bump_version.py major`

## Rollback

```bash
# See history
git log --oneline -10

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Full rollback to specific version
git checkout v1.0.0
```
