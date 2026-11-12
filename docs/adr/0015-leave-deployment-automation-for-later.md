# 0015. Leave deployment automation for later

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | - |
| Supersedes | - |

## Context

The app is about to move to Railway. A continuous deployment pipeline (build, release, rollback,
previews) is a large decision that depends on how the team wants to release.

## Decision

No deployment workflow exists yet. The repo documents what a deployment needs (required
variables, the start command, the health check) in `docs/runbooks/deployment.md`. Railway can
redeploy on its own when connected to the repository; that is a hosting setting, not a pipeline
owned here. Deployment automation will be defined later and recorded as its own decision.

## Consequences

- CI gates changes, but nothing automates a release or a rollback.
- The deployment runbook must be kept in step with the settings the app requires.
