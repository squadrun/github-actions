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

## Install cache for comment-triggered reviews

GitHub gives `issue_comment` runs read-only access to default-branch caches.
Set the review job's `cache-mode: read` and pass `save-cache: "false"` to Hermes.
A cache miss still installs Hermes and runs the review, without attempting a save.

Warm the install cache in the **caller repository** using
`squadrun/github-actions/agent/hermes/setup@<commit-sha>` with `save-cache: "true"`.
Run it on trusted pushes to the default branch, a daily schedule, or manual
`workflow_dispatch` on the default branch, with `cache-mode: write`.
The setup action requires no API key, does not run a prompt, and uses exactly the
same Hermes revision, OS-specific key and install paths as the review action.
Override `hermes-ref` identically in both actions when changing Hermes versions.
Keep the warmer free of PR checkouts and PR-controlled code. A warmer in this
shared-actions repository cannot populate a consumer repository's cache.
