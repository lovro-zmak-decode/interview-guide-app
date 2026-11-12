---
name: repo-pr-review
description: This skill should be used when the user asks to "review this PR", "review pull request 12 against our rules", "run the repo PR review", or says "/repo-pr-review". Reviews only the changed code with independent agents and a verification pass, reports high-confidence bugs and clear violations of this repo's rules, and posts inline comments only when --comment is given.
argument-hint: "[--comment] <owner/repo/pull/N | PR number>"
allowed-tools: Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh pr comment:*), Bash(gh api repos/*/pulls/*/comments*), Bash(git log:*), Bash(git blame:*), Bash(git show:*), Bash(git diff:*), Agent
---

> **Tools used:** `Bash(gh pr view|diff|comment:*)`, `Bash(gh api repos/*/pulls/*/comments*)`,
> `Bash(git log|blame|show|diff:*)`, `Read`, `Glob`, `Grep`, `Agent`.
>
> Without `--comment` this skill is read-only and prints its findings. With `--comment` it posts
> to the pull request. Typing the flag is the confirmation; a comment is trivially reversible.

Review a pull request the way a careful senior engineer would: read the change, hunt for things
that are actually wrong, check them, and say only what survives. False positives erode trust
faster than misses, so the bar is high on purpose.

Tell every subagent: all tools work, make no exploratory calls, and never call the comment tool;
only the top-level run posts.

## Step 0, resolve the target

The argument is `owner/repo/pull/N` or a bare PR number; with none, use the PR for the current
branch. Run `gh pr view <N> --json number,url,headRefOid,isDraft,state` and keep the repo, the
number and the full head SHA (needed for links). Record `--comment` if present. Use `gh` for
GitHub; never web fetch.

## Step 1, decide whether to review

Stop with one line saying why if the PR is closed, merged, a draft, or an automated change that is
obviously correct (a Dependabot bump). Collect what a previous run of this skill already said
(inline review comments, and issue comments starting `## Code review`) as `prior_findings`, and
report only what is new.

## Step 2, collect the rules that apply

Return file paths only: `AGENTS.md`, and the rule files under `.contract/rules/` whose
`appliesTo` globs match a changed file (read `.contract/index.json`). Skip the `global-*` process rules (branching, commits,
PRs, testing). Rules with an empty `appliesTo` but a code subject (the `style-*` rules) do apply.

## Step 3, review in parallel (independent agents)

Run these as separate agents, each given only the diff and the rules above:

1. **Rules audit.** Does the change violate a rule? Quote the rule id and the line.
2. **Bug scan.** Logic errors, missing `None` handling, wrong queries, access control mistakes,
   data hidden only in the page, user text inserted as HTML.
3. **Data and migration check.** Model changes without the matching handling for an existing
   database, and queries that behave differently on PostgreSQL than SQLite.
4. **Tests.** Missing tests for new behaviour, or tests weakened to pass.

## Step 4, verify each finding

For every finding a separate agent tries to disprove it by reading the surrounding code. Keep
only findings that survive. Anything the change did not introduce is out of scope.

## Step 5, report

Group by severity. For each: the file and line (link with the head SHA), the problem, a concrete
failure scenario, and the proposed fix. If nothing survived, say so in one line.

With `--comment`, post each finding as an inline review comment on its line, plus one summary
comment starting `## Code review`. Never post anything else, and never approve or request
changes.
