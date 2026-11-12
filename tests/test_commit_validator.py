import pytest

from tools.commit.validate_message import load_config, strip_git_noise, validate

CONFIG = {"types": ["feat", "fix", "chore"], "scopes": ["app", "ci"]}
DASH = chr(0x2014)


def check(message, source="commit"):
    return validate(message, CONFIG, source)


@pytest.mark.parametrize(
    "subject",
    [
        "feat(app): add own questions",
        "fix(ci): point the health check at /healthz",
        "chore: bump ruff",
        "feat(app): add own questions (#12)",  # GitHub appends the PR number on a squash merge
    ],
)
def test_valid_subjects_pass(subject):
    assert check(subject).ok


@pytest.mark.parametrize(
    ("subject", "problem"),
    [
        ("Add own questions", "does not match"),
        ("feat(app): Add own questions", "lowercase"),
        ("feat(app): add own questions.", "period"),
        ("feature(app): add it", "type"),
        ("feat(frontend): add it", "scope"),
        ("feat(app):", "does not match"),
        ("feat(app): ", "does not match"),
        (f"feat(app): add it {DASH} quickly", "em dash"),
    ],
)
def test_invalid_subjects_are_rejected_with_a_reason(subject, problem):
    result = check(subject)
    assert not result.ok
    assert any(problem in error for error in result.errors)


def test_git_generated_subjects_are_exempt():
    for subject in ("Merge pull request #5 from x/y", 'Revert "feat(app): x"', "fixup! feat(app): x", "squash! x"):
        assert check(subject).exempt


def test_an_empty_message_is_rejected():
    assert not check("").ok
    assert not check("# only a comment\n").ok


def test_git_comment_lines_and_the_verbose_diff_are_ignored():
    message = "feat(app): add it\n\n# Please enter the commit message\n# ------------------------ >8 ------------------------\ndiff --git a b"
    assert strip_git_noise(message) == "feat(app): add it"
    assert check(message).ok


def test_the_body_must_be_separated_from_the_subject():
    assert not check("feat(app): add it\nbody right away").ok
    assert check("feat(app): add it\n\nbody after a blank line").ok


def test_a_long_subject_warns_and_a_very_long_one_fails():
    warned = check("feat(app): " + "x" * 65)
    assert warned.ok and warned.warnings
    assert not check("feat(app): " + "x" * 100).ok


def test_long_body_lines_only_warn_for_commits():
    body = "feat(app): add it\n\n" + "y" * 90
    assert check(body, "commit").warnings
    assert not check(body, "pr").warnings
    assert check(body).ok


def test_an_em_dash_in_the_body_is_rejected():
    assert not check(f"feat(app): add it\n\nbecause {DASH} reasons").ok


def test_the_vocabulary_comes_from_the_contract_config():
    config = load_config()
    assert "feat" in config["types"] and "app" in config["scopes"]
