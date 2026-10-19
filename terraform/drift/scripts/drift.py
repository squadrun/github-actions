#!/usr/bin/env python3
"""Turn a Terraform plan into a redacted drift summary, a Hermes prompt, and PR text.

Subcommands:
  summarize  plan JSON (terraform show -json) -> drift summary JSON, sensitive values masked
  prompt     drift summary + template -> Hermes prompt
  report     drift summary + residual summary + Hermes report -> PR body, comment, outcome
"""
import argparse
import json
import sys
from pathlib import Path

SENSITIVE = "(sensitive)"
UNKNOWN = "(known after apply)"
# Keeps the prompt well under the 1 MB step-output limit and the model's context.
MAX_CHANGES_BYTES = 150_000
# Kinds Hermes may fix by editing code. Everything else needs a human decision.
AUTO_FIXABLE = {"update"}


# --- Core: pure functions over plain data -----------------------------------


def classify(actions):
    """Map a plan action list to a single kind, or None when nothing changes."""
    if actions in (["no-op"], ["read"]):
        return None
    if "create" in actions and "delete" in actions:
        return "replace"
    return actions[0] if len(actions) == 1 else "+".join(actions)


def redact(value, mask):
    """Replace every value whose sensitivity mask is true."""
    if mask is True:
        return SENSITIVE
    if isinstance(value, dict) and isinstance(mask, dict):
        return {k: redact(v, mask.get(k, False)) for k, v in value.items()}
    if isinstance(value, list) and isinstance(mask, list):
        return [redact(v, mask[i] if i < len(mask) else False) for i, v in enumerate(value)]
    return value


def mark_unknown(value, unknown):
    """Replace every value Terraform only learns at apply time."""
    if unknown is True:
        return UNKNOWN
    if isinstance(unknown, dict):
        base = value if isinstance(value, dict) else {}
        keys = set(base) | {k for k, u in unknown.items() if u is True}
        return {k: mark_unknown(base.get(k), unknown.get(k, False)) for k in keys}
    if isinstance(value, list) and isinstance(unknown, list):
        return [mark_unknown(v, unknown[i] if i < len(unknown) else False) for i, v in enumerate(value)]
    return value


