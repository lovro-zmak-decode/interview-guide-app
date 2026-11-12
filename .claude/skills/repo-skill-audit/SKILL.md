---
name: repo-skill-audit
description: This skill should be used when the user asks to "audit skills", "review skill quality", "check for duplicate or overlapping skills", "merge skills". The skill-auditor sub-agent owns the proactive trigger after a skill file changes; this skill is the procedure it follows and the one to use when asked directly. Checks the affected skills against the standards below, reports findings, and applies fixes only after confirmation.
argument-hint: "[scope: a skill name, several comma-separated, or 'all']"
---

> **Tools used:** `Read`, `Glob`, `Grep`, `Write`, `Edit`, `Bash(find:*)`.

Audit skills in `.claude/skills/` and agents in `.claude/agents/` for quality, convention
violations and overlap.

**Never modify or delete a skill file without explicit confirmation.**
**Never remove a field or section without proposing what replaces it.**

## Step 0, scope

Default to the skills that changed, not everything: one changed means that folder name, several
means each of them, and "all" (or an overlap question that names no skill) means `all`. A scoped
audit skips the overlap analysis unless the changed skill shares a prefix with a neighbour.

## Step 1, read and evaluate

Read each in-scope `SKILL.md` in full and check it against this list.

**Frontmatter**

- [ ] `name` matches the folder name exactly (the harness requires it)
- [ ] `description` is third person and starts "This skill should be used when..."
- [ ] `description` contains trigger phrases a user would really type
- [ ] `argument-hint` is present if the skill takes arguments
- [ ] `disable-model-invocation: true` on anything with side effects: deploys, bulk writes
- [ ] a `> **Tools used:**` line at the top of the body

**Content**

- [ ] imperative voice ("Read the file"), not "You should read the file"
- [ ] lean: roughly 1,500 to 2,000 words; over 3,000 needs a `references/` folder
- [ ] every claim about this repo is true right now: paths, commands, ports, scope names
- [ ] destructive steps have a confirmation gate
- [ ] it links to a rule in `.contract/rules/` instead of restating it

**Repo fit**

- [ ] the folder prefix is `repo-` (or a tool name); one area prefix per `apps[].scope` in
      `.contract/project.config.json` (currently none)
- [ ] it does not contradict a rule in `.contract/`, which wins on conflict
- [ ] no em dashes (`style-no-em-dash`)

## Step 2, overlap (scope `all` only)

Build a table of every skill's domain and trigger phrases. Flag any pair whose triggers would both
fire on the same user sentence, and propose a merge or a sharper boundary. Do not perform one.

## Step 3, report

Write findings to `.claude/skills/SKILL-AUDIT-<scope>-<yyyymmdd>.md`, grouped by severity, each
with the file, the problem and the proposed fix. Present a summary and stop. Apply fixes only
after the user accepts. Once applied or discarded, tell the user and delete the audit file; leaving it behind is a
bug (it is git-ignored, but still).
