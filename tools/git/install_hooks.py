#!/usr/bin/env python3
"""Install the git hooks for this repo. Run once after cloning:

    python tools/git/install_hooks.py

- pre-commit and commit-msg: installed by the `pre-commit` tool (ruff, file checks, the
  Conventional commit message check, the contract freshness check).
- pre-push: a native hook that refuses a push to a protected branch (see refuse_push_to_main.py).
  It is not a pre-commit hook because pre-commit skips pre-push hooks when a push has no new
  commits, which is the case of pushing an already-pushed branch to main.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKER = "# installed by tools/git/install_hooks.py"

PRE_PUSH = f"""#!/bin/sh
{MARKER}
# Refuse a push to a protected branch. Git passes the pushed refs on stdin.
exec python3 "$(git rev-parse --show-toplevel)/tools/git/refuse_push_to_main.py"
"""


def hooks_dir(repo: Path) -> Path:
    path = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    return (repo / path).resolve()


def install_pre_push(repo: Path = REPO_ROOT) -> Path:
    target = hooks_dir(repo) / "pre-push"
    if target.exists() and MARKER not in target.read_text(encoding="utf-8"):
        raise SystemExit(f"{target} already exists and was not installed by this script; move it aside first.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(PRE_PUSH, encoding="utf-8")
    target.chmod(0o755)
    return target


def main() -> int:
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-commit", "--hook-type", "commit-msg"],
        cwd=REPO_ROOT,
        check=True,
    )
    print(f"installed {install_pre_push()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