def diff(old, new, path=""):
    """List the leaf paths where old and new differ, as (path, old, new)."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in sorted(set(old) | set(new)):
            out += diff(old.get(key), new.get(key), f"{path}.{key}" if path else key)
        return out
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        out = []
        for i, (o, n) in enumerate(zip(old, new)):
            out += diff(o, n, f"{path}[{i}]")
        return out
    return [] if old == new else [(path, old, new)]


def _masked(change, side):
    value = redact(change.get(side), change.get(f"{side}_sensitive", False))
    if side == "after":
        value = mark_unknown(value, change.get("after_unknown", False))
    return value


def summarize(plan):
    """Reduce a plan to the managed-resource changes and the drift Terraform saw in AWS."""
    changes = []
    for rc in plan.get("resource_changes", []):
        kind = classify(rc["change"]["actions"])
        if kind is None or rc.get("mode") == "data":
            continue
        entry = {"address": rc["address"], "kind": kind}
        if kind in ("update", "replace"):
            before, after = _masked(rc["change"], "before"), _masked(rc["change"], "after")
            # Plan semantics: before is the refreshed live state, after is what the code produces.
            entry["diff"] = [
                {"path": p, "live": o, "code": n} for p, o, n in diff(before, after) if n != UNKNOWN
            ]
        if rc["change"].get("replace_paths"):
            entry["replace_paths"] = rc["change"]["replace_paths"]
        changes.append(entry)

    drift = []
    for rd in plan.get("resource_drift", []):
        before, after = _masked(rd["change"], "before"), _masked(rd["change"], "after")
        drift.append({
            "address": rd["address"],
            "kind": classify(rd["change"]["actions"]) or "no-op",
            "diff": [{"path": p, "was": o, "now": n} for p, o, n in diff(before, after)],
        })

    return {"has_drift": bool(changes), "changes": changes, "drift": drift}


def _fit(summary, limit):
    """Serialize the summary for the prompt, dropping context before dropping changes."""
    payload = {"changes": summary["changes"], "drift": summary["drift"]}
    text = json.dumps(payload, indent=1)
    if len(text) <= limit:
        return text
    payload["drift"] = "(omitted: too large)"
    text = json.dumps(payload, indent=1)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated: fix what is listed and report the rest as unresolved)"


def render_prompt(template, summary, working_directory, workspace, report_path):
    fields = {
        "WORKING_DIRECTORY": working_directory,
        "WORKSPACE": workspace or "default",
        "REPORT_PATH": report_path,
        "CHANGES": _fit(summary, MAX_CHANGES_BYTES),
    }
    for key, value in fields.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def build_outcome(before, residual, hermes_report):
    """Decide what was fixed by comparing the plan before and after Hermes's edits.

    The residual plan is the ground truth; the Hermes report only adds explanations.
    """
    remaining = {c["address"] for c in residual["changes"]}
    hermes_notes = {u.get("address"): u for u in hermes_report.get("unresolved", []) if isinstance(u, dict)}
    hermes_fixes = {r.get("address"): r for r in hermes_report.get("resolved", []) if isinstance(r, dict)}
    resolved = [
        {**c, "summary": hermes_fixes.get(c["address"], {}).get("summary", "")}
        for c in before["changes"] if c["address"] not in remaining
    ]
    unresolved = [
        {
            **c,
            "reason": hermes_notes.get(c["address"], {}).get("reason") or _default_reason(c["kind"]),
            "human_action": hermes_notes.get(c["address"], {}).get("human_action") or _default_action(c["kind"]),
        }
        for c in residual["changes"]
    ]
    return {"solved": not unresolved, "resolved": resolved, "unresolved": unresolved}


def _default_reason(kind):
    return {
        "create": "In code but not in AWS (deleted outside Terraform?)",
        "delete": "Terraform would destroy it",
        "replace": "Terraform would destroy and recreate it",
    }.get(kind, "Code still differs from AWS")


def _default_action(kind):
    return {
        "create": "Confirm it was deleted on purpose, then remove it from code with a `removed {}` block, or recreate it via apply",
        "delete": "Check why Terraform wants to destroy it; restore the code that defines it",
        "replace": "Find the attribute forcing replacement (see `replace_paths`) and match it to AWS",
    }.get(kind, "Update the code so `terraform plan` shows no change")


def _fmt(value):
    text = json.dumps(value) if not isinstance(value, str) else value
    return (text[:80] + "…" if len(text) > 80 else text).replace("|", "\\|").replace("`", "'")


def render_body(name, outcome, run_url):
    status = (
        "All drift is fixed in code. `terraform plan` on this branch shows no changes."
        if outcome["solved"]
        else "Drift is **only partly fixed**. See the checklist comment for what a human needs to do."
    )
    lines = [
        f"Daily drift check for the `{name}` Terraform root found code out of sync with AWS.",
        "AWS is treated as the source of truth: this PR changes code only, so applying it should be a no-op.",
        "",
        status,
        "",
        f"Fixed: {len(outcome['resolved'])} · Needs a human: {len(outcome['unresolved'])} · [Workflow run]({run_url})",
    ]
    if outcome["resolved"]:
        lines += ["", "## Fixed in code", "", "| Resource | Live value now in code |", "|---|---|"]
        for c in outcome["resolved"]:
            detail = c.get("summary") or ", ".join(
                f"`{d['path']}` = `{_fmt(d['live'])}`" for d in c.get("diff", [])[:5]
            )
            lines.append(f"| `{c['address']}` | {detail or c['kind']} |")
    lines += ["", "<sub>Opened by the `terraform/drift` action. The branch is rebuilt on every run.</sub>"]
    return "\n".join(lines) + "\n"


def render_comment(marker, name, outcome, branch, working_directory, workspace):
    if outcome["solved"]:
        return f"{marker}\nNo manual steps left: the latest run fixed all drift for `{name}`.\n"
    lines = [
        marker,
        f"## Manual steps for `{name}`",
        "",
        "These changes are still in `terraform plan` after the automatic fix. "
        "The action has no AWS access while editing, so it can't safely decide these.",
        "",
    ]
    for c in outcome["unresolved"]:
        lines.append(f"- [ ] `{c['address']}` ({c['kind']}): {c['reason']}. **Do:** {c['human_action']}")
        for d in c.get("diff", [])[:5]:
            lines.append(f"  - `{d['path']}`: AWS `{_fmt(d['live'])}`, code `{_fmt(d['code'])}`")
    addresses = " ".join(c["address"] for c in outcome["unresolved"])
    lines += [
        "",
        "### Finish it locally with Claude",
        "",
        "```bash",
        f"git fetch origin {branch} && git checkout {branch}",
        f"cd {working_directory} && terraform init && terraform workspace select {workspace or 'default'}",
        "claude \"Terraform still has drift in this root. AWS is the source of truth: change only the "
        "Terraform code (never AWS) until terraform plan shows no changes. Use import {} blocks for "
        "resources that exist only in AWS and removed {} blocks for ones deleted from AWS, and ask me "
        f"before removing anything. Remaining addresses: {addresses}\"",
        "```",
        "",
        "Push to this branch, then mark the PR ready for review. The next scheduled run rebuilds the "
        "branch from `main`, so merge or close this PR before then.",
    ]
    return "\n".join(lines) + "\n"


# --- Edges: CLI and file I/O ------------------------------------------------


def _read_json(path, default=None):
    p = Path(path)
    if default is not None and (not p.is_file() or not p.read_text().strip()):
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        if default is not None:
            print(f"warning: {path} is not valid JSON; ignoring it", file=sys.stderr)
            return default
        raise


def cmd_summarize(args):
    summary = summarize(_read_json(args.plan_json))
    Path(args.out).write_text(json.dumps(summary, indent=1))
    print(f"changes={len(summary['changes'])} drift={len(summary['drift'])}")


def cmd_prompt(args):
    prompt = render_prompt(
        Path(args.template).read_text(),
        _read_json(args.summary),
        args.working_directory,
        args.workspace,
        args.report_path,
    )
    Path(args.out).write_text(prompt)


def cmd_report(args):
    outcome = build_outcome(
        _read_json(args.before),
        _read_json(args.after),
        _read_json(args.hermes_report, default={}),
    )
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "outcome.json").write_text(json.dumps(outcome, indent=1))
    (out / "body.md").write_text(render_body(args.name, outcome, args.run_url))
    (out / "comment.md").write_text(
        render_comment(args.marker, args.name, outcome, args.branch, args.working_directory, args.workspace)
    )
    print(f"solved={str(outcome['solved']).lower()} resolved={len(outcome['resolved'])} unresolved={len(outcome['unresolved'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summarize")
    s.add_argument("--plan-json", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_summarize)

    p = sub.add_parser("prompt")
    p.add_argument("--summary", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--working-directory", required=True)
    p.add_argument("--workspace", default="")
    p.add_argument("--report-path", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_prompt)

    r = sub.add_parser("report")
    r.add_argument("--name", required=True)
    r.add_argument("--before", required=True)
    r.add_argument("--after", required=True)
    r.add_argument("--hermes-report", required=True)
    r.add_argument("--branch", required=True)
    r.add_argument("--working-directory", required=True)
    r.add_argument("--workspace", default="")
    r.add_argument("--run-url", required=True)
    r.add_argument("--marker", required=True)
    r.add_argument("--out-dir", required=True)
    r.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
