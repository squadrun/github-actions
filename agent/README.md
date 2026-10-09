# agent

Runs a coding agent (such as pi or hermes) inside a GitHub Actions job.

**Status:** planned. The action isn't implemented yet, so the inputs below are placeholders.

## Use from another repo

```yaml
- uses: squadrun/github-actions/agent@v1
  with:
    agent: pi                              # TBD: pi or hermes
    prompt: "Review the diff in this PR"   # TBD
```

Pin to a release tag or commit SHA, not `main`.
