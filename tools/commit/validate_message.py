#!/usr/bin/env python3
"""Validate a commit subject or a PR title against the Conventional format in
.contract/rules/general/global-commit.md.

One validator serves both: the `commit-msg` hook checks the commit, and
.github/workflows/pr-title.yml checks the PR title, because GitHub's squash merge uses the
commit subject when a branch holds one commit and the PR title when it holds several. Two
implementations would drift.

The type and scope vocabulary is read from .contract/project.config.json.

Usage:
  python tools/commit/validate_message.py --source=commit .git/COMMIT_EDITMSG
  python tools/commit/validate_message.py --source=pr --text "feat(app): add own questions"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Git and GitHub generate these; they cannot carry our format.
EXEMPT_SUBJECT = re.compile(r"^(Merge |Revert |fixup!|squash!|amend!)")
# GitHub appends " (#123)" to the subject when it squashes.
PR_NUMBER_SUFFIX = re.compile(r"\s\(#\d+\)$")
SUBJECT = re.compile(r"^([a-z]+)(?:\(([^)]*)\))?:\s(.*)$")

SUBJECT_WARN_AT = 72
SUBJECT_FAIL_AT = 100
BODY_WRAP_AT = 78
EM_DASH = chr(0x2014)  # written this way so the source itself stays free of the character


@dataclass
class Result:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    exempt: bool = False


def load_config(root: Path = REPO_ROOT) -> dict:
    raw = json.loads((root / ".contract" / "project.config.json").read_text(encoding="utf-8"))
    return {"types": raw["branchTypes"], "scopes": raw["commitScopes"]}


def strip_git_noise(message: str) -> str:
    """Drop the comment lines git adds, and everything past the --verbose scissors."""
    lines = []
    for line in message.split("\n"):
        if re.match(r"^#\s*-+\s*>8\s*-+", line):
            break
        if line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def validate(message: str, config: dict, source: str = "commit") -> Result:
    types, scopes = config["types"], config["scopes"]
    errors: list[str] = []
    warnings: list[str] = []

    cleaned = strip_git_noise(message)
    if not cleaned:
        return Result(False, ["the message is empty"])

    lines = cleaned.split("\n")
    raw_subject = lines[0]
    if EXEMPT_SUBJECT.match(raw_subject):
        return Result(True, exempt=True)

    subject = PR_NUMBER_SUFFIX.sub("", raw_subject)
    match = SUBJECT.match(subject)
    if not match:
        errors.append("does not match {type}({scope}): {description}")
    else:
        type_, scope, description = match.group(1), match.group(2), match.group(3).strip()
        if type_ not in types:
            errors.append(f'type "{type_}" is not one of: {", ".join(types)}')
        if scope is not None and scope not in scopes:
            errors.append(
                f'scope "{scope}" is not one of: {", ".join(scopes)} '
                "(omit the parentheses when the change spans several)"
            )
        if not description:
            errors.append("the description is empty")
        else:
            if description[0].isupper():
                errors.append(f'the description must be lowercase, got "{description}"')
            if description.endswith("."):
                errors.append("the description must not end with a period")

    if len(subject) > SUBJECT_FAIL_AT:
        errors.append(f"the subject is {len(subject)} characters, over the {SUBJECT_FAIL_AT} limit")
    elif len(subject) > SUBJECT_WARN_AT:
        warnings.append(
            f"the subject is {len(subject)} characters; keep it under {SUBJECT_WARN_AT}, "
            'GitHub appends " (#123)" on merge'
        )

    if EM_DASH in cleaned:
        errors.append("contains an em dash; use a colon, a comma, parentheses, or two sentences")

    if len(lines) > 1 and lines[1].strip() != "":
        errors.append("separate the subject from the body with a blank line")

    if source == "commit":
        overlong = sum(1 for line in lines[2:] if len(line) > BODY_WRAP_AT)
        if overlong:
            warnings.append(f"{overlong} body line(s) exceed {BODY_WRAP_AT} characters")

    return Result(not errors, errors, warnings)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["commit", "pr"], default="commit")
    parser.add_argument("--text")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args(argv)

    if args.source == "commit" and os.environ.get("SKIP_COMMIT_LINT") == "1":
        print("SKIP_COMMIT_LINT=1 set; skipping the commit message check.")
        return 0

    message = args.text if args.text is not None else Path(args.file).read_text(encoding="utf-8") if args.file else ""
    label = "PR title" if args.source == "pr" else "Commit message"
    result = validate(message, load_config(), args.source)

    for warning in result.warnings:
        print(f"warning: {label.lower()} {warning}", file=sys.stderr)
    if result.ok:
        return 0

    subject = (strip_git_noise(message).split("\n")[0]) or "(empty)"
    print(f"\n{label} rejected:\n\n    {subject}\n", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    print("\n  Format:  {type}({scope}): {description}", file=sys.stderr)
    print("  Example: fix(ci): point the health check at /healthz", file=sys.stderr)
    print("  Rule:    .contract/rules/general/global-commit.md\n", file=sys.stderr)
    if args.source == "commit":
        print("  Bypass, for a commit that genuinely cannot take the format:", file=sys.stderr)
        print("    SKIP_COMMIT_LINT=1 git commit ...\n", file=sys.stderr)
    else:
        print("  Fix it with: gh pr edit <number> --title '...'\n", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
