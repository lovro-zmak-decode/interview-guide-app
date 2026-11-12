---
id: repo-pinned-actions
title: Pin GitHub Actions to commit SHAs, and never put untrusted text in a shell line
scope: [global]
impact: HIGH
triggers: [github actions, workflow, uses, action, sha, pin, dependabot, ci.yml, pr title, untrusted]
appliesTo:
  - .github/**
---

Every `uses:` in `.github/workflows/` is pinned to a full commit SHA with the tag in a comment
(`actions/checkout@<sha> # v7.0.1`); Dependabot bumps them. Pull request titles, branch names
and issue text are untrusted: pass them into a step through `env:`, never inline in a `run:`
line, so they cannot inject commands. Keep `permissions:` as narrow as the job allows.

Source: [ADR 0013](../../../docs/adr/0013-run-ci-as-two-jobs-on-sqlite-and-postgresql-with-pinned-actions.md)
