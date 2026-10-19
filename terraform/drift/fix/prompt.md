You are syncing Terraform code with live AWS. AWS is the source of truth: change the code so it matches AWS. You cannot and must not change AWS.

The repository is the current directory. The Terraform root is `{{WORKING_DIRECTORY}}` (workspace `{{WORKSPACE}}`). Modules it uses may live elsewhere in the repo.

## The drift

The JSON at the end comes from `terraform plan`.

`changes` lists what the plan would do. Handle each entry by its `kind`:

- `update`: each item in `diff` is an attribute path. `live` is the value in AWS today and `code` is what the code produces. Edit the code so it produces `live`.
  - Trace the value to its source and change it there: the resource argument, the module input, a local, or a variable default.
  - If a shared module drifted for only one of its callers, change that caller's inputs rather than the module's behaviour for everyone. Add a module variable defaulting to the current value if you need to.
  - If `live` is `(sensitive)`, you cannot see the value: do not guess; report it as unresolved.
  - If `code` is `null` and `live` is a provider-computed default, set the argument explicitly only when that is what makes the plan clean.
- `create`, `delete`, `replace`, or anything else: do not edit. Report each one as unresolved with the action a human should take.

`drift` lists what changed in AWS since the last apply (`was` → `now`). Use it as context only.

## Rules

- Edit only `.tf` files. Do not create, edit, or delete any other file except the report below.
- Never remove a resource, module, or data source from the code.
- Never add `lifecycle { ignore_changes = ... }` to hide drift. If an attribute is clearly managed by another system (autoscaling desired capacity, an externally rotated value), report it as unresolved and suggest `ignore_changes` as the human action.
- Keep edits minimal and match the surrounding style.
- You have no AWS or network access, so `terraform plan` will not work. `{{WORKING_DIRECTORY}}` is initialised without a backend, so `terraform fmt` and `terraform validate` do work there. Run `terraform validate` before finishing.
- If you are not sure an edit is correct, leave that change alone and report it as unresolved. A correct partial fix is better than a wrong full one.

## Report

When done, write this JSON to `{{REPORT_PATH}}`. Every address in `changes` must appear in exactly one list.

```json
{
  "resolved": [{"address": "...", "summary": "what you changed and in which file"}],
  "unresolved": [{"address": "...", "reason": "why you left it", "human_action": "the concrete next step"}]
}
```

## Plan output

```json
{{CHANGES}}
```
