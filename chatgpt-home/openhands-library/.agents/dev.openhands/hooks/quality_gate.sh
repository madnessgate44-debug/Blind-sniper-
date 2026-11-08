#!/bin/bash
# Stop hook: refuse to let the agent finish while a real gate fails.
#
# Design notes:
#  * Only enforce gates that exist in this project, so it never blocks on
#    missing tooling.
#  * `git diff --check` sees only the working tree, so it passes vacuously once
#    the changes are committed. We therefore also check committed changes
#    against the merge-base with origin/main (falling back to HEAD~1).
#  * Unpushed work is lost on a sandbox restart, so the gate refuses to finish
#    while there are uncommitted changes or commits not pushed to upstream.
#  * Every JSON output is built with python3's json.dumps so it is always valid.
#  * A loop breaker caps consecutive denials: after MAX_DENIALS the gate allows
#    the stop and prints a loud warning, so a stuck agent cannot be trapped
#    forever by a gate it cannot satisfy.
set -u

cd "${OPENHANDS_PROJECT_DIR:-.}" 2>/dev/null || exit 0

MAX_DENIALS=3
project_key="$(printf '%s' "$(pwd)" | cksum | cut -d' ' -f1)"
state_file="/tmp/openhands_quality_gate_${project_key}"

json_line() {
  # $1 = decision, $2 = reason. json.dumps guarantees valid escaping.
  python3 -c 'import json,sys; print(json.dumps({"decision": sys.argv[1], "reason": sys.argv[2]}))' "$1" "$2"
}

deny() {
  count=0
  if [ -f "$state_file" ]; then
    # Expire a stale counter: if the state file was last written more than an
    # hour ago, treat this as a fresh session, not a loop. `-mmin +60` matches
    # an mtime older than 60 minutes.
    if [ -n "$(find "$state_file" -mmin +60 -print -quit 2>/dev/null)" ]; then
      rm -f "$state_file" 2>/dev/null || true
    else
      count="$(cat "$state_file" 2>/dev/null || echo 0)"
    fi
  fi
  case "$count" in ''|*[!0-9]*) count=0 ;; esac
  count=$((count + 1))
  printf '%s' "$count" >"$state_file"
  if [ "$count" -gt "$MAX_DENIALS" ]; then
    msg="Quality gate BYPASSED after ${count} consecutive denials (limit ${MAX_DENIALS}). Reason: $1"
    json_line allow "$msg"
    exit 0
  fi
  json_line deny "$1"
  exit 2
}

clear_state() { rm -f "$state_file" 2>/dev/null || true; }

inside_work_tree() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1
}

# If the checked-out branch is main/master, a bare `git push` would update the
# protected branch. Point the agent at `git switch -c <short-name>` first.
on_protected_branch() {
  case "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" in
    main|master) return 0 ;;
    *) return 1 ;;
  esac
}

BRANCH_HINT=""
if inside_work_tree && on_protected_branch; then
  BRANCH_HINT=" You are on main/master: run \`git switch -c <short-name>\` first."
fi

# 1. Whitespace errors in the working tree.
if inside_work_tree; then
  bad="$(git diff --check 2>/dev/null)"
  if [ -n "$bad" ]; then
    deny "git diff --check reports whitespace errors in the working tree (often a trailing blank line at EOF). Fix them before finishing: perl -0pi -e 's/\n+\z/\n/' <files>"
  fi

  # 2. Whitespace errors in committed changes, which `git diff --check` misses.
  if git rev-parse --verify -q origin/main >/dev/null 2>&1; then
    base="$(git merge-base origin/main HEAD 2>/dev/null)"
  else
    base="$(git rev-parse --verify -q HEAD~1 2>/dev/null)"
  fi
  if [ -n "${base:-}" ]; then
    bad_committed="$(git diff --check "$base" HEAD 2>/dev/null)"
    if [ -n "$bad_committed" ]; then
      deny "git diff --check reports whitespace errors in committed changes (base ${base}). Fix them before finishing."
    fi
  fi

  # 3. Unpushed work: a sandbox restart wipes uncommitted and unpushed changes.
  #    `.openhands/` is the agent's own memory directory (untracked by design),
  #    not task work, so exclude it from the dirty check.
  if git remote get-url origin >/dev/null 2>&1; then
    dirty="$(git status --porcelain -- . ':(exclude).openhands' 2>/dev/null)"
    if [ -n "$dirty" ]; then
      deny "There are uncommitted changes. Commit and push before finishing: git add -A && git commit -m \"...\" && git push -u origin HEAD${BRANCH_HINT}"
    fi
    upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"
    if [ -n "$upstream" ]; then
      ahead="$(git rev-list --count "${upstream}..HEAD" 2>/dev/null || echo 0)"
    elif git rev-parse --verify -q origin/main >/dev/null 2>&1; then
      ahead="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
    else
      ahead=0
    fi
    if [ "${ahead:-0}" -gt 0 ]; then
      deny "There are ${ahead} commit(s) not pushed. Push before finishing: git push -u origin HEAD${BRANCH_HINT}"
    fi
  fi
fi

# 4. Typecheck gate, only if a script exists and dependencies are installed.
if [ -f package.json ] && grep -q '"typecheck"' package.json 2>/dev/null; then
  if [ -d node_modules ]; then
    if ! npm run --silent typecheck >/tmp/tsc_gate.log 2>&1; then
      deny "Typecheck failed. Fix the errors before finishing (see /tmp/tsc_gate.log)."
    fi
  else
    echo "typecheck skipped: dependencies not installed" >&2
  fi
fi

# All gates passed: reset the denial counter.
clear_state
exit 0
