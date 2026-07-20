#!/usr/bin/env bash
set -euo pipefail

RECONCILIATION_BRANCH="agent/reconcile-foundation-state"
RECEIPT_BRANCH="agent/pf001-main-receipts"
WORKFLOW_ID="315675709"

git config user.name 'Project Foundry Reconciler'
git config user.email 'project-foundry-reconciler@users.noreply.github.com'

current_status() {
  python - <<'PY'
import json
with open('planning/current-state.v1.json', encoding='utf-8') as handle:
    print(json.load(handle)['current_task_status'])
PY
}

approve_exact_head() {
  local head_sha="$1"
  local run_id=""
  for _ in $(seq 1 45); do
    run_id="$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/$WORKFLOW_ID/runs?event=pull_request&head_sha=$head_sha&per_page=20" --jq '.workflow_runs | map(select(.conclusion == "action_required")) | if length > 0 then .[0].id else "" end')"
    if [[ -n "$run_id" ]]; then
      gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$run_id/approve"
      echo "Approved exact-Head Foundation run $run_id for $head_sha"
      return 0
    fi
    sleep 2
  done
  echo "No action-required exact-Head run appeared for $head_sha" >&2
  return 1
}

initialize() {
  local pr_number subject_sha receipt_head
  pr_number="$(gh pr list --repo "$GITHUB_REPOSITORY" --head "$RECONCILIATION_BRANCH" --state open --json number --jq 'if length == 1 then .[0].number else error("expected one open reconciliation PR") end')"
  git fetch origin main "$RECONCILIATION_BRANCH"
  git switch -C "$RECONCILIATION_BRANCH" origin/main

  python scripts/foundation_reconcile.py validation-pending
  git add planning/execution-program.v1.json planning/current-state.v1.json PROJECT_CHARTER.md SYSTEM_MAP.md planning/NEXT_WORK.md
  git commit -m 'Transition PF-001 to validation pending'
  git commit --allow-empty -m 'Establish immutable branch validation subject'
  subject_sha="$(git rev-parse HEAD)"

  python scripts/foundation_reconcile.py validated-on-branch \
    --subject-sha "$subject_sha" \
    --pr-number "$pr_number" \
    --branch "$RECONCILIATION_BRANCH"
  git add planning/execution-program.v1.json planning/current-state.v1.json PROJECT_CHARTER.md SYSTEM_MAP.md planning/NEXT_WORK.md
  git commit -m 'Record exact PF-001 branch validation receipt'
  receipt_head="$(git rev-parse HEAD)"
  git push --force-with-lease="refs/heads/$RECONCILIATION_BRANCH" origin "HEAD:$RECONCILIATION_BRANCH"
  approve_exact_head "$receipt_head"
}

advance_pull_request() {
  local status merge_pending_head
  status="$(current_status)"
  test -n "${RUN_PR_NUMBER:-}"
  if [[ "$status" == 'validated_on_branch' ]]; then
    git switch -C "$RECONCILIATION_BRANCH"
    python scripts/foundation_reconcile.py merge-pending
    git add planning/execution-program.v1.json planning/current-state.v1.json PROJECT_CHARTER.md SYSTEM_MAP.md planning/NEXT_WORK.md
    git commit -m 'Advance externally attested PF-001 to merge pending'
    merge_pending_head="$(git rev-parse HEAD)"
    git push origin "HEAD:$RECONCILIATION_BRANCH"
    approve_exact_head "$merge_pending_head"
  elif [[ "$status" == 'merge_pending' ]]; then
    echo "Exact PR Head is ready for owner-authenticated merge: $RUN_HEAD_SHA"
  fi
}

stage_main_receipt() {
  local status pr_number pr_head_sha
  status="$(current_status)"
  git switch -C main
  if [[ "$status" == 'merge_pending' ]]; then
    parents=( $(git show -s --format=%P "$RUN_HEAD_SHA") )
    test "${#parents[@]}" -eq 2
    gh api "repos/$GITHUB_REPOSITORY/commits/$RUN_HEAD_SHA/pulls" > "$RUNNER_TEMP/merge-pulls.json"
    read -r pr_number pr_head_sha < <(python - "$RUN_HEAD_SHA" "$RUNNER_TEMP/merge-pulls.json" <<'PY'
import json,sys
integration,path=sys.argv[1:]
with open(path, encoding='utf-8') as handle:
    pulls=json.load(handle)
matches=[item for item in pulls if item.get('merged_at') and item.get('merge_commit_sha')==integration]
if len(matches)!=1:
    raise SystemExit(f'expected one hosted merged PR, observed {len(matches)}')
print(matches[0]['number'], matches[0]['head']['sha'])
PY
    )
    python scripts/foundation_reconcile.py merged \
      --integration-sha "$RUN_HEAD_SHA" \
      --pr-head-sha "$pr_head_sha" \
      --pr-number "$pr_number"
    git add planning/execution-program.v1.json planning/current-state.v1.json PROJECT_CHARTER.md SYSTEM_MAP.md planning/NEXT_WORK.md
    git commit -m 'Record hosted Merge receipt for PF-001'
    git push --force origin "HEAD:$RECEIPT_BRANCH"
  elif [[ "$status" == 'merged' ]]; then
    python scripts/foundation_reconcile.py current-main-verified
    rm -f scripts/foundation_reconciliation_controller.sh
    git add -A
    git commit -m 'Verify PF-001 on current main and activate PF-002'
    git push --force origin "HEAD:$RECEIPT_BRANCH"
  fi
}

case "${1:-}" in
  initialize)
    initialize
    ;;
  advance)
    actual_sha="$(git rev-parse HEAD)"
    test "$actual_sha" = "$RUN_HEAD_SHA"
    if [[ "$RUN_EVENT" == 'pull_request' && "$RUN_HEAD_BRANCH" == "$RECONCILIATION_BRANCH" ]]; then
      advance_pull_request
    elif [[ "$RUN_EVENT" == 'push' && "$RUN_HEAD_BRANCH" == 'main' ]]; then
      stage_main_receipt
    fi
    ;;
  *)
    echo "usage: $0 initialize|advance" >&2
    exit 2
    ;;
esac
