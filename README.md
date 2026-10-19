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
