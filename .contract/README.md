# Agent Contract: how it works and how to extend it

This folder is the single source of truth for the rules any coding agent follows in this repo
(Claude Code, Cursor, Codex, whatever). If you have ever pasted "remember to branch first" into an
agent, this is where that knowledge lives now, once.

The design is borrowed from the A List monorepo's `.contract/` and ported to Python.

## The mental model (four layers)

An agent reads a little and pulls only what the task needs:

1. **`/AGENTS.md`** (root, tiny): universal rules plus a routing table. Always read.
2. **`.contract/rules/{general,project}/*.md`** (one rule each): the detail. Read only when the
   routing table points there. `general/` holds portable way-of-working rules, `project/` holds
   rules specific to this app. The folder sets the rule's class.
3. **`.contract/index.json`** and **`.contract/reference/AGENTS.full.md`**: machine index and
   compiled whole-set document, for tooling and search. Not read by hand.

## How to add or change a rule

You never hand-edit the routing table, `index.json`, the compiled reference, or the resolved
general rules (`.contract/rules/general/`). You edit a source and regenerate.

- **Project rule** (specific to this app): author it at `.contract/rules/project/<prefix>-<slug>.md`.
- **General rule** (portable): author a *template* at `.contract/templates/general/<prefix>-<slug>.md`,
  using `{{placeholders}}` for anything that varies per repo. The build resolves it into
  `.contract/rules/general/<same-name>.md`, which is generated.

Then:

```bash
python .contract/scripts/build_agents.py          # rewrite every derived artifact
python .contract/scripts/build_agents.py --check  # fail if artifacts are stale (CI and the hook run this)
```

Copy `.contract/rules/_template.md` as a starting point. The filename must equal the `id` in the
frontmatter; the build enforces this.

## Frontmatter fields

```yaml
---
id: data-scoring-visibility        # must match the filename (minus .md)
title: Hide scores from others only while an interview is in progress
scope: [global]                    # global, or an area listed in project.config.json apps
impact: CRITICAL                   # CRITICAL | HIGH | MEDIUM | LOW (reference ordering)
triggers: [score, grade, hidden]   # words that route a task to this rule
appliesTo:                         # optional globs, lets tools match a rule to a file
  - app.py
---
```

## Project config

Everything project-specific lives in `.contract/project.config.json`: the branch and commit
vocabulary, protected branches, area list and reference categories. General rule templates
interpolate `{{placeholders}}` from it, and the commit validator and the push guard read it too,
so a rule and its enforcement cannot disagree.

## Guardrails

The build fails, rather than producing something subtly wrong, when:

| Condition | Error |
|---|---|
| A template uses a key absent from `project.config.json` | `unknown placeholder` |
| A rule's filename does not match its `id` | `filename must match id` |
| Two rules share an `id` | `duplicate rule id` |
| Required frontmatter is missing | `missing required frontmatter field` |
| A target file lacks its `BEGIN/END GENERATED` markers | `missing generated markers` |
| Committed artifacts are stale (`--check`) | exit 1, lists the stale files |

The build and its guardrails are covered by `tests/test_contract_build.py`.
