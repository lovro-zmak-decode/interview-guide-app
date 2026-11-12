---
id: global-branching
title: Branch before touching any file, and never commit to main
scope: [global]
impact: CRITICAL
triggers: [branch, git checkout, start work, new task, commit to main, push to main]
appliesTo: []
---

Never edit, commit or push on `{{protectedBranches}}`. Create and switch to a branch before
the first file change, not at commit time. This holds even when the request is only
"commit" or "commit and push": switch to a new branch first.

**Branch name format:** `{{branchFormat}}`

- `type` is one of `{{branchTypes}}`.
- The slug is short, lowercase and hyphenated: `feat/own-questions`,
  `fix/health-check-redirect`, `chore/dev-harness`.
- The branch must not already exist on the remote. If it does, append an integer:
  `feat/own-questions-2`.

**Do:**

```bash
git branch --show-current            # if this prints main, stop and branch first
git checkout -b fix/health-check-redirect
```

**Never:**

```bash
# editing files while `git branch --show-current` prints `main`
# committing to main, or `git push origin HEAD:main`
```

If you discover you already edited files on `main`, run `git checkout -b <branch>`
immediately (uncommitted changes follow you) before staging anything.

**The `pre-push` hook backstops this** (installed by `python tools/git/install_hooks.py`). It refuses any push whose **remote** ref is
`refs/heads/main`, at any remote, which also catches `git push origin HEAD:main` and
`git push origin my-branch:main`. It is a backstop, not protection: hooks can be skipped
with `--no-verify`, and `main` is not yet protected on GitHub. Emergency bypass, for
repairing `main` after an accident:

```bash
ALLOW_PUSH_TO_MAIN=1 git push ...
```

Source: [ADR 0014](../../../docs/adr/0014-never-commit-to-main-and-enforce-it-with-a-pre-push-hook.md)
