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
init_socket_script="${INIT_DOCKER_SOCKET_SCRIPT:-.devcontainer/init-docker-socket.sh}"
backend_service="${BACKEND_SERVICE:-backend}"
frontend_service="${FRONTEND_SERVICE:-frontend}"
docker_bin="${DOCKER_BIN:-docker}"
backend_health_url="${BACKEND_HEALTH_URL:-http://localhost:8000/health}"
frontend_status_url="${FRONTEND_STATUS_URL:-http://${backend_service}:8000/api/v1/status}"

compose_path="${repo_root}/${compose_file}"
dev_compose_path="${repo_root}/${dev_compose_file}"
init_socket_path="${repo_root}/${init_socket_script}"

command -v "${docker_bin}" >/dev/null 2>&1 || fail "docker command not found: ${docker_bin}"
[ -f "${compose_path}" ] || fail "Compose file not found: ${compose_path}"
[ -f "${dev_compose_path}" ] || fail "DevContainer compose file not found: ${dev_compose_path}"
[ -x "${init_socket_path}" ] || fail "Docker socket init script not found or not executable: ${init_socket_path}"

TTY_FLAG=""
if [ "${CI:-}" = "true" ] || [ "${TERM:-}" = "dumb" ] || [ ! -t 0 ]; then
  TTY_FLAG="-T"
fi

detect_socket() {
  info "Detecting Docker socket via ${init_socket_script}"
  socket_output="$("${init_socket_path}")"
  eval "${socket_output}"
  if [ -z "${DOCKER_SOCKET:-}" ]; then
    fail "DOCKER_SOCKET not set by ${init_socket_script}"
  fi
  if [ -S "${DOCKER_SOCKET}" ]; then
    return 0
  fi
  if [ "${DOCKER_SOCKET_ALLOW_REGULAR_FILE:-0}" = "1" ] && [ -e "${DOCKER_SOCKET}" ]; then
    return 0
  fi
  fail "Docker socket path not usable: ${DOCKER_SOCKET}"
}

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

detect_socket

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

info "Validating Docker socket access at ${DOCKER_SOCKET}"
"${docker_bin}" --host "unix://${DOCKER_SOCKET}" ps >/dev/null

info "Validating DevContainer backend dev command"
compose_exec "${dev_compose_path}" "${backend_service}" python - <<'PY'
import uvicorn  # noqa: F401
print("uvicorn import ok")
PY

info "Validating DevContainer frontend dev command"
compose_exec "${dev_compose_path}" "${frontend_service}" npm run dev -- --help >/dev/null

info "Integration verification passed."
