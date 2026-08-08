#!/usr/bin/env bash
# Lint staged Python files with the ruff version the API pins.
#
# Called by lint-staged (root package.json), which appends the staged paths.
# Before this, the pre-commit hook ran only oxfmt and oxlint -- both JS/TS-only
# -- so Python had no local gate whatsoever and every mistake waited for CI to
# say so. That cost a round trip on 2026-08-07 for one long line and two unused
# imports, in a change that had otherwise already been verified.
#
# --fix is deliberate here and deliberately absent in CI. Locally a fix is kept:
# lint-staged re-stages what the task rewrites. In CI a fix is discarded when the
# runner exits, so `ruff check --fix` there would report success over violations
# that remain in the commit -- a gate that reports on a working copy nobody keeps.
set -euo pipefail

API_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# One source of truth for the version. Bumping requirements/local.txt has to move
# the hook and the uvx fallback with it, or the hook passes what CI then fails.
PINNED="$(sed -n 's/^ruff==\([0-9][0-9.]*\).*/\1/p' "${API_DIR}/requirements/local.txt" | head -1)"

resolve_ruff() {
  # Same env var and default venv as bin/dev-api.sh, so one Python setup serves both.
  if [[ -n "${RUFF:-}" ]]; then
    echo "${RUFF}"
    return 0
  fi
  local venv_ruff="${PLANE_VENV:-${HOME}/.venvs/plane-qa-api}/bin/ruff"
  if [[ -x "${venv_ruff}" ]]; then
    echo "${venv_ruff}"
    return 0
  fi
  if command -v ruff >/dev/null 2>&1; then
    command -v ruff
    return 0
  fi
  return 1
}

if RUFF_BIN="$(resolve_ruff)"; then
  found="$("${RUFF_BIN}" --version | awk '{print $2}')"
  if [[ -n "${PINNED}" && "${found}" != "${PINNED}" ]]; then
    # A warning, not a failure. A newer ruff usually agrees with the pinned one,
    # and blocking a commit over a patch release helps nobody -- but when the two
    # disagree, this line is the difference between "CI is flaky" and "CI runs a
    # different linter than you do".
    echo "ruff ${found} in use, apps/api pins ${PINNED}; CI runs ${PINNED}." >&2
  fi
  exec "${RUFF_BIN}" check --fix --force-exclude "$@"
fi

# No local interpreter set up is normal for someone who only touches the web apps
# -- but they would not be here, because lint-staged only runs this when a .py
# file is staged. Whoever is editing Python needs the linter that guards it.
if command -v uvx >/dev/null 2>&1; then
  exec uvx "ruff@${PINNED}" check --fix --force-exclude "$@"
fi

cat >&2 <<EOF
ruff not found, and Python files are staged.

Install it one of these ways, then commit again:
  pip install ruff==${PINNED}                       (into ~/.venvs/plane-qa-api)
  uv tool install ruff@${PINNED}
  RUFF=/path/to/ruff git commit ...                 (one-off override)

This is a hard failure on purpose. Skipping the check quietly is how apps/api
ended up with no local gate at all.
EOF
exit 1
