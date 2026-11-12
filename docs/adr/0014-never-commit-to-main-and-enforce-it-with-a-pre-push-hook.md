# 0014. Never commit to main, and enforce it with a native pre-push hook

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | - |
| Supersedes | - |

## Context

Earlier changes were committed and pushed straight to `main`, which made a pull request
impossible for them and had to be corrected afterwards. `main` is not protected on GitHub. The
rule "never commit to main" lived only in instructions.

## Decision

All work happens on a branch (`{type}/{short-slug}`) and reaches `main` through a pull request.
A `pre-push` git hook refuses any push whose **remote** ref is `main`, so it also catches
`git push origin HEAD:main` and `git push origin my-branch:main`. `ALLOW_PUSH_TO_MAIN=1` is the
emergency bypass.

The hook is a native git hook installed by `python tools/git/install_hooks.py`, not a pre-commit
hook. pre-commit skips its pre-push hooks when a push contains no new commits, and pushing an
already-pushed branch to `main` is exactly that case. This was found by testing, and the
tests now cover it.

## Consequences

- A slip is stopped on the developer's machine, with the recovery steps printed.
- Hooks can be skipped with `--no-verify`, and nothing server-side backs them up until branch
  protection is enabled on GitHub.
- Each developer must run the installer once after cloning.
