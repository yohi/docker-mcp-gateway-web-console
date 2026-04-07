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
dev_compose_file="${DEVCONTAINER_COMPOSE_FILE:-.devcontainer/docker-compose.devcontainer.yml}"
backend_service="${BACKEND_SERVICE:-backend}"
frontend_service="${FRONTEND_SERVICE:-frontend}"
workspace_service="${WORKSPACE_SERVICE:-workspace}"
docker_bin="${DOCKER_BIN:-docker}"
backend_health_url="${BACKEND_HEALTH_URL:-http://localhost:8000/health}"
frontend_status_url="${FRONTEND_STATUS_URL:-http://${backend_service}:8000/api/v1/status}"

compose_path="${repo_root}/${compose_file}"
dev_compose_path="${repo_root}/${dev_compose_file}"

command -v "${docker_bin}" >/dev/null 2>&1 || fail "docker command not found: ${docker_bin}"
[ -f "${compose_path}" ] || fail "Compose file not found: ${compose_path}"
[ -f "${dev_compose_path}" ] || fail "DevContainer compose file not found: ${dev_compose_path}"

TTY_FLAG=""
if [ "${CI:-}" = "true" ] || [ "${TERM:-}" = "dumb" ] || [ ! -t 0 ]; then
  TTY_FLAG="-T"
fi

compose_exec() {
  local file="$1"
  shift
  local service="$1"
  shift
  local args=("${docker_bin}" compose -f "${file}" exec)
  if [ -n "${TTY_FLAG}" ]; then
    args+=("${TTY_FLAG}")
  fi
  args+=("${service}" "$@")
  "${args[@]}"
}

require_dind_config() {
  info "Validating DinD/TLS configuration in ${dev_compose_file}"
  grep -q "dind:" "${dev_compose_path}" || fail "dind service missing from ${dev_compose_file}"
  grep -q "DOCKER_HOST=tcp://dind:2376" "${dev_compose_path}" || fail "DOCKER_HOST for dind missing from ${dev_compose_file}"
  grep -q "DOCKER_TLS_VERIFY=1" "${dev_compose_path}" || fail "DOCKER_TLS_VERIFY missing from ${dev_compose_file}"
  grep -q "DOCKER_CERT_PATH=/certs/client" "${dev_compose_path}" || fail "DOCKER_CERT_PATH missing from ${dev_compose_file}"
  grep -q "dind-certs:/certs/client:ro" "${dev_compose_path}" || fail "dind client cert mount missing from ${dev_compose_file}"
}

require_dind_config

info "Checking backend health at ${backend_health_url}"
health_body="$(compose_exec "${compose_path}" "${backend_service}" curl -fsSL "${backend_health_url}" | tr -d '\r')"
if ! echo "${health_body}" | grep -qi '"status"'; then
  fail "Backend health response missing status field: ${health_body}"
fi
if ! echo "${health_body}" | grep -qi "ok"; then
  fail "Backend health response not OK: ${health_body}"
fi

info "Checking frontend -> backend connectivity (${frontend_status_url})"
frontend_status="$(compose_exec "${compose_path}" "${frontend_service}" curl -fsSL "${frontend_status_url}" | tr -d '\r')"
if [ -z "${frontend_status}" ]; then
  fail "Frontend connectivity check returned empty response"
fi

info "Validating DevContainer backend Docker access via DinD"
compose_exec "${dev_compose_path}" "${backend_service}" docker info >/dev/null

info "Validating DevContainer workspace Docker access via DinD"
compose_exec "${dev_compose_path}" "${workspace_service}" docker info >/dev/null

info "Validating DevContainer frontend dev command"
compose_exec "${dev_compose_path}" "${frontend_service}" npm run dev -- --help >/dev/null

info "Integration verification passed."
