#!/usr/bin/env python3
"""pre-push backstop: refuse any push whose REMOTE ref is a protected branch.

Run as a native git `pre-push` hook (installed by tools/git/install_hooks.py). Git feeds it one
"<local ref> <local sha> <remote ref> <remote sha>" line per pushed ref on stdin. Matching the
remote ref rather than the current branch is what catches `git push origin HEAD:main` and
`git push origin my-branch:main`, which land on main while `git branch --show-current` prints
something else.

This is deliberately not a pre-commit hook: pre-commit skips its pre-push hooks when the push
carries no new commits, which is exactly the case of pushing an already-pushed branch to main.

A backstop, not protection: hooks can be skipped with --no-verify.
Emergency bypass, for repairing main after an accident:  ALLOW_PUSH_TO_MAIN=1 git push ...
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def protected_refs() -> set[str]:
    config = json.loads((REPO_ROOT / ".contract" / "project.config.json").read_text(encoding="utf-8"))
    return {f"refs/heads/{name}" for name in config["protectedBranches"]}


def pushed_remote_refs(stdin_lines: list[str]) -> list[str]:
    return [parts[2] for parts in (line.split() for line in stdin_lines) if len(parts) >= 3]


def main() -> int:
    if os.environ.get("ALLOW_PUSH_TO_MAIN") == "1":
        print("ALLOW_PUSH_TO_MAIN=1 set; skipping the protected-branch backstop.")
        return 0

    blocked = [ref for ref in pushed_remote_refs(sys.stdin.read().splitlines()) if ref in protected_refs()]
    if not blocked:
        return 0

    name = blocked[0].removeprefix("refs/heads/")
    print(f"Refusing to push to {name}.\n", file=sys.stderr)
    print("  Open a PR instead:", file=sys.stderr)
    print("    git checkout -b {type}/{short-slug}", file=sys.stderr)
    print("    git push -u origin HEAD\n", file=sys.stderr)
    print("  See .contract/rules/general/global-branching.md", file=sys.stderr)
    print("  Emergency bypass: ALLOW_PUSH_TO_MAIN=1 git push ...", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
