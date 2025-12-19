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
frontend_service="${FRONTEND_SERVICE:-frontend}"
docker_bin="${DOCKER_BIN:-docker}"
node_prefix="${NODE_PREFIX:-v22.12.}"
health_url="${HEALTH_URL:-http://localhost:3000}"

command -v "${docker_bin}" >/dev/null 2>&1 || fail "docker command not found: ${docker_bin}"
[ -d "${repo_root}/frontend" ] || fail "frontend/ not found. Run this from repository root."
[ -f "${compose_path}" ] || fail "Compose file not found: ${compose_path}"

cleanup_needed="false"
cleanup() {
  status=$?
  if [ "${cleanup_needed}" = "true" ]; then
    ${docker_bin} compose -f "${compose_path}" stop "${frontend_service}" >/dev/null 2>&1 || true
  fi
  if [ $status -ne 0 ]; then
    info "Collecting logs for ${frontend_service} (exit ${status})"
    ${docker_bin} compose -f "${compose_path}" logs "${frontend_service}" || true
  fi
  exit $status
}
trap cleanup EXIT

info "Building frontend service image (${compose_file})"
${docker_bin} compose -f "${compose_path}" build "${frontend_service}"

info "Starting frontend service"
${docker_bin} compose -f "${compose_path}" up -d "${frontend_service}"
cleanup_needed="true"

info "Validating Node.js runtime"
node_version="$(${docker_bin} compose -f "${compose_path}" exec -T "${frontend_service}" node --version | tr -d '\r')"
echo "node --version: ${node_version}"
case "${node_version}" in
  ${node_prefix}*) ;;
  *) fail "Expected Node.js version prefix '${node_prefix}' but got '${node_version}'" ;;
esac

info "Checking frontend health at ${health_url}"
health_body="$(${docker_bin} compose -f "${compose_path}" exec -T "${frontend_service}" curl -fsSL "${health_url}" | tr -d '\r')"
if [ -z "${health_body}" ]; then
  fail "Health endpoint returned empty response"
fi

info "Frontend build and health verification passed."
