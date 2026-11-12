import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "git" / "refuse_push_to_main.py"


def run(stdin="", **env):
    base = {"PATH": "/usr/bin:/bin"}
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, env={**base, **env}, capture_output=True, text=True
    )


def line(remote_ref):
    return f"refs/heads/some-branch abc123 {remote_ref} def456\n"


def test_a_push_to_main_is_refused_whatever_the_local_branch_is():
    result = run(line("refs/heads/main"))
    assert result.returncode == 1
    assert "Refusing to push to main" in result.stderr


def test_a_push_to_a_feature_branch_is_allowed():
    assert run(line("refs/heads/chore/dev-harness")).returncode == 0


def test_one_blocked_ref_among_several_blocks_the_push():
    assert run(line("refs/heads/feat/x") + line("refs/heads/main")).returncode == 1


def test_the_emergency_bypass_is_honoured():
    assert run(line("refs/heads/main"), ALLOW_PUSH_TO_MAIN="1").returncode == 0


def test_an_empty_push_is_allowed():
    assert run("").returncode == 0
