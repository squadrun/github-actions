# terraform

## drift

Daily drift sync. AWS is the source of truth: when `terraform plan` shows changes, Hermes edits the Terraform code to match AWS and the action opens a PR.

- **Fully fixed** (the re-plan with the edits shows no changes): a ready PR.
- **Partly fixed or not fixable**: a draft PR, plus a comment listing the manual steps and a ready-to-run `claude` prompt for finishing it locally.

It is split into three actions, one per job, so the agent never runs next to credentials:

| Action | Job needs | Does |
|---|---|---|
| `drift/detect` | AWS read, `pull-requests: write` | `plan -lock=false -detailed-exitcode`, uploads a redacted summary, closes the drift PR when drift is gone |
| `drift/fix` | nothing (refuses AWS creds or `id-token`) | Hermes edits `.tf` files from the summary only; uploads the patch |
| `drift/pr` | AWS read, `contents: write`, `pull-requests: write` | applies the patch, re-plans, opens or updates the PR on `drift/<name>` |

What the agent may fix: `update` changes, by making the code produce the live value. Creates, deletes, replacements and sensitive values always go to a human.

Guardrails:
- Sensitive values are masked before anything leaves the detect job, so they never reach the model or an artifact.
- Only `.tf` changes survive the fix job.
- Ready vs draft comes from the re-plan, not from the agent's own report.

See [`drift/examples/drift.yml`](drift/examples/drift.yml). Requires `python3` on the runner, and the repo setting "Allow GitHub Actions to create and approve pull requests". PRs opened with `GITHUB_TOKEN` don't trigger other `pull_request` workflows, so the PR body carries the result instead.

Pin to a commit SHA, not `main`.
