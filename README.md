# github-actions

Shared custom GitHub Actions for the squadrun org.

## Layout

Each action lives in its own directory with an `action.yml`, so it is referenced as
`squadrun/github-actions/<path>@<ref>`.

| Path | Purpose |
|---|---|
| `terraform/plan` | Terraform plan (planned) |
| `terraform/apply` | Terraform apply (planned) |
| `terraform/drift/{detect,fix,pr}` | Daily drift sync: plan, let Hermes match code to AWS, open a PR. See [`terraform/README.md`](terraform/README.md) |
| `security/gitleaks` | Scan for secrets with the gitleaks CLI |
| `agent/hermes` | Run a one-shot Hermes agent prompt via OpenRouter |

## Usage

```yaml
- uses: squadrun/github-actions/terraform/plan@v1
```

Pin to a tag or SHA, not `main`.

## Runners

Workflows and examples use `ubuntu-26.04` explicitly. JavaScript dependencies use
Node 24; self-hosted runners must be version `2.327.1` or newer. The custom actions
are composite actions and do not select the caller's runner image.

Hermes install caches include the OS distribution and version as well as the
architecture and Hermes revision, so an Ubuntu 24.04 install cannot be restored
on Ubuntu 26.04.

When adopting this migration, update caller workflows to `ubuntu-26.04` and bump
their pinned `squadrun/github-actions` SHAs to the reviewed migration commit.
Existing SHA pins continue to use the old dependencies until updated.
