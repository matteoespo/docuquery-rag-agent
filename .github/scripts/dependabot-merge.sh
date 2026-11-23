#!/usr/bin/env bash
# Squash-merge a Dependabot PR only if it is safe:
#   - opened by Dependabot
#   - every dependency in it is a semver patch/minor update (majors need a human)
#   - it doesn't modify .github/workflows (GITHUB_TOKEN can't merge those anyway)
#   - both CI jobs passed on its current head commit
# Anything else is skipped with exit 0; only a failed merge exits non-zero.
#
# Usage: dependabot-merge.sh <pr-number>
# Env:   GH_TOKEN, GH_REPO (owner/name), CO_AUTHOR (optional "Name <email>" trailer)
set -euo pipefail

pr="$1"
REQUIRED_CHECKS=("Backend Tests (Pytest)" "Frontend Lint & Build")

skip() { echo "#$pr: skipped — $1"; exit 0; }

read -r author sha < <(gh pr view "$pr" --json author,headRefOid -q '"\(.author.login) \(.headRefOid)"')
[[ "$author" == "app/dependabot" ]] || skip "not opened by Dependabot ($author)"

if gh pr view "$pr" --json files -q '.files[].path' | grep -q '^\.github/workflows/'; then
  skip "modifies workflow files, merge manually"
fi

msg=$(gh api "repos/$GH_REPO/commits/$sha" -q .commit.message)
if grep -q 'update-type: version-update:semver-major' <<<"$msg"; then
  skip "contains a semver-major update"
fi
grep -qE 'update-type: version-update:semver-(minor|patch)' <<<"$msg" || skip "no update-type metadata"

for check in "${REQUIRED_CHECKS[@]}"; do
  conclusion=$(gh api -X GET "repos/$GH_REPO/commits/$sha/check-runs" -f check_name="$check" \
    -q '.check_runs[0].conclusion // "missing"')
  [[ "$conclusion" == "success" ]] || skip "CI check '$check' is $conclusion"
done

body=$(tail -n +3 <<<"$msg")
[[ -n "${CO_AUTHOR:-}" ]] && body+=$'\n\n'"Co-authored-by: $CO_AUTHOR"

# --match-head-commit: refuse if a newer, unverified commit was pushed meanwhile.
gh pr merge "$pr" --squash --match-head-commit "$sha" --body "$body"
echo "#$pr: merged"
