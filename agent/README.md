# agent

Runs a coding agent inside a GitHub Actions job.

## hermes

Runs a one-shot [Hermes](https://hermes-agent.nousresearch.com) prompt on OpenRouter and optionally comments the output on a PR.

The action does not check out code. Run `actions/checkout` first so the agent can read the repo.

See [`hermes/examples/pr-review.yml`](hermes/examples/pr-review.yml) for a PR review workflow that follows `review.md`.

```yaml
- uses: squadrun/github-actions/agent/hermes@<commit-sha>
  with:
    prompt: "Review the diff in this PR"
    openrouter-api-key: ${{ secrets.OPENROUTER_API_KEY }}
    pr-number: ${{ github.event.pull_request.number }}
    yolo: "true"   # required for unattended tool use
```

Pin to a release tag or commit SHA, not `main`.
