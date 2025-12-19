#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  echo "WARN: $*" >&2
}

ok() {
  echo "OK: $*"
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || fail "Required command not found in PATH: ${cmd}"
}

repo_root="$(pwd)"

[ -d "${repo_root}/backend" ] || fail "backend/ not found. Run this from repository root."
[ -d "${repo_root}/frontend" ] || fail "frontend/ not found. Run this from repository root."

status_file="${repo_root}/.devcontainer/.post-create.status"
if [ ! -f "${status_file}" ]; then
  fail "postCreateCommand status file not found: ${status_file} (rebuild/recreate the DevContainer to run postCreateCommand)"
fi
post_create_rc="$(head -n 1 "${status_file}" | tr -d '\r' || true)"
if [ "${post_create_rc}" != "0" ]; then
  fail "postCreateCommand did not complete successfully (rc=${post_create_rc}). See .devcontainer/.post-create.log"
fi
ok "postCreateCommand status rc=0"

require_cmd python
python_version="$(python --version 2>&1 | tr -d '\r')"
echo "python --version: ${python_version}"
echo "${python_version}" | grep -Eq '^Python 3\.14\.' || fail "Expected Python 3.14.x"
ok "Python version OK"

require_cmd node
node_version="$(node --version 2>&1 | tr -d '\r')"
echo "node --version: ${node_version}"
echo "${node_version}" | grep -Eq '^v22\.12\.' || fail "Expected Node.js v22.12.x"
ok "Node.js version OK"

require_cmd pip
pip_list="$(pip list 2>&1 || true)"
echo "${pip_list}" | grep -Eiq '^fastapi[[:space:]]' || fail "FastAPI not found in pip list"
echo "${pip_list}" | grep -Eiq '^pydantic[[:space:]]' || fail "Pydantic not found in pip list"
echo "${pip_list}" | grep -Eiq '^uvicorn[[:space:]]' || fail "uvicorn not found in pip list"
ok "Backend dependencies OK (fastapi/pydantic/uvicorn)"

require_cmd npm
npm list next --prefix frontend >/dev/null 2>&1 || fail "Next.js not found (npm list next --prefix frontend failed)"
npm list react --prefix frontend >/dev/null 2>&1 || fail "React not found (npm list react --prefix frontend failed)"
npm list react-dom --prefix frontend >/dev/null 2>&1 || fail "react-dom not found (npm list react-dom --prefix frontend failed)"
npm list typescript --prefix frontend >/dev/null 2>&1 || fail "TypeScript not found (npm list typescript --prefix frontend failed)"
ok "Frontend dependencies OK (next/react/react-dom/typescript)"

required_extensions=(
  "ms-python.python"
  "ms-python.vscode-pylance"
  "charliermarsh.ruff"
  "dbaeumer.vscode-eslint"
  "esbenp.prettier-vscode"
  "bradlc.vscode-tailwindcss"
)

# CI など headless 環境では VS Code が無いため、テスト用にバイパスできるフラグを用意
if [ "${VERIFY_DEVCONTAINER_SKIP_EXTENSIONS:-}" = "1" ]; then
  ok "VS Code extensions check skipped (VERIFY_DEVCONTAINER_SKIP_EXTENSIONS=1)"
  required_extensions=()
fi

installed_extensions=""
if [ "${#required_extensions[@]}" -gt 0 ]; then
  if command -v code >/dev/null 2>&1; then
    installed_extensions="$(code --list-extensions 2>/dev/null || true)"
  elif [ -d "${HOME}/.vscode-server/extensions" ] || [ -d "${HOME}/.vscode-server-insiders/extensions" ]; then
    ext_dir=""
    if [ -d "${HOME}/.vscode-server/extensions" ]; then
      ext_dir="${HOME}/.vscode-server/extensions"
    else
      ext_dir="${HOME}/.vscode-server-insiders/extensions"
    fi
    installed_extensions="$(ls -1 "${ext_dir}" 2>/dev/null | sed -E 's/-[0-9].*$//' || true)"
  else
    warn "VS Code extension directory not found and 'code' command not available; cannot verify extensions."
    fail "Unable to verify VS Code extensions (run inside a VS Code DevContainer session)."
  fi
fi

missing=()
for ext in "${required_extensions[@]}"; do
  echo "${installed_extensions}" | grep -Fxq "${ext}" || missing+=("${ext}")
done

if [ "${#required_extensions[@]}" -gt 0 ]; then
  if [ "${#missing[@]}" -ne 0 ]; then
    printf 'Missing VS Code extensions:\n' >&2
    printf '  - %s\n' "${missing[@]}" >&2
    fail "VS Code extensions check failed"
  fi
  ok "VS Code extensions OK"
fi

ok "DevContainer verification passed."
