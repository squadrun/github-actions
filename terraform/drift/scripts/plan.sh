#!/usr/bin/env bash
# Read-only drift plan: init, select workspace, plan without taking the state lock,
# then write a redacted summary.json and plan.txt to OUT_DIR. The raw plan (which holds
# sensitive values in clear text) is deleted before returning.
#
# Env: OUT_DIR, WORKSPACE (optional), INIT_ARGS (optional). Run from the Terraform root.
set -euo pipefail

mkdir -p "$OUT_DIR"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# shellcheck disable=SC2086
terraform init -input=false $INIT_ARGS
if [ -n "${WORKSPACE:-}" ]; then
  # select, not select -or-create: a drift check must never create state.
  terraform workspace select "$WORKSPACE"
fi

plan_bin="$OUT_DIR/plan.bin"
plan_json="$OUT_DIR/plan.json"
trap 'rm -f "$plan_bin" "$plan_json"' EXIT

set +e
# -lock=false: plan never writes state, and this keeps the drift check from blocking applies.
terraform plan -input=false -lock=false -detailed-exitcode -out="$plan_bin"
code=$?
set -e
if [ "$code" -eq 1 ]; then
  echo "terraform plan failed" >&2
  exit 1
fi

terraform show -no-color "$plan_bin" > "$OUT_DIR/plan.txt"
terraform show -json "$plan_bin" > "$plan_json"
python3 "$script_dir/drift.py" summarize --plan-json "$plan_json" --out "$OUT_DIR/summary.json"
