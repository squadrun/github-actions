# github-actions

Shared custom GitHub Actions for the squadrun org.

## Layout

Each action lives in its own directory with an `action.yml`, so it is referenced as
`squadrun/github-actions/<path>@<ref>`.

| Path | Purpose |
|---|---|
| `terraform/plan` | Terraform plan (planned) |
| `terraform/apply` | Terraform apply (planned) |
| `terraform/drift` | Terraform drift detection (planned) |
| `security/gitleaks` | Scan for secrets with the gitleaks CLI |
| `agent/` | Run a coding agent such as pi or hermes (planned) |

## Usage

```yaml
- uses: squadrun/github-actions/terraform/plan@v1
```

Pin to a tag or SHA, not `main`.
