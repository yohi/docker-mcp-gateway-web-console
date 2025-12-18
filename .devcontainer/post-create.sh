#!/usr/bin/env bash
set -u
set -o pipefail

repo_root="${WORKSPACE_FOLDER:-/workspace}"
status_file="${repo_root}/.devcontainer/.post-create.status"
log_file="${repo_root}/.devcontainer/.post-create.log"

mkdir -p "$(dirname "${status_file}")"

rc=0
{
  echo "[post-create] repo_root=${repo_root}"
  echo "[post-create] $(date -Iseconds)"

  echo "[post-create] Installing backend dependencies..."
  (cd "${repo_root}/backend" && pip install -r requirements.txt) || rc=$?

  if [ "${rc}" -eq 0 ]; then
    echo "[post-create] Installing frontend dependencies..."
    (cd "${repo_root}/frontend" && npm ci) || rc=$?
  fi

  echo "[post-create] done rc=${rc}"
} >"${log_file}" 2>&1

printf '%s\n' "${rc}" >"${status_file}"

if [ "${rc}" -ne 0 ]; then
  echo "postCreateCommand failed (rc=${rc}). See ${log_file}" >&2
fi

exit "${rc}"

