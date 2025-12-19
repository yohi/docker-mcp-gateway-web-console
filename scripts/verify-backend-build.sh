#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "INFO: $*"
}

repo_root="$(pwd)"
compose_file="${COMPOSE_FILE:-docker-compose.yml}"
compose_path="${repo_root}/${compose_file}"
backend_service="${BACKEND_SERVICE:-backend}"
docker_bin="${DOCKER_BIN:-docker}"
python_prefix="${PYTHON_PREFIX:-Python 3.14.}"
health_url="${HEALTH_URL:-http://localhost:8000/health}"

command -v "${docker_bin}" >/dev/null 2>&1 || fail "docker command not found: ${docker_bin}"
[ -d "${repo_root}/backend" ] || fail "backend/ not found. Run this from repository root."
[ -f "${compose_path}" ] || fail "Compose file not found: ${compose_path}"

cleanup_needed="false"
cleanup() {
  if [ "${cleanup_needed}" = "true" ]; then
    ${docker_bin} compose -f "${compose_path}" stop "${backend_service}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

info "Building backend service image (${compose_file})"
${docker_bin} compose -f "${compose_path}" build "${backend_service}"

info "Starting backend service"
${docker_bin} compose -f "${compose_path}" up -d "${backend_service}"
cleanup_needed="true"

info "Validating Python runtime"
python_version="$(${docker_bin} compose -f "${compose_path}" exec -T "${backend_service}" python --version | tr -d '\r')"
echo "python --version: ${python_version}"
case "${python_version}" in
  ${python_prefix}*) ;;
  *) fail "Expected Python version prefix '${python_prefix}' but got '${python_version}'" ;;
esac

info "Checking C extension imports (cryptography)"
${docker_bin} compose -f "${compose_path}" exec -T "${backend_service}" python - <<'PY'
import importlib
import sys

modules = ["cryptography"]
failed = []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failed.append((name, exc))

if failed:
    for name, exc in failed:
        print(f"FAILED:{name}:{exc}", file=sys.stderr)
    sys.exit(1)
PY

info "Checking health endpoint ${health_url}"
health_body="$(${docker_bin} compose -f "${compose_path}" exec -T "${backend_service}" curl -fsSL "${health_url}" | tr -d '\r')"
echo "health response: ${health_body}"
echo "${health_body}" | grep -qi "healthy" || fail "Health endpoint did not return healthy status"

info "Backend build and health verification passed."
