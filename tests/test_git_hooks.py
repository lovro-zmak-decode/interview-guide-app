"""The pre-push hook, exercised with real git in a scratch repository."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.git import install_hooks  # noqa: E402


def git(cwd, *args, **env):
    import os

    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **env}, check=False
    )


@pytest.fixture
def scratch(tmp_path):
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    git(tmp_path, "init", "--bare", "-q", str(remote))
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "Tester")
    git(work, "remote", "add", "origin", str(remote))
    for relative in ("tools/git/refuse_push_to_main.py", ".contract/project.config.json"):
        (work / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / relative, work / relative)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "initial")
    install_hooks.install_pre_push(work)
    git(work, "checkout", "-q", "-b", "feat/something")
    (work / "note.txt").write_text("x")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "note")
    return work


def test_pushing_a_branch_is_allowed(scratch):
    assert git(scratch, "push", "-q", "-u", "origin", "feat/something").returncode == 0


def test_pushing_to_main_is_refused(scratch):
    result = git(scratch, "push", "origin", "HEAD:main")
    assert result.returncode != 0
    assert "Refusing to push to main" in result.stderr


def test_pushing_an_already_pushed_branch_to_main_is_refused(scratch):
    """The case a pre-commit pre-push hook misses: no new commits are being pushed."""
    assert git(scratch, "push", "-q", "origin", "feat/something").returncode == 0
    result = git(scratch, "push", "origin", "feat/something:main")
    assert result.returncode != 0
    assert "Refusing to push to main" in result.stderr


def test_the_emergency_bypass_lets_a_push_through(scratch):
    assert git(scratch, "push", "-q", "origin", "HEAD:main", ALLOW_PUSH_TO_MAIN="1").returncode == 0


def test_installing_twice_is_fine_but_a_foreign_hook_is_not_overwritten(scratch):
    install_hooks.install_pre_push(scratch)
    hook = install_hooks.hooks_dir(scratch) / "pre-push"
    hook.write_text("#!/bin/sh\necho somebody else's hook\n")
    with pytest.raises(SystemExit, match="not installed by this script"):
        install_hooks.install_pre_push(scratch)
